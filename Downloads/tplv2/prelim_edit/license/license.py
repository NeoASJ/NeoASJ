"""
╔══════════════════════════════════════════════════════════════════╗
║           APPLICATION LICENSE PROTECTION SYSTEM                  ║
║   Locks your .exe to ONE specific machine using hardware ID      ║
╚══════════════════════════════════════════════════════════════════╝

HOW TO USE:
  Step 1 → Run: app.exe --generate-license   (on the authorized machine)
  Step 2 → Send the user: app.exe + license.json
  Step 3 → App will auto-verify on every launch

COMMANDS:
  app.exe --generate-license    → Creates license.json for this machine
  app.exe --show-fingerprint    → Shows this machine's hardware fingerprint
  app.exe                       → Normal launch (verifies license automatically)
"""
import hashlib
import hmac
import json
import uuid
import platform
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv()
# ══════════════════════════════════════════════════════════════════
# CONFIGURATION  ──  Change these values before building your .exe
# ══════════════════════════════════════════════════════════════════

SECRET_KEY = os.getenv("SECRET_KEY_FN").encode()
# Your application name — must match exactly in license.json
APP_NAME = "MyApp"
# License file must be placed in the SAME folder as the .exe
LICENSE_FILE = "license.json"

# ══════════════════════════════════════════════════════════════════
# STEP 1 — Collect hardware identifiers from the current machine
# ══════════════════════════════════════════════════════════════════

def get_hardware_fingerprint() -> str:
    """
    Reads hardware info from the current machine and returns a unique
    SHA256 fingerprint. This fingerprint will be DIFFERENT on every machine.
    
    Collects:
      - MAC address (network card)
      - CPU model
      - OS type and hostname
      - BIOS serial / motherboard serial / disk UUID (Windows/Linux/macOS)
    """
    components = []

    # --- Universal identifiers (work on all OS) ---
    components.append(hex(uuid.getnode()))          # MAC address
    components.append(platform.processor())          # CPU name
    components.append(platform.machine())            # CPU architecture (x86_64 etc.)
    components.append(platform.system())             # OS name (Windows/Linux/Darwin)
    components.append(platform.node())               # Hostname / computer name

    system = platform.system()

    # --- Linux-specific hardware IDs ---
    if system == "Linux":
        linux_sources = [
            ("machine-id", ["cat", "/etc/machine-id"]),                        # Unique OS install ID
            ("dmi-uuid",   ["cat", "/sys/class/dmi/id/product_uuid"]),          # Motherboard UUID
            ("bios-serial",["cat", "/sys/class/dmi/id/product_serial"]),        # BIOS serial
            ("disk-uuid",  ["blkid", "-s", "UUID", "-o", "value", "/dev/sda1"]),# Disk UUID
        ]
        for label, command in linux_sources:
            try:
                output = subprocess.check_output(command, stderr=subprocess.DEVNULL)
                components.append(f"{label}:{output.decode().strip()}")
            except Exception:
                pass  # Skip silently if not available

    # --- Windows-specific hardware IDs ---
    elif system == "Windows":
        windows_sources = [
            ("bios",  ["wmic", "bios",        "get", "serialnumber"]),  # BIOS serial
            ("board", ["wmic", "baseboard",   "get", "serialnumber"]),  # Motherboard serial
            ("uuid",  ["wmic", "csproduct",   "get", "UUID"]),           # System UUID
            ("cpu",   ["wmic", "cpu",         "get", "processorid"]),    # CPU ID
            ("disk",  ["wmic", "diskdrive",   "get", "serialnumber"]),   # Hard drive serial
        ]
        for label, command in windows_sources:
            try:
                output = subprocess.check_output(command, stderr=subprocess.DEVNULL)
                components.append(f"{label}:{output.decode().strip()}")
            except Exception:
                pass
    
    # --- macOS-specific hardware IDs ---
    elif system == "Darwin":
        try:
            output = subprocess.check_output(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                stderr=subprocess.DEVNULL
            )
            for line in output.decode().splitlines():
                if "IOPlatformSerialNumber" in line or "IOPlatformUUID" in line:
                    components.append(line.strip())
        except Exception:
            pass

    # Combine all parts and hash into a single 64-character fingerprint
    raw_string = "|".join(filter(None, components))
    fingerprint = hashlib.sha256(raw_string.encode()).hexdigest()
    return fingerprint


# ══════════════════════════════════════════════════════════════════
# STEP 2 — Generate a license file locked to this machine
# ══════════════════════════════════════════════════════════════════

def generate_license() -> str:
    """
    Call this ONCE on the machine you want to authorize.
    Creates a license.json file tied to that machine's hardware fingerprint.
    
    The license contains:
      - machine_id  → The hardware fingerprint of the authorized machine
      - app         → Your application name (must match APP_NAME)
      - issued_at   → Timestamp of when the license was created
      - sig         → HMAC cryptographic signature (prevents tampering)
    """
    if not SECRET_KEY:
        raise ValueError(
            "❌ SECRET_KEY is empty!\n"
            "Set it in the script or use: export APP_SECRET='your-secret'"
        )

    machine_id = get_hardware_fingerprint()

    # Build the payload (the data we want to lock)
    payload = json.dumps({
        "app":        APP_NAME,
        "issued_at":  datetime.now(timezone.utc).isoformat(),
        "machine_id": machine_id,
    }, sort_keys=True)

    # Sign the payload using HMAC-SHA256 (proves the payload was not tampered with)
    signature = hmac.new(SECRET_KEY, payload.encode(), hashlib.sha256).hexdigest()

    # Combine into final license structure
    license_data = json.dumps({
        "payload": payload,
        "sig":     signature,
    }, indent=2)

    return license_data


# ══════════════════════════════════════════════════════════════════
# STEP 3 — Verify the license on every launch
# ══════════════════════════════════════════════════════════════════

def verify_license() -> bool:
    """
    Runs automatically every time the app starts.
    Returns True only if ALL of these checks pass:
    
      Check 1 → license.json file exists next to the .exe
      Check 2 → HMAC signature is valid (file was not tampered with)
      Check 3 → machine_id in the file matches THIS machine's hardware
      Check 4 → App name in the file matches APP_NAME
    
    If ANY check fails → returns False → app exits.
    """
    if not SECRET_KEY:
        _show_error("Configuration Error", "APP_SECRET is not set in the application.")
        return False

    try:
        # --- Check 1: Does the license file exist? ---
        license_path = Path(LICENSE_FILE)
        if not license_path.exists():
            _show_error(
                "License Not Found",
                f"'{LICENSE_FILE}' is missing.\n\nContact the software provider."
            )
            return False

        license_data = json.loads(license_path.read_text())
        payload_str  = license_data["payload"]
        stored_sig   = license_data["sig"]

        # --- Check 2: Is the HMAC signature valid? ---
        # If someone edited license.json, the signature won't match
        expected_sig = hmac.new(SECRET_KEY, payload_str.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(stored_sig, expected_sig):
            _show_error(
                "License Corrupted",
                "The license file has been modified or is invalid."
            )
            return False

        # Parse the payload now that we know it's authentic
        payload = json.loads(payload_str)

        # --- Check 3: Does this machine's hardware match the license? ---
        current_machine_id = get_hardware_fingerprint()
        if payload.get("machine_id") != current_machine_id:
            _show_error(
                "Unauthorized Machine",
                "This application is not licensed for this computer.\n\n"
                "The license is locked to a different machine."
            )
            return False

        # --- Check 4: Does the app name match? ---
        if payload.get("app") != APP_NAME:
            _show_error(
                "Invalid License",
                "This license file belongs to a different application."
            )
            return False

        # All checks passed ✅
        return True

    except (FileNotFoundError, KeyError, json.JSONDecodeError) as e:
        _show_error("License Error", f"Could not read license file.\n\nDetails: {e}")
        return False


# ══════════════════════════════════════════════════════════════════
# HELPER — Show error popup (works even without a GUI framework)
# ══════════════════════════════════════════════════════════════════

def _show_error(title: str, message: str):
    """Shows a popup error dialog if tkinter is available, otherwise prints to console."""
    print(f"\n❌ {title}: {message}\n")
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()  # Hide the blank root window
        root.attributes("-topmost", True)
        messagebox.showerror(title, message)
        root.destroy()
    except Exception:
        pass  # If no GUI available, the console print above is enough


# ══════════════════════════════════════════════════════════════════
# YOUR APPLICATION LOGIC — Replace this with your real app code
# ══════════════════════════════════════════════════════════════════

def run_application():
    """
    This function only runs AFTER the license is verified successfully.
    Replace the contents with your actual application logic.
    """
    print("✅ License verified. Application is running!")
    print(f"   App     : {APP_NAME}")
    print(f"   Machine : {get_hardware_fingerprint()[:16]}...  (authorized)")
    print()

    # ── PUT YOUR APP CODE HERE ──────────────────────────────────
    # Examples:
    #   from your_gui import start_gui; start_gui()
    #   from your_tool import main; main()
    # ────────────────────────────────────────────────────────────


# ══════════════════════════════════════════════════════════════════
# ENTRY POINT — Program starts here
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":

    # ── Command: Generate license for this machine ──
    if "--generate-license" in sys.argv:
        print(f"\n🔐 Generating license for this machine...")
        print(f"   App name    : {APP_NAME}")
        print(f"   Fingerprint : {get_hardware_fingerprint()}")
        print()

        license_str = generate_license()
        Path(LICENSE_FILE).write_text(license_str)

        print(f"✅ License saved to: {LICENSE_FILE}")
        print(f"\n📦 Distribute to the user:")
        print(f"   ├── your_app.exe")
        print(f"   └── {LICENSE_FILE}   ← locked to THIS machine only")
        sys.exit(0)
    # ── Command: Show this machine's fingerprint ──
    elif "--show-fingerprint" in sys.argv:
        print(f"\n🖥️  Hardware Fingerprint for this machine:")
        print(f"   {get_hardware_fingerprint()}")
        print(f"\n   (This value is unique to this computer's hardware)")
        sys.exit(0)
    
    # ── Normal launch: verify license then run app ──
    else:
        if verify_license():
            run_application()
        else:
            sys.exit(1)