import cv2
from ultralytics import YOLO
import time
from datetime import datetime
import json
import os
import sys
import threading
import queue
import torch
from concurrent.futures import ThreadPoolExecutor   
from alarm_v2_v1 import AlarmPlayer
import yaml
import ctypes
import win32gui
import win32con
from notification_codebase import email_coke, send_sms

# FFMpeg related suppression
os.environ['OPENCV_FFMPEG_LOGLEVEL'] = 'quiet'
os.environ['OPENCV_LOG_LEVEL']       = 'SILENT'
cv2.setLogLevel(-1)

# ======================
# YAML CONFIGURATION LOADER
# ======================
def load_yaml_config(yaml_path="detection_core.yaml"):
    """Load configuration from YAML file - PyInstaller compatible"""
    if getattr(sys, 'frozen', False):
        exe_dir        = os.path.dirname(sys.executable)
        yaml_full_path = os.path.join(exe_dir, yaml_path)

        if not os.path.exists(yaml_full_path):
            application_path = sys._MEIPASS
            yaml_full_path   = os.path.join(application_path, yaml_path)
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))
        yaml_full_path   = os.path.join(application_path, yaml_path)

    print(f"[DEBUG] Looking for YAML at: {yaml_full_path}")
    print(f"[DEBUG] File exists: {os.path.exists(yaml_full_path)}")

    if not os.path.exists(yaml_full_path):
        raise FileNotFoundError(
            f"Configuration file '{yaml_path}' not found!\n"
            f"Searched in: {yaml_full_path}"
        )
    
    print(f"[INFO] Loading YAML config from: {yaml_full_path}")
    with open(yaml_full_path, 'r') as f:
        return yaml.safe_load(f)


# Load YAML configurations
yaml_config    = load_yaml_config()
config_details = load_yaml_config("config_notifications.yaml")


# ======================
# HELPER FUNCTIONS
# ======================
def resource_path(relative_path: str) -> str:
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def set_opencv_window_icon(window_name, ico_path):
    try:
        hwnd = win32gui.FindWindow(None, window_name)
        if hwnd:
            icon_flags = win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE
            hicon      = ctypes.windll.user32.LoadImageW(
                0, ico_path, win32con.IMAGE_ICON, 0, 0, icon_flags
            )
            ctypes.windll.user32.SendMessageW(hwnd, win32con.WM_SETICON, 1, hicon)
            ctypes.windll.user32.SendMessageW(hwnd, win32con.WM_SETICON, 0, hicon)
    except Exception as e:
        print(f"Could not set window icon: {e}")


# ======================
# GLOBAL CONFIGURATION
# ======================
ALARM_WAV_PATH = resource_path(yaml_config['paths']['alarm_wav'])

# Parse ROI configurations
ROIs_DISPLAY          = []
ROI_NAMES             = []
ROI_FOLDER_NAMES      = []
ROI_PERSON_CONFIDENCE = []

for roi_name, roi_config in yaml_config['rois'].items():
    ROIs_DISPLAY.append(tuple(roi_config['coordinates']))
    ROI_FOLDER_NAMES.append(roi_config['folder_name'])

    if roi_name == 'tank_view':
        ROI_NAMES.append('Tank View')
        ROI_PERSON_CONFIDENCE.append(yaml_config['person']['tank_view_confidence'])
    elif roi_name == 'road_view':
        ROI_NAMES.append('Road View')
        ROI_PERSON_CONFIDENCE.append(yaml_config['person']['road_view_confidence'])

MAX_DISPLAY_WIDTH  = yaml_config['display']['max_width']
MAX_DISPLAY_HEIGHT = yaml_config['display']['max_height']

LOG_FILE_PATH = yaml_config['paths']['log_file']
CONFIG_FILE   = yaml_config['paths']['config_file']
COMMAND_FILE  = yaml_config['paths']['command_file']

MONITOR_DURATION = yaml_config['detection']['monitor_duration']
FRAME_SKIP       = yaml_config['detection']['frame_skip']
PPE_FRAME_SKIP   = yaml_config['detection']['ppe_frame_skip']
ROI_EMPTY_TIME   = yaml_config['detection']['roi_empty_time']

VEHICLE_CLASSES = yaml_config['vehicle']['classes']

# Notification configs
message        = config_details["sms"]["message"]
mobile_numbers = config_details["sms"]["Mobile_numbers"]
html_string    = config_details["email"]["message"]
dtTimestamp1   = datetime.now()
smtp_server    = config_details["email"]["smtp_server"]
email_ids      = config_details["email"]["email_ids"]

image_quality = yaml_config['image']['quality']


# ======================
# MAIN CLASS
# ======================
class DetectionCore:
    def __init__(self):
        # Reload YAML config on each init
        global yaml_config
        yaml_config = load_yaml_config()

        self.alarm_player = AlarmPlayer(ALARM_WAV_PATH, cooldown=yaml_config['alarm']['cooldown'])

        self.config = self.load_config()

        # Cooldown settings
        self.VEHICLE_COOLDOWN         = yaml_config['vehicle']['cooldown_seconds']
        self.PERSON_COOLDOWN          = yaml_config['person']['cooldown_minutes'] * 60.0
        self.person_cooldown_enabled  = yaml_config['person']['cooldown_enabled']
        self.vehicle_cooldown_enabled = yaml_config['vehicle']['cooldown_enabled']

        # Override with config file values if present
        if 'vehicle_cooldown_seconds' in self.config:
            self.VEHICLE_COOLDOWN = self.config.get("vehicle_cooldown_seconds", self.VEHICLE_COOLDOWN)
        if 'person_cooldown_minutes' in self.config:
            self.PERSON_COOLDOWN = self.config.get("person_cooldown_minutes", yaml_config['person']['cooldown_minutes']) * 60.0
        if 'person_cooldown_enabled' in self.config:
            self.person_cooldown_enabled = self.config.get("person_cooldown_enabled", self.person_cooldown_enabled)
        if 'vehicle_cooldown_enabled' in self.config:
            self.vehicle_cooldown_enabled = self.config.get("vehicle_cooldown_enabled", self.vehicle_cooldown_enabled)

        # CUDA settings
        torch.backends.cudnn.benchmark = yaml_config['cuda']['benchmark']
        torch.cuda.set_per_process_memory_fraction(yaml_config['cuda']['memory_fraction'])

        # ROI state tracking
        self.ROIs_FOR_PROCESSING = []
        self.roi_state           = {i: "IDLE" for i in range(len(ROIs_DISPLAY))}
        self.roi_last_seen       = {i: 0.0   for i in range(len(ROIs_DISPLAY))}
        self.person_lock         = {i: False  for i in range(len(ROIs_DISPLAY))}
        self.monitor_start_time  = {i: None   for i in range(len(ROIs_DISPLAY))}

        # PPE confidence tracking - stores best score seen per item per ROI
        self.ppe_confidence = {i: {"helmet": 0.0, "vest": 0.0} for i in range(len(ROIs_DISPLAY))}

        # Fixed-size top-3 buffer per ROI
        # Each entry: {"score": float, "frame": annotated_np_array}
        # score    = helmet_conf + vest_conf for that frame
        # Buffer never grows beyond 3 - lowest score evicted when full
        self.best_frames = {i: [] for i in range(len(ROIs_DISPLAY))}

        # Cooldown state
        self.vehicle_last_detected = {i: 0.0 for i in range(len(ROIs_DISPLAY))}
        self.person_cooldown_until = {i: 0.0 for i in range(len(ROIs_DISPLAY))}

        # Command processing
        self.last_command_timestamp = None

        # Load AI models onto GPU
        self.person_model = YOLO(resource_path(yaml_config['paths']['person_model'])).to("cuda")
        self.ppe_model    = YOLO(resource_path(yaml_config['paths']['ppe_model'])).to("cuda")

        # Threading
        self.frame_queue        = queue.Queue(maxsize=5)
        self.stop_event         = threading.Event()
        self.capture_thread_obj = None
        self.cap                = None

        # FIX 2: Fixed thread pool for notifications — max 2 workers at any time
        # Replaces bare threading.Thread which could accumulate indefinitely
        # on slow SMTP or network issues. Same behaviour, bounded resource usage.
        self.notification_executor = ThreadPoolExecutor(max_workers=2)

        # Display control
        self.show_display       = False
        self.cv2_window_created = False
        self.display_lock       = threading.Lock()

    # ------------------------------------------------------------------
    def load_config(self):
        """Load configuration from JSON file"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {
            "video_path":               "",
            "person_cooldown_enabled":  yaml_config['person']['cooldown_enabled'],
            "person_cooldown_minutes":  yaml_config['person']['cooldown_minutes'],
            "vehicle_cooldown_enabled": yaml_config['vehicle']['cooldown_enabled'],
            "vehicle_cooldown_seconds": yaml_config['vehicle']['cooldown_seconds']
        }

    # ------------------------------------------------------------------
    def capture_thread(self):
        """Capture frames from video source and push to queue"""
        VIDEO_PATH = self.config.get("video_path", "")

        if not VIDEO_PATH:
            print("No video path configured!")
            return

        print(f"Using video path: {VIDEO_PATH}")

        self.cap = cv2.VideoCapture(VIDEO_PATH)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  yaml_config['video']['width'])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, yaml_config['video']['height'])

        while not self.stop_event.is_set():
            ret, frame = self.cap.read()
            if not ret:
                break
            if not self.frame_queue.full():
                self.frame_queue.put(frame)

        self.cap.release()
        self.stop_event.set()

    # ------------------------------------------------------------------
    def toggle_display(self, show):
        """Show or hide the OpenCV display window"""
        with self.display_lock:
            self.show_display = show
            if not show and self.cv2_window_created:
                cv2.destroyWindow("Output")
                self.cv2_window_created = False
                print("Display window hidden")
            elif show:
                print("Display window will be shown")

    # ------------------------------------------------------------------
    def process_commands(self):
        """Read and act on commands written by the control panel"""
        if not os.path.exists(COMMAND_FILE):
            return

        try:
            with open(COMMAND_FILE, 'r') as f:
                command = json.load(f)

            timestamp = command.get("timestamp")
            if timestamp == self.last_command_timestamp:
                return

            self.last_command_timestamp = timestamp
            action = command.get("action")

            if action == "set_person_cooldown_enabled":
                self.person_cooldown_enabled = command.get("enabled", True)
                print(f"Person cooldown {'enabled' if self.person_cooldown_enabled else 'disabled'}")

            elif action == "set_person_cooldown_time":
                minutes = command.get("minutes", 30)
                self.PERSON_COOLDOWN = minutes * 60.0
                print(f"Person cooldown time set to {minutes} minutes")

            elif action == "set_vehicle_cooldown_enabled":
                self.vehicle_cooldown_enabled = command.get("enabled", True)
                print(f"Vehicle cooldown {'enabled' if self.vehicle_cooldown_enabled else 'disabled'}")

            elif action == "set_vehicle_cooldown_time":
                self.VEHICLE_COOLDOWN = command.get("seconds", 10)
                print(f"Vehicle cooldown time set to {self.VEHICLE_COOLDOWN} seconds")

            elif action == "reset_person_cooldown":
                roi_index = command.get("roi_index", 0)
                if self.roi_state[roi_index] == "COOLDOWN":
                    self.roi_state[roi_index]          = "IDLE"
                    self.person_cooldown_until[roi_index] = 0.0
                    print(f"{ROI_NAMES[roi_index]} person cooldown reset")

            elif action == "reset_vehicle_cooldown":
                roi_index = command.get("roi_index", 0)
                self.vehicle_last_detected[roi_index] = 0.0
                print(f"{ROI_NAMES[roi_index]} vehicle cooldown reset")

            elif action == "reset_all_cooldowns":
                for i in range(len(ROIs_DISPLAY)):
                    if self.roi_state[i] == "COOLDOWN":
                        self.roi_state[i] = "IDLE"
                    self.person_cooldown_until[i]  = 0.0
                    self.vehicle_last_detected[i]  = 0.0
                print("All cooldowns reset for all ROIs")

            elif action == "stop_alarm":
                self.alarm_player.stop()
                print("Alarm stopped by user")

            elif action == "toggle_display":
                self.toggle_display(command.get("show", False))

            elif action == "stop_detection":
                self.stop_event.set()
                print("Detection stopped by user")

        except Exception as e:
            print(f"Error processing command: {e}")

    # ------------------------------------------------------------------
    def resize_to_screen(self, img):
        """Resize image to fit within max display dimensions"""
        h, w  = img.shape[:2]
        scale = min(MAX_DISPLAY_WIDTH / w, MAX_DISPLAY_HEIGHT / h)
        if scale < 1:
            return cv2.resize(img, (int(w * scale), int(h * scale))), scale
        return img, 1.0

    # ------------------------------------------------------------------
    def draw_timestamp(self, img):
        """Draw current timestamp on bottom-left of image"""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(img, ts, (20, img.shape[0] - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

    # ------------------------------------------------------------------
    def get_today_roi_dir(self, roi_index):
        """Get (and create) the save directory for today's detections"""
        today = datetime.now().strftime("%Y-%m-%d")
        path  = os.path.join("detections", today, ROI_FOLDER_NAMES[roi_index])
        os.makedirs(path, exist_ok=True)
        return path

    # ------------------------------------------------------------------
    def person_overlaps_roi(self, px1, py1, px2, py2, rx1, ry1, rx2, ry2):
        """Return True if person bounding box overlaps with ROI rectangle"""
        return not (px2 < rx1 or px1 > rx2 or py2 < ry1 or py1 > ry2)

    # ------------------------------------------------------------------
    def update_ppe_buffer(self, roi_index, score, annotated_frame):
        """
        Maintain a fixed-size buffer of top 3 best PPE frames per ROI.

        Rules:
          - Buffer max size = 3
          - If buffer has space  → add new frame, re-sort best → worst
          - If buffer is full    → compare new score with worst (index -1)
              better  → evict worst, insert new, re-sort
              worse   → discard new frame immediately
          - Result: buffer always holds the 3 highest-scoring frames seen so far
          - Memory stays bounded — no unbounded growth
        """
        buffer = self.best_frames[roi_index]

        if len(buffer) < 3:
            buffer.append({"score": score, "frame": annotated_frame})
            buffer.sort(key=lambda x: x["score"], reverse=True)
        elif score > buffer[-1]["score"]:
            buffer[-1] = {"score": score, "frame": annotated_frame}
            buffer.sort(key=lambda x: x["score"], reverse=True)
        # else: discard — new frame score not good enough

        self.best_frames[roi_index] = buffer
    
    # ------------------------------------------------------------------
    def detect_and_save_vehicle(self, frame, roi_index, roi_coords):
        """
        Run vehicle detection INSIDE the ROI crop only.
        Saves an annotated image if a vehicle is found and cooldown has elapsed.
        """
        current_time = time.time()

        # Skip if ROI is in person cooldown
        if self.person_cooldown_enabled and self.roi_state[roi_index] == "COOLDOWN":
            return

        # Skip if vehicle cooldown has not elapsed
        if self.vehicle_cooldown_enabled and (current_time - self.vehicle_last_detected[roi_index] < self.VEHICLE_COOLDOWN):
            return

        rx1, ry1, rx2, ry2 = roi_coords
        roi_img             = frame[ry1:ry2, rx1:rx2]

        vehicle_results = self.person_model.predict(
            roi_img,
            imgsz=yaml_config['model']['vehicle_detection']['imgsz'],
            conf=yaml_config['model']['vehicle_detection']['conf'],
            device=0, half=False, verbose=False
        )[0]

        vehicle_detected = any(
            vehicle_results.names[int(box.cls[0])] in VEHICLE_CLASSES
            for box in vehicle_results.boxes
        )

        if vehicle_detected:
            print(f"Vehicle detected in {ROI_NAMES[roi_index]}")
            self.vehicle_last_detected[roi_index] = current_time

            save_dir = self.get_today_roi_dir(roi_index)
            ts       = datetime.now().strftime("%H-%M-%S")
            img      = frame.copy()
            self.draw_timestamp(img)

            for box in vehicle_results.boxes:
                class_name = vehicle_results.names[int(box.cls[0])]
                if class_name in VEHICLE_CLASSES:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    conf            = float(box.conf[0])
                    full_x1         = x1 + rx1
                    full_y1         = y1 + ry1
                    full_x2         = x2 + rx1
                    full_y2         = y2 + ry1
                    cv2.rectangle(img, (full_x1, full_y1), (full_x2, full_y2), (255, 165, 0), 2)
                    cv2.putText(img, f"Vehicle {conf:.2f}",
                                (full_x1, full_y1 - 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 165, 0), 2)

            cv2.imwrite(
                os.path.join(save_dir, f"{ts}_VEHICLE_DETECTED.jpg"),
                img, [cv2.IMWRITE_JPEG_QUALITY, image_quality]
            )
            print(f"Vehicle image saved for {ROI_NAMES[roi_index]}")

    # ------------------------------------------------------------------
    def finalize_person(self, roi):
        """
        Called when MONITOR_DURATION has elapsed for a ROI.

        Save behaviour by status:
        ┌──────────────────┬──────────────────────────────────────────────────┐
        │ FULLY_COMPLIANT  │ Skip saving violation frames entirely            │
        │ PARTIAL_PPE      │ Save up to 3 frames as HH-MM-SS_partial_ppe_N    │
        │ NO_PPE           │ Save up to 3 frames as HH-MM-SS_no_ppe_N         │
        └──────────────────┴──────────────────────────────────────────────────┘

        Frames already have:
          - Coloured PPE boxes drawn (blue = helmet, yellow = vest)
          - Red person box drawn
        Buffer already holds best 3 — no re-inference needed, just save.
        """
        helmet = self.ppe_confidence[roi]["helmet"] > yaml_config['ppe']['helmet_confidence']
        vest   = self.ppe_confidence[roi]["vest"]   > yaml_config['ppe']['vest_confidence']

        status = (
            "FULLY_COMPLIANT" if helmet and vest else
            "PARTIAL_PPE"     if helmet or vest  else
            "NO_PPE"
        )

        # Log result
        log_dir = os.path.dirname(LOG_FILE_PATH)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        with open(LOG_FILE_PATH, "a") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "roi":       ROI_NAMES[roi],
                "status":    status,
                **self.ppe_confidence[roi]
            }, f)
            f.write("\n")

        save_dir = self.get_today_roi_dir(roi)
        ts       = datetime.now().strftime("%H-%M-%S")

        if status == "FULLY_COMPLIANT":
            # helmet + vest both present — no violation images needed
            print(f"{ROI_NAMES[roi]} FULLY COMPLIANT - no violation images saved")

        elif status == "PARTIAL_PPE":
            # only helmet OR vest — save violation frames
            for idx, entry in enumerate(self.best_frames[roi], start=1):
                img = entry["frame"].copy()
                self.draw_timestamp(img)
                cv2.imwrite(
                    os.path.join(save_dir, f"{ts}_partial_ppe_{idx}.jpg"),
                    img, [cv2.IMWRITE_JPEG_QUALITY, image_quality]
                )
            print(f"{ROI_NAMES[roi]} PARTIAL PPE - {len(self.best_frames[roi])} violation image(s) saved")

        elif status == "NO_PPE":
            # neither helmet nor vest — save violation frames
            for idx, entry in enumerate(self.best_frames[roi], start=1):
                img = entry["frame"].copy()
                self.draw_timestamp(img)
                cv2.imwrite(
                    os.path.join(save_dir, f"{ts}_no_ppe_{idx}.jpg"),
                    img, [cv2.IMWRITE_JPEG_QUALITY, image_quality]
                )
            print(f"{ROI_NAMES[roi]} NO PPE - {len(self.best_frames[roi])} violation image(s) saved")

        # Transition ROI state
        if self.person_cooldown_enabled:
            self.roi_state[roi]             = "COOLDOWN"
            self.person_cooldown_until[roi] = time.time() + self.PERSON_COOLDOWN
            print(f"{ROI_NAMES[roi]} entering {int(self.PERSON_COOLDOWN / 60)}-minute cooldown")
        else:
            self.roi_state[roi] = "OCCUPIED"
            print(f"{ROI_NAMES[roi]} cooldown disabled, moving to OCCUPIED")

        # Reset all per-ROI tracking state
        self.person_lock[roi]        = False
        self.monitor_start_time[roi] = None
        self.ppe_confidence[roi]     = {"helmet": 0.0, "vest": 0.0}
        self.best_frames[roi]        = []

        self.alarm_player.clear_roi(roi)

    # ------------------------------------------------------------------
    def start(self):
        """Main entry point - starts capture thread and runs the processing loop"""
        self.config = self.load_config()

        self.capture_thread_obj = threading.Thread(target=self.capture_thread, daemon=True)
        self.capture_thread_obj.start()

        # Wait for first frame
        while self.frame_queue.empty():
            if self.stop_event.is_set():
                return
            time.sleep(0.01)

        # Use first frame to compute display-to-processing scale
        frame = self.frame_queue.get()
        h, w  = frame.shape[:2]
        scale = min(MAX_DISPLAY_WIDTH / w, MAX_DISPLAY_HEIGHT / h)

        for x1, y1, x2, y2 in ROIs_DISPLAY:
            self.ROIs_FOR_PROCESSING.append((
                int(x1 / scale), int(y1 / scale),
                int(x2 / scale), int(y2 / scale)
            ))

        frame_id              = 0
        command_check_counter = 0

        print("Detection started - processing frames...")

        while not self.stop_event.is_set():
            if self.frame_queue.empty():
                time.sleep(0.001)
                continue

            frame = self.frame_queue.get()
            frame_id += 1

            # Check for control panel commands every 30 frames
            command_check_counter += 1
            if command_check_counter >= 30:
                self.process_commands()
                command_check_counter = 0

            run_person = frame_id % FRAME_SKIP     == 0
            run_ppe    = frame_id % PPE_FRAME_SKIP == 0

            current_time = time.time()

            # Check if any ROI cooldown has expired
            for i in range(len(ROIs_DISPLAY)):
                if self.roi_state[i] == "COOLDOWN" and current_time >= self.person_cooldown_until[i]:
                    self.roi_state[i] = "IDLE"
                    print(f"{ROI_NAMES[i]} cooldown ended, back to IDLE")

            # ----------------------------------------------------------
            # PERSON DETECTION
            # Model runs ONLY on ROI crop — never on full frame
            # ----------------------------------------------------------
            if run_person:
                for i, (rx1, ry1, rx2, ry2) in enumerate(self.ROIs_FOR_PROCESSING):

                    # Skip ROI entirely if in cooldown
                    if self.person_cooldown_enabled and self.roi_state[i] == "COOLDOWN":
                        continue

                    # Crop to ROI only
                    roi_crop = frame[ry1:ry2, rx1:rx2]

                    person_results = self.person_model.predict(
                        roi_crop,
                        imgsz=yaml_config['model']['person_detection']['imgsz'],
                        conf=yaml_config['model']['person_detection']['conf'],
                        device=0, half=False, verbose=False
                    )[0]

                    for box in person_results.boxes:
                        if person_results.names[int(box.cls[0])] != "person":
                            continue

                        person_conf = float(box.conf[0])

                        if person_conf < ROI_PERSON_CONFIDENCE[i]:
                            continue

                        self.roi_last_seen[i] = time.time()

                        # Convert ROI-space coords to full-frame coords
                        bx1, by1, bx2, by2 = map(int, box.xyxy[0])
                        fx1 = bx1 + rx1
                        fy1 = by1 + ry1
                        fx2 = bx2 + rx1
                        fy2 = by2 + ry1

                        # Draw GREEN box on display frame — person detected, PPE unknown
                        cv2.rectangle(frame, (fx1, fy1), (fx2, fy2), (0, 255, 0), 2)
                        cv2.putText(frame, f"person {person_conf:.2f}",
                                    (fx1, fy1 - 5),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

                        # Trigger monitoring only if ROI was IDLE
                        if self.roi_state[i] == "IDLE":
                            self.roi_state[i]          = "MONITORING"
                            self.person_lock[i]        = True
                            self.monitor_start_time[i] = time.time()

                            self.alarm_player.play_alarm(roi_index=i)

                            # Save first-detection image with green box
                            img       = frame.copy()
                            self.draw_timestamp(img)
                            filename  = f"{datetime.now().strftime('%H-%M-%S')}_PERSON_DETECTED.jpg"
                            save_path = os.path.join(self.get_today_roi_dir(i), filename)
                            cv2.imwrite(save_path, img, [cv2.IMWRITE_JPEG_QUALITY, image_quality])

                            # FIX 2: Submit notifications via bounded thread pool
                            # Max 2 workers — prevents thread accumulation on slow SMTP/network
                            # Behaviour identical to before — runs in background, non-blocking
                            if i == 0 :
                                # Tank view notification only 
                                if os.path.exists(save_path):
                                    self.notification_executor.submit(
                                        email_coke,
                                        html_string, smtp_server, email_ids,
                                        dtTimestamp1.strftime("%d-%b-%y"), save_path
                                    )

                                self.notification_executor.submit(
                                    send_sms,
                                    message, mobile_numbers
                                )

                            print(f"Person detected in {ROI_NAMES[i]} (conf: {person_conf:.2f}) - Alarm triggered")

                # Vehicle detection for all ROIs
                for i, roi_coords in enumerate(self.ROIs_FOR_PROCESSING):
                    self.detect_and_save_vehicle(frame, i, roi_coords)

            # ----------------------------------------------------------
            # PPE DETECTION
            # Model runs ONLY on MONITORING ROI crops — never on full frame
            #
            # FIX 1 — Two-pass approach to eliminate frame.copy() churn:
            #
            #   PASS 1: Run PPE model, collect scores only — NO frame copy yet
            #           Compute frame_score = helmet_conf + vest_conf
            #           For NO_PPE frames (no detection): score = 0.01
            #           so they can still enter an empty buffer
            #
            #   CHECK:  Is this frame worth storing?
            #           len(buffer) < 3  → yes, buffer not full yet
            #           score > buffer worst → yes, better than what we have
            #           otherwise → skip copy entirely, skip person model call
            #
            #   PASS 2: Only if frame passed the check:
            #           frame.copy() — copy once, only when needed
            #           Draw PPE boxes on copy
            #           Run person model on same roi_img crop — fresh coords
            #           (person is moving so we need current position)
            #           Draw RED person box on copy
            #           Push to buffer
            #
            # Result: frame.copy() fires only for frames that enter the buffer
            #         person model in PPE block fires only for those same frames
            #         frames with score too low are discarded with zero allocation
            # ----------------------------------------------------------
            if run_ppe:
                for i in range(len(self.ROIs_FOR_PROCESSING)):
                    if self.roi_state[i] != "MONITORING":
                        continue

                    elapsed = time.time() - self.monitor_start_time[i]

                    if elapsed <= MONITOR_DURATION:
                        x1, y1, x2, y2 = self.ROIs_FOR_PROCESSING[i]
                        roi_img         = frame[y1:y2, x1:x2]

                        ppe_res = self.ppe_model.predict(
                            roi_img,
                            imgsz=yaml_config['model']['ppe_detection']['imgsz'],
                            conf=yaml_config['model']['ppe_detection']['conf'],
                            device=0, half=False, verbose=False
                        )[0]

                        # -------------------------------------------
                        # PASS 1: scores only — no copy, no drawing
                        # -------------------------------------------
                        frame_helmet_conf = 0.0
                        frame_vest_conf   = 0.0
                        has_detection     = False

                        for b in ppe_res.boxes:
                            name = ppe_res.names[int(b.cls[0])]
                            if name not in ["helmet", "vest"]:
                                continue
                            conf          = float(b.conf[0])
                            has_detection = True

                            # Update global best confidence per PPE item
                            self.ppe_confidence[i][name] = max(self.ppe_confidence[i][name], conf)

                            if name == "helmet":
                                frame_helmet_conf = max(frame_helmet_conf, conf)
                            else:
                                frame_vest_conf = max(frame_vest_conf, conf)

                        # NO_PPE frames get score 0.01 so they can enter an empty buffer
                        # this ensures violation images are always available for NO_PPE case
                        frame_score = frame_helmet_conf + frame_vest_conf if has_detection else 0.01

                        # -------------------------------------------
                        # CHECK: is this frame worth storing?
                        # -------------------------------------------
                        buffer      = self.best_frames[i]
                        worth_storing = len(buffer) < 3 or frame_score > buffer[-1]["score"]

                        if worth_storing:
                            # -------------------------------------------
                            # PASS 2: copy + draw — only when needed
                            # -------------------------------------------
                            annotated = frame.copy()

                            # Draw PPE boxes (coloured by class)
                            for b in ppe_res.boxes:
                                name = ppe_res.names[int(b.cls[0])]
                                if name not in ["helmet", "vest"]:
                                    continue
                                conf            = float(b.conf[0])
                                bx1, by1, bx2, by2 = map(int, b.xyxy[0])
                                bx1 += x1;  bx2 += x1
                                by1 += y1;  by2 += y1
                                color = (255, 0, 0) if name == "helmet" else (0, 255, 255)
                                cv2.rectangle(annotated, (bx1, by1), (bx2, by2), color, 2)
                                cv2.putText(annotated, f"{name} {conf:.2f}",
                                            (bx1, by1 - 5),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

                            # Run person model on same roi_img — fresh coords for moving person
                            # This is intentional: person moves between frames so we cannot
                            # reuse a box from a previous FRAME_SKIP run — it would be stale
                            person_ppe = self.person_model.predict(
                                roi_img,
                                imgsz=yaml_config['model']['person_detection']['imgsz'],
                                conf=yaml_config['model']['person_detection']['conf'],
                                device=0, half=False, verbose=False
                            )[0]

                            for pb in person_ppe.boxes:
                                if person_ppe.names[int(pb.cls[0])] != "person":
                                    continue
                                px1, py1, px2, py2 = map(int, pb.xyxy[0])
                                px1 += x1;  px2 += x1
                                py1 += y1;  py2 += y1
                                # RED box — person box on violation frame
                                cv2.rectangle(annotated, (px1, py1), (px2, py2), (0, 0, 255), 2)

                            self.update_ppe_buffer(i, frame_score, annotated)

                        # else: score too low — skip copy, skip person model, skip buffer
                        # zero allocation, zero model call for this frame

                    else:
                        # Monitoring window elapsed — finalize, log and save
                        self.finalize_person(i)

            # ----------------------------------------------------------
            # OCCUPIED to IDLE transition (when cooldown is disabled)
            # ----------------------------------------------------------
            for i in range(len(ROIs_DISPLAY)):
                if self.roi_state[i] == "OCCUPIED":
                    if time.time() - self.roi_last_seen[i] > ROI_EMPTY_TIME:
                        self.roi_state[i] = "IDLE"

            # ----------------------------------------------------------
            # DISPLAY
            # ----------------------------------------------------------
            with self.display_lock:
                if self.show_display:
                    if not self.cv2_window_created:
                        cv2.namedWindow("Output", cv2.WINDOW_NORMAL)
                        self.cv2_window_created = True
                        time.sleep(0.3)
                        set_opencv_window_icon("Output", resource_path("output.ico"))

                    disp, sc = self.resize_to_screen(frame)

                    for i, (x1, y1, x2, y2) in enumerate(self.ROIs_FOR_PROCESSING):
                        color = (
                            (0, 255, 0)     if self.roi_state[i] == "IDLE"       else
                            (0, 0, 255)     if self.roi_state[i] == "MONITORING" else
                            (255, 0, 255)   if self.roi_state[i] == "COOLDOWN"   else
                            (128, 128, 128)
                        )

                        cv2.rectangle(
                            disp,
                            (int(x1 * sc), int(y1 * sc)),
                            (int(x2 * sc), int(y2 * sc)),
                            color, 2
                        )
                        cv2.putText(
                            disp, ROI_NAMES[i],
                            (int(x1 * sc), int(y1 * sc) - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2
                        )

                        if self.roi_state[i] == "COOLDOWN":
                            remaining = int(self.person_cooldown_until[i] - time.time())
                            minutes   = remaining // 60
                            seconds   = remaining % 60
                            cv2.putText(
                                disp,
                                f"Repeat Detection Disabled: {minutes}m {seconds}s",
                                (int(x1 * sc) + 150, int(y1 * sc) - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2
                            )

                    cv2.imshow("Output", disp)
                    if cv2.waitKey(1) & 0xFF == 27:
                        self.stop_event.set()
                        break
                else:
                    cv2.waitKey(1)

        # Clean shutdown
        if self.cv2_window_created:
            try:
                cv2.destroyAllWindows()
                cv2.waitKey(1)
            except Exception as e:
                print(f"Error destroying windows: {e}")

        print("Detection stopped")

    # ------------------------------------------------------------------
    def stop(self):
        """Gracefully stop the detection system"""
        print("Stopping detection system...")
        self.stop_event.set()

        # FIX 2: Shut down notification thread pool cleanly
        # wait=False — don't block stop() waiting for pending emails/SMS
        self.notification_executor.shutdown(wait=False)

        if self.alarm_player:
            try:
                self.alarm_player.stop()
            except Exception as e:
                print(f"Error stopping alarm: {e}")

        if self.cap:
            try:
                self.cap.release()
            except Exception as e:
                print(f"Error releasing capture: {e}")
            
        print("Detection system stopped")
