import hashlib
import uuid
import platform
import subprocess

def get_windows_hardware_raw():
    print("\n" + "="*60)
    print("   WINDOWS HARDWARE COMPONENTS - RAW OUTPUT")
    print("="*60)

    # --- Universal identifiers ---
    print("\n[UNIVERSAL]")
    print(f"  MAC Address       : {hex(uuid.getnode())}")
    print(f"  CPU Name          : {platform.processor()}")
    print(f"  CPU Architecture  : {platform.machine()}")
    print(f"  OS Name           : {platform.system()}")
    print(f"  Hostname          : {platform.node()}")

    # --- Windows-specific hardware IDs ---
    print("\n[WINDOWS SPECIFIC]")
    windows_sources = [
        ("BIOS Serial",         ["wmic", "bios",      "get", "serialnumber"]),
        ("Motherboard Serial",  ["wmic", "baseboard", "get", "serialnumber"]),
        ("System UUID",         ["wmic", "csproduct", "get", "UUID"]),
        ("CPU ID",              ["wmic", "cpu",       "get", "processorid"]),
        ("Disk Serial",         ["wmic", "diskdrive", "get", "serialnumber"]),
    ]

    for label, command in windows_sources:
        try:
            output = subprocess.check_output(command, stderr=subprocess.DEVNULL)
            value = output.decode().strip()
            print(f"  {label:<22}: {value}")
        except Exception as e:
            print(f"  {label:<22}: ERROR - {e}")

    # --- Final combined fingerprint ---
    print("\n[COMBINED FINGERPRINT]")
    components = [
        hex(uuid.getnode()),
        platform.processor(),
        platform.machine(),
        platform.system(),
        platform.node(),
    ]
    for label, command in windows_sources:
        try:
            output = subprocess.check_output(command, stderr=subprocess.DEVNULL)
            components.append(output.decode().strip())
        except Exception:
            pass

    raw_string  = "|".join(filter(None, components))
    fingerprint = hashlib.sha256(raw_string.encode()).hexdigest()
    print(f"  SHA256 : {fingerprint}")
    print("\n" + "="*60)


if __name__ == "__main__":
    get_windows_hardware_raw()