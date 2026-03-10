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
from alarm_v2_v1 import AlarmPlayer
import yaml
import ctypes
import win32gui
import win32con
# REMOVED: email/SMS imports
# from dotenv import load_dotenv
# from twilio.rest import Client
# from notification_logic import send_email, send_sms
# load_dotenv()
# SUPPRESION OD ERROR LOGS
os.environ['OPENCV_FFMPEG_LOGLEVEL'] = 'quiet'  # Complete FFmpeg silence
os.environ['OPENCV_LOG_LEVEL'] = 'SILENT'      # Complete OpenCV silence
cv2.setLogLevel(-1)  # Maximum suppression
# ======================
# YAML CONFIGURATION LOADER - FIXED FOR PYINSTALLER
# ======================
def load_yaml_config(yaml_path="detection_core.yaml"):
    """Load configuration from YAML file - PyInstaller compatible"""
    import sys
    import os
    
    # Determine the correct path based on whether we're frozen or not
    if getattr(sys, 'frozen', False):
        # Running as compiled executable - check next to .exe first
        exe_dir = os.path.dirname(sys.executable)
        yaml_full_path = os.path.join(exe_dir, yaml_path)
        
        # If not found next to exe, try _MEIPASS (bundled resources)
        if not os.path.exists(yaml_full_path):
            application_path = sys._MEIPASS
            yaml_full_path = os.path.join(application_path, yaml_path)
    else:
        # Running as normal Python script - use current directory
        application_path = os.path.dirname(os.path.abspath(__file__))
        yaml_full_path = os.path.join(application_path, yaml_path)
    
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

# Load YAML configuration
yaml_config = load_yaml_config()

# ======================   
# CONFIGURATION FROM YAML                        
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
            hicon = ctypes.windll.user32.LoadImageW(
                0, ico_path, win32con.IMAGE_ICON, 0, 0, icon_flags
            )
            ctypes.windll.user32.SendMessageW(hwnd, win32con.WM_SETICON, 1, hicon)
            ctypes.windll.user32.SendMessageW(hwnd, win32con.WM_SETICON, 0, hicon)
    except Exception as e:
        print(f"Could not set window icon: {e}")

ALARM_WAV_PATH = resource_path(yaml_config['paths']['alarm_wav'])

# Parse ROI configurations from new structure
ROIs_DISPLAY = []
ROI_NAMES = []
ROI_FOLDER_NAMES = []
ROI_PERSON_CONFIDENCE = []

for roi_name, roi_config in yaml_config['rois'].items():
    ROIs_DISPLAY.append(tuple(roi_config['coordinates']))
    ROI_FOLDER_NAMES.append(roi_config['folder_name'])
    
    # Set ROI display names
    if roi_name == 'tank_view':
        ROI_NAMES.append('Tank View')
        ROI_PERSON_CONFIDENCE.append(yaml_config['person']['tank_view_confidence'])
    elif roi_name == 'road_view':
        ROI_NAMES.append('Road View')
        ROI_PERSON_CONFIDENCE.append(yaml_config['person']['road_view_confidence'])

MAX_DISPLAY_WIDTH = yaml_config['display']['max_width']
MAX_DISPLAY_HEIGHT = yaml_config['display']['max_height']

LOG_FILE_PATH = yaml_config['paths']['log_file']
CONFIG_FILE = yaml_config['paths']['config_file']
COMMAND_FILE = yaml_config['paths']['command_file']

MONITOR_DURATION = yaml_config['detection']['monitor_duration']
FRAME_SKIP = yaml_config['detection']['frame_skip']
PPE_FRAME_SKIP = yaml_config['detection']['ppe_frame_skip']

ROI_EMPTY_TIME = yaml_config['detection']['roi_empty_time']

# Vehicle Detection Configuration
VEHICLE_CLASSES = yaml_config['vehicle']['classes']

# ================
# IMAGE QUALITY   
# ================
image_quality = yaml_config['image']['quality']

class DetectionCore:
    def __init__(self):
        # RELOAD YAML CONFIG ON EACH INIT - allows runtime updates
        global yaml_config
        yaml_config = load_yaml_config()
        
        self.alarm_player = AlarmPlayer(ALARM_WAV_PATH, cooldown=yaml_config['alarm']['cooldown'])
        
        # Load configuration
        self.config = self.load_config()
        
        # Cooldown settings from YAML
        self.VEHICLE_COOLDOWN = yaml_config['vehicle']['cooldown_seconds']
        self.PERSON_COOLDOWN = yaml_config['person']['cooldown_minutes'] * 60.0
        self.person_cooldown_enabled = yaml_config['person']['cooldown_enabled']
        self.vehicle_cooldown_enabled = yaml_config['vehicle']['cooldown_enabled']
        
        # Override with config file if exists
        if 'vehicle_cooldown_seconds' in self.config:
            self.VEHICLE_COOLDOWN = self.config.get("vehicle_cooldown_seconds", self.VEHICLE_COOLDOWN)
        if 'person_cooldown_minutes' in self.config:
            self.PERSON_COOLDOWN = self.config.get("person_cooldown_minutes", yaml_config['person']['cooldown_minutes']) * 60.0
        if 'person_cooldown_enabled' in self.config:
            self.person_cooldown_enabled = self.config.get("person_cooldown_enabled", self.person_cooldown_enabled)
        if 'vehicle_cooldown_enabled' in self.config:
            self.vehicle_cooldown_enabled = self.config.get("vehicle_cooldown_enabled", self.vehicle_cooldown_enabled)
        
        # CUDA SAFETY
        torch.backends.cudnn.benchmark = yaml_config['cuda']['benchmark']
        torch.cuda.set_per_process_memory_fraction(yaml_config['cuda']['memory_fraction'])
        
        # STATE
        self.ROIs_FOR_PROCESSING = []
        self.roi_state = {i: "IDLE" for i in range(len(ROIs_DISPLAY))}
        self.roi_last_seen = {i: 0.0 for i in range(len(ROIs_DISPLAY))}
        self.person_lock = {i: False for i in range(len(ROIs_DISPLAY))}
        self.monitor_start_time = {i: None for i in range(len(ROIs_DISPLAY))}
        self.ppe_confidence = {
            i: {"helmet": 0.0, "vest": 0.0}
            for i in range(len(ROIs_DISPLAY))
        }
        self.best_frames = {i: [] for i in range(len(ROIs_DISPLAY))}
        
        # Cooldown State
        self.vehicle_last_detected = {i: 0.0 for i in range(len(ROIs_DISPLAY))}
        self.person_cooldown_until = {i: 0.0 for i in range(len(ROIs_DISPLAY))}
        
        # Command processing
        self.last_command_timestamp = None
        
        # MODELS
        self.person_model = YOLO(resource_path(yaml_config['paths']['person_model'])).to("cuda")
        self.ppe_model = YOLO(resource_path(yaml_config['paths']['ppe_model'])).to("cuda")
        
        # THREADING
        self.frame_queue = queue.Queue(maxsize=5)
        self.stop_event = threading.Event()
        self.capture_thread_obj = None
        self.cap = None
        
        # Display control
        self.show_display = False
        self.cv2_window_created = False
        self.display_lock = threading.Lock()
    
    def load_config(self):
        """Load configuration from file"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {
            "video_path": "",
            "person_cooldown_enabled": yaml_config['person']['cooldown_enabled'],
            "person_cooldown_minutes": yaml_config['person']['cooldown_minutes'],
            "vehicle_cooldown_enabled": yaml_config['vehicle']['cooldown_enabled'],
            "vehicle_cooldown_seconds": yaml_config['vehicle']['cooldown_seconds']
        }
    
    def capture_thread(self):
        """Capture frames from video source"""
        VIDEO_PATH = self.config.get("video_path", "")
        
        if not VIDEO_PATH:
            print("No video path configured!")
            return
        
        print(f"Using video path: {VIDEO_PATH}")
        
        self.cap = cv2.VideoCapture(VIDEO_PATH)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, yaml_config['video']['width'])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, yaml_config['video']['height'])

        while not self.stop_event.is_set():
            ret, frame = self.cap.read()
            if not ret:
                break
            if not self.frame_queue.full():
                self.frame_queue.put(frame)

        self.cap.release()
        self.stop_event.set()
    
    def toggle_display(self, show):
        """Toggle display window visibility"""
        with self.display_lock:
            self.show_display = show
            if not show and self.cv2_window_created:
                cv2.destroyWindow("Output")
                self.cv2_window_created = False
                print("Display window hidden")
            elif show:
                print("Display window will be shown")
    
    def process_commands(self):
        """Process commands from control panel"""
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
                    self.roi_state[roi_index] = "IDLE"
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
                    self.person_cooldown_until[i] = 0.0
                    self.vehicle_last_detected[i] = 0.0
                print("All cooldowns reset for all ROIs")
            
            elif action == "stop_alarm":
                self.alarm_player.stop()
                print("Alarm stopped by user")
            
            elif action == "toggle_display":
                show = command.get("show", False)
                self.toggle_display(show)
            
            elif action == "stop_detection":
                self.stop_event.set()
                print("Detection stopped by user")
        
        except Exception as e:
            print(f"Error processing command: {e}")
    
    def resize_to_screen(self, img):
        """Resize image to fit screen"""
        h, w = img.shape[:2]
        scale = min(MAX_DISPLAY_WIDTH / w, MAX_DISPLAY_HEIGHT / h)
        if scale < 1:
            return cv2.resize(img, (int(w * scale), int(h * scale))), scale
        return img, 1.0
    
    def draw_timestamp(self, img):
        """Draw timestamp on image"""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(img, ts, (20, img.shape[0] - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    
    def get_today_roi_dir(self, roi_index):
        """Get directory for today's ROI detections"""
        today = datetime.now().strftime("%Y-%m-%d")
        path = os.path.join("detections", today, ROI_FOLDER_NAMES[roi_index])
        os.makedirs(path, exist_ok=True)
        return path
    
    def draw_person_boxes(self, frame, results, cooldown_rois):
        """Draw person detection boxes - ONLY for ROIs not in cooldown"""
        for box in results.boxes:
            if results.names[int(box.cls[0])] != "person":
                continue
            
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            conf = float(box.conf[0])
            
            # Check if person overlaps with any cooldown ROI
            should_skip = False
            for i in cooldown_rois:
                rx1, ry1, rx2, ry2 = self.ROIs_FOR_PROCESSING[i]
                if self.person_overlaps_roi(x1, y1, x2, y2, rx1, ry1, rx2, ry2):
                    should_skip = True
                    break
            
            # Only draw if not in any cooldown ROI
            if not should_skip:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, f"person {conf:.2f}",
                            (x1, y1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    
    def person_overlaps_roi(self, px1, py1, px2, py2, rx1, ry1, rx2, ry2):
        """Check if person bounding box overlaps with ROI"""
        return not (px2 < rx1 or px1 > rx2 or py2 < ry1 or py1 > ry2)
    
    def detect_and_save_vehicle(self, frame, roi_index, roi_coords):
        """Detect vehicles in ROI and save image if cooldown elapsed"""
        current_time = time.time()
        
        # Skip vehicle detection if ROI is in person cooldown
        if self.person_cooldown_enabled and self.roi_state[roi_index] == "COOLDOWN":
            return
        
        if self.vehicle_cooldown_enabled and (current_time - self.vehicle_last_detected[roi_index] < self.VEHICLE_COOLDOWN):
            return
        
        rx1, ry1, rx2, ry2 = roi_coords
        roi_img = frame[ry1:ry2, rx1:rx2]
        
        vehicle_results = self.person_model.predict(
            roi_img, 
            imgsz=yaml_config['model']['vehicle_detection']['imgsz'], 
            conf=yaml_config['model']['vehicle_detection']['conf'],
            device=0, half=False, verbose=False
        )[0]
        
        vehicle_detected = False
        for box in vehicle_results.boxes:
            class_name = vehicle_results.names[int(box.cls[0])]
            if class_name in VEHICLE_CLASSES:
                vehicle_detected = True
                break
        
        if vehicle_detected:
            print(f"Vehicle detected: {vehicle_detected}, {ROI_NAMES[roi_index]}")
            self.vehicle_last_detected[roi_index] = current_time
            
            save_dir = self.get_today_roi_dir(roi_index)
            ts = datetime.now().strftime("%H-%M-%S")
            
            img = frame.copy()
            self.draw_timestamp(img)

            # Draw boxes on the ROI portion of the image
            for box in vehicle_results.boxes:
                class_name = vehicle_results.names[int(box.cls[0])]
                if class_name in VEHICLE_CLASSES:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])  # These are ROI coordinates
                    conf = float(box.conf[0])
                    
                    # Convert to full frame coordinates for drawing
                    full_x1 = x1 + rx1
                    full_x2 = x2 + rx1
                    full_y1 = y1 + ry1
                    full_y2 = y2 + ry1
                    
                    cv2.rectangle(img, (full_x1, full_y1), (full_x2, full_y2), (255, 165, 0), 2)
                    cv2.putText(img, f"Vehicle {conf:.2f}",
                            (full_x1, full_y1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 165, 0), 2)
                        
            cv2.imwrite(
                os.path.join(save_dir, f"{ts}_VEHICLE_DETECTED.jpg"),
                img, [cv2.IMWRITE_JPEG_QUALITY, image_quality]       
            )
            print(f"Vehicle detected and saved in {ROI_NAMES[roi_index]}")
    
    def finalize_person(self, roi):
        """Finalize person detection and save results"""
        helmet = self.ppe_confidence[roi]["helmet"] > yaml_config['ppe']['helmet_confidence']
        vest = self.ppe_confidence[roi]["vest"] > yaml_config['ppe']['vest_confidence']

        status = (
            "FULLY_COMPLIANT" if helmet and vest else
            "PARTIAL_PPE" if helmet else
            "PARTIAL_PPE" if vest else
            "NO_PPE"
        )
        
        with open(LOG_FILE_PATH, "a") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "roi": ROI_NAMES[roi],
                "status": status,
                **self.ppe_confidence[roi]
            }, f)
            f.write("\n")

        save_dir = self.get_today_roi_dir(roi)
        ts = datetime.now().strftime("%H-%M-%S")

        for idx, (_, img) in enumerate(self.best_frames[roi], start=1):
            stamped = img.copy() 
            self.draw_timestamp(stamped) 
            cv2.imwrite(os.path.join(save_dir, f"{ts}_BEST_{idx}.jpg"), stamped,[cv2.IMWRITE_JPEG_QUALITY, image_quality])
        
        if self.person_cooldown_enabled:
            self.roi_state[roi] = "COOLDOWN"
            self.person_cooldown_until[roi] = time.time() + self.PERSON_COOLDOWN
            print(f"{ROI_NAMES[roi]} entering {int(self.PERSON_COOLDOWN/60)}-minute person detection cooldown")
        else:
            self.roi_state[roi] = "OCCUPIED"
            print(f"{ROI_NAMES[roi]} person cooldown disabled, moving to OCCUPIED")
        
        self.person_lock[roi] = False
        self.monitor_start_time[roi] = None
        self.ppe_confidence[roi] = {"helmet": 0.0, "vest": 0.0}
        self.best_frames[roi] = []
        # Notify alarm player this ROI is no longer actively alarming
        self.alarm_player.clear_roi(roi)
    
    def start(self):
        """Start detection system"""
        self.config = self.load_config()
        
        self.capture_thread_obj = threading.Thread(target=self.capture_thread, daemon=True)
        self.capture_thread_obj.start()

        while self.frame_queue.empty():
            if self.stop_event.is_set():
                return
            time.sleep(0.01)
        
        frame = self.frame_queue.get() 
        h, w = frame.shape[:2]   
        scale = min(MAX_DISPLAY_WIDTH / w, MAX_DISPLAY_HEIGHT / h)

        for x1, y1, x2, y2 in ROIs_DISPLAY:
            self.ROIs_FOR_PROCESSING.append(
                (int(x1 / scale), int(y1 / scale),
                 int(x2 / scale), int(y2 / scale))
            )

        frame_id = 0
        prev_time = time.time()
        command_check_counter = 0

        print("Detection started - processing frames...")

        while not self.stop_event.is_set():
            if self.frame_queue.empty():
                time.sleep(0.001)
                continue

            frame = self.frame_queue.get()
            frame_id += 1

            command_check_counter += 1
            if command_check_counter >= 30:
                self.process_commands()
                command_check_counter = 0
            
            run_person = frame_id % FRAME_SKIP == 0 
            run_ppe = frame_id % PPE_FRAME_SKIP == 0

            roi_has_person = {i: False for i in range(len(ROIs_DISPLAY))}

            current_time = time.time() 
            for i in range(len(ROIs_DISPLAY)):
                if self.roi_state[i] == "COOLDOWN" and current_time >= self.person_cooldown_until[i]:
                    self.roi_state[i] = "IDLE"
                    print(f"{ROI_NAMES[i]} person detection cooldown ended, back to IDLE")

            if run_person:
                # Get list of ROIs in cooldown to skip drawing boxes
                cooldown_rois = [i for i in range(len(ROIs_DISPLAY)) 
                                if self.person_cooldown_enabled and self.roi_state[i] == "COOLDOWN"]
                
                # Run person detection on full frame with default confidence
                person_results = self.person_model.predict(
                    frame, 
                    imgsz=yaml_config['model']['person_detection']['imgsz'],   
                    conf=yaml_config['model']['person_detection']['conf'],    
                    device=0, half=False, verbose=False
                )[0]

                # Draw person boxes - ONLY for ROIs not in cooldown
                self.draw_person_boxes(frame, person_results, cooldown_rois)
            
                for box in person_results.boxes:
                    if person_results.names[int(box.cls[0])] != "person":
                        continue

                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    person_conf = float(box.conf[0])

                    for i, (rx1, ry1, rx2, ry2) in enumerate(self.ROIs_FOR_PROCESSING):
                        # Skip detection if ROI is in cooldown
                        if self.person_cooldown_enabled and self.roi_state[i] == "COOLDOWN":
                            continue
                        
                        # Check if person overlaps with ROI AND meets ROI-specific confidence threshold
                        if self.person_overlaps_roi(x1, y1, x2, y2, rx1, ry1, rx2, ry2):
                            # Apply ROI-specific confidence threshold
                            if person_conf >= ROI_PERSON_CONFIDENCE[i]:
                                roi_has_person[i] = True
                                self.roi_last_seen[i] = time.time()

                                if self.roi_state[i] == "IDLE":
                                    self.roi_state[i] = "MONITORING"
                                    self.person_lock[i] = True
                                    self.monitor_start_time[i] = time.time()

                                    self.alarm_player.play_alarm(roi_index=i)
                                    
                                    # REMOVED: SMS and Email notifications
                                    # send_sms(...)
                                    # send_email(...)
                                    print(f"Person detected in {ROI_NAMES[i]} (conf: {person_conf:.2f}) - Alarm triggered")

                                    img = frame.copy()
                                    self.draw_timestamp(img)
                                    cv2.imwrite(
                                        os.path.join(
                                            self.get_today_roi_dir(i),
                                            f"{datetime.now().strftime('%H-%M-%S')}_PERSON_DETECTED.jpg"
                                        ),
                                        img, [cv2.IMWRITE_JPEG_QUALITY, image_quality]
                                    )

                # Vehicle detection - only for ROIs not in person cooldown
                if True:
                    for i, roi_coords in enumerate(self.ROIs_FOR_PROCESSING):
                        self.detect_and_save_vehicle(frame, i, roi_coords)
            
            if run_ppe: 
                for i in range(len(self.ROIs_FOR_PROCESSING)):
                    if self.roi_state[i] != "MONITORING":
                        continue

                    elapsed = time.time() - self.monitor_start_time[i]
                    if elapsed <= MONITOR_DURATION:
                        x1, y1, x2, y2 = self.ROIs_FOR_PROCESSING[i]
                        roi_img = frame[y1:y2, x1:x2]

                        ppe_res = self.ppe_model.predict(
                            roi_img, 
                            imgsz=yaml_config['model']['ppe_detection']['imgsz'], 
                            conf=yaml_config['model']['ppe_detection']['conf'],
                            device=0, half=False, verbose=False
                        )[0]

                        for b in ppe_res.boxes:
                            name = ppe_res.names[int(b.cls[0])]
                            if name not in ["helmet", "vest"]:
                                continue

                            conf = float(b.conf[0])
                            self.ppe_confidence[i][name] = max(
                                self.ppe_confidence[i][name], conf
                            )
                            # Different pad
                            bx1, by1, bx2, by2 = map(int, b.xyxy[0])
                            bx1 += x1
                            bx2 += x1
                            by1 += y1
                            by2 += y1

                            annotated = frame.copy()
                            color = (255, 0, 0) if name == "helmet" else (0, 255, 255)
                            cv2.rectangle(annotated, (bx1, by1), (bx2, by2), color, 2)
                            cv2.putText(
                                annotated, f"{name} {conf:.2f}",
                                (bx1, by1 - 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2
                            )

                            self.best_frames[i].append((conf, annotated))
                            self.best_frames[i] = sorted(
                                self.best_frames[i],
                                key=lambda x: x[0],
                                reverse=True
                            )[:3]
                    else:
                        self.finalize_person(i)

            for i in range(len(ROIs_DISPLAY)):
                if self.roi_state[i] == "OCCUPIED":
                    if time.time() - self.roi_last_seen[i] > ROI_EMPTY_TIME:
                        self.roi_state[i] = "IDLE"
            
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
                            (0, 255, 0) if self.roi_state[i] == "IDLE" else
                            (0, 0, 255) if self.roi_state[i] == "MONITORING" else
                            (255, 0, 255) if self.roi_state[i] == "COOLDOWN" else
                            (128, 128, 128)
                        )
                        roi_name = ROI_NAMES[i]
                        cv2.rectangle( 
                            disp,
                            (int(x1 * sc), int(y1 * sc)),
                            (int(x2 * sc), int(y2 * sc)),
                            color, 2
                        )
                        y_text = int(y1 * sc) - 10
                        cv2.putText(
                                disp,
                                roi_name,
                                (int(x1 * sc), y_text),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.6,
                                color,
                                2
                        )
                        if self.roi_state[i] == "COOLDOWN":
                            remaining = int(self.person_cooldown_until[i] - time.time())
                            minutes = remaining // 60
                            seconds = remaining % 60
                            cv2.putText(
                                disp,
                                f"Repeat Detection Disable: {minutes}m {seconds}s",
                                (int(x1 * sc) + 150, int(y1 * sc) - 10),           
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2    
                            )
                            cv2.putText(
                                    disp,
                                    roi_name,
                                    (int(x1 * sc), int(y1 * sc) - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    0.6,
                                    color,
                                    2
                            )
                    # fps = int(1 / max(time.time() - prev_time, 1e-6))
                    # prev_time = time.time()
                    # cv2.putText(disp, f"FPS: {fps}", (20, 40),
                    #             cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

                    cv2.imshow("Output", disp)
                    if cv2.waitKey(1) & 0xFF == 27:
                        self.stop_event.set()
                        break
                else:
                    cv2.waitKey(1)

        # Clean shutdown - destroy windows in same thread that created them
        if self.cv2_window_created:
            try:
                cv2.destroyAllWindows()
                cv2.waitKey(1)  # Process pending events
            except Exception as e:
                print(f"Error destroying windows: {e}")
        
        print("Detection stopped")
    
    def stop(self):
        """Stop detection system"""
        print("Stopping detection system...")
        self.stop_event.set()
        
        # Stop alarm
        if self.alarm_player:
            try:
                self.alarm_player.stop()
            except Exception as e:
                print(f"Error stopping alarm: {e}")
        
        # Release video capture
        if self.cap:
            try:
                self.cap.release()
            except Exception as e:
                print(f"Error releasing capture: {e}")
        
        # Note: Don't destroy windows here - they should be destroyed in the same thread
        # that created them (which is the start() thread)
        print("Detection system stopped")