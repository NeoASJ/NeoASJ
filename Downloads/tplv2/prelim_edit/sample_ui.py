import sys
import ctypes
# Fix taskbar icon on Windows - MUST be at top before anything else
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PPEDetection.App")
except Exception:
    pass
import json
import os
from datetime import datetime
import threading
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QLineEdit, 
                             QSpinBox, QCheckBox, QGroupBox, QFileDialog,
                             QMessageBox, QTextEdit)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QPixmap, QIcon

# from detection_core_v3 import DetectionCore 
from integrate import DetectionCore , resource_path 
from notification_codebase import send_sms, email_coke, get_current_user_windows_login

# Configuration file for sharing settings with main script
CONFIG_FILE = "detection_config.json"    
COMMAND_FILE = "detection_commands.json" 

class ControlPanel(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(" Tiny Prism Labs ")
        self.setGeometry(100, 100, 700, 850)

        # Set window icon from output.ico
        ico_path = resource_path(r'output_logo.ico')
        if os.path.exists(ico_path):
            self.setWindowIcon(QIcon(ico_path))
        
        # Load or create config
        self.config = self.load_config()
        
        # Detection core instance
        self.detection_core = None
        self.detection_thread = None
        self.detection_running = False
        
        
        self.init_ui()
        
        # Timer to update status
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status_display)
        self.status_timer.start(1000)  # Update every second
    
    def init_ui(self):
        """Initialize UI components"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Title bar with image on the right
        title_bar = QWidget()
        title_bar.setStyleSheet("background-color: #2196F3;")
        title_bar_layout = QHBoxLayout()
        title_bar_layout.setContentsMargins(10, 2, 0, 2)
        title_bar.setLayout(title_bar_layout)

        # Title label (centered, takes most space)
        title_label = QLabel("PPE Detection System - Control Panel")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: white; background-color: transparent;")
        title_bar_layout.addWidget(title_label, stretch=1)

        # Image on the right
        img_label = QLabel()
        img_path = resource_path(r"data\TPL_Logo.PNG")
        if os.path.exists(img_path):
            pixmap = QPixmap(img_path)
            if not pixmap.isNull():
                img_label.setPixmap(pixmap.scaled(75, 75, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        img_label.setStyleSheet("background-color: transparent;")
        img_label.setFixedSize(79, 79)
        title_bar_layout.addWidget(img_label)

        main_layout.addWidget(title_bar)
        
        # Video Input Group
        video_group = QGroupBox("Video Input Configuration")
        video_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        video_layout = QVBoxLayout()
        
        path_label = QLabel("Video Path / RTSP URL:")
        self.video_path_input = QLineEdit()
        self.video_path_input.setPlaceholderText("e.g., /path/to/video.mp4 or rtsp://192.168.1.100:554/stream")
        self.video_path_input.setText(self.config.get("video_path", ""))
        video_layout.addWidget(path_label)
        video_layout.addWidget(self.video_path_input)
        
        browse_layout = QHBoxLayout()
        browse_btn = QPushButton("Browse File")
        browse_btn.clicked.connect(self.browse_video)
        browse_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px;")
        self.save_path_btn = QPushButton("Save Path & Start Detection")
        self.save_path_btn.clicked.connect(self.save_and_start)
        self.save_path_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 8px; font-weight: bold;")
        browse_layout.addWidget(browse_btn)
        browse_layout.addWidget(self.save_path_btn)
        video_layout.addLayout(browse_layout)
        video_group.setLayout(video_layout)
        main_layout.addWidget(video_group)
        
        # Detection Control Group
        detection_group = QGroupBox("Detection Control")
        detection_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        detection_layout = QVBoxLayout()
        
        # Status indicator
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("Detection Status:"))
        self.detection_status_label = QLabel("STOPPED")
        self.detection_status_label.setStyleSheet("color: red; font-weight: bold; padding: 5px;")
        status_layout.addWidget(self.detection_status_label)
        status_layout.addStretch()
        detection_layout.addLayout(status_layout)
        
        # Show/Hide Display Button
        self.toggle_display_btn = QPushButton("Show Live Detection Window")
        self.toggle_display_btn.clicked.connect(self.toggle_display)
        self.toggle_display_btn.setEnabled(False)
        self.toggle_display_btn.setStyleSheet("background-color: #9C27B0; color: white; padding: 15px; font-size: 14px; font-weight: bold;")
        detection_layout.addWidget(self.toggle_display_btn)
        
        # Info label
        info_label = QLabel("Note: Close the window to stop detection and exit application")
        info_label.setStyleSheet("color: #666; font-style: italic; padding: 5px;")
        detection_layout.addWidget(info_label)
        
        detection_group.setLayout(detection_layout)
        main_layout.addWidget(detection_group)
        
        # Alarm Control Group
        alarm_group = QGroupBox("Alarm Control")
        alarm_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        alarm_layout = QVBoxLayout()
        
        self.stop_alarm_btn = QPushButton("Acknowledge Alarm")
        self.stop_alarm_btn.clicked.connect(self.stop_alarm)
        self.stop_alarm_btn.setStyleSheet("background-color: #FF5722; color: white; padding: 15px; font-size: 14px; font-weight: bold;")
        alarm_layout.addWidget(self.stop_alarm_btn)
        
        alarm_group.setLayout(alarm_layout)
        main_layout.addWidget(alarm_group)
    
        # Person Cooldown Group
        person_group = QGroupBox("Person Detection Settings")
        person_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        person_layout = QVBoxLayout()
        
        # Enable/Disable
        self.person_cooldown_checkbox = QCheckBox("Enable Person Repeat Detection Disable")
        self.person_cooldown_checkbox.setChecked(self.config.get("person_cooldown_enabled", True))
        self.person_cooldown_checkbox.stateChanged.connect(self.update_person_cooldown_state)
        person_layout.addWidget(self.person_cooldown_checkbox)
        
        # Cooldown time
        person_time_layout = QHBoxLayout()
        person_time_layout.addWidget(QLabel("Repeat Detection Disable "))
        self.person_cooldown_spinbox = QSpinBox()
        self.person_cooldown_spinbox.setRange(1, 120)
        self.person_cooldown_spinbox.setValue(self.config.get("person_cooldown_minutes", 30))
        self.person_cooldown_spinbox.valueChanged.connect(self.update_person_cooldown_time)
        person_time_layout.addWidget(self.person_cooldown_spinbox)
        person_time_layout.addStretch()
        person_layout.addLayout(person_time_layout)
        
        # ROI-specific controls
        person_layout.addWidget(QLabel("Reset Person Repeat Detection Disable for Specific ROI:"))
        person_reset_layout = QHBoxLayout()
        reset_person_roi1_btn = QPushButton("Reset Tank View")
        reset_person_roi1_btn.clicked.connect(lambda: self.reset_person_cooldown(0))
        reset_person_roi1_btn.setStyleSheet("background-color: #FF9800; color: white; padding: 15px; font-size: 14px;")
        reset_person_roi2_btn = QPushButton("Reset Road View")
        reset_person_roi2_btn.clicked.connect(lambda: self.reset_person_cooldown(1))
        reset_person_roi2_btn.setStyleSheet("background-color: #FF9800; color: white; padding: 15px; font-size: 14px;")
        person_reset_layout.addWidget(reset_person_roi1_btn)
        person_reset_layout.addWidget(reset_person_roi2_btn)
        person_layout.addLayout(person_reset_layout)
        
        person_group.setLayout(person_layout)
        main_layout.addWidget(person_group)
        
        # Vehicle Cooldown Group
        vehicle_group = QGroupBox("Vehicle Detection Settings")
        vehicle_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        vehicle_layout = QVBoxLayout()
        
        # Enable/Disable
        self.vehicle_cooldown_checkbox = QCheckBox("Enable Vehicle Repeat Detection Disable")
        self.vehicle_cooldown_checkbox.setChecked(self.config.get("vehicle_cooldown_enabled", True))
        self.vehicle_cooldown_checkbox.stateChanged.connect(self.update_vehicle_cooldown_state)
        vehicle_layout.addWidget(self.vehicle_cooldown_checkbox)
        
        # Cooldown time
        vehicle_time_layout = QHBoxLayout()
        vehicle_time_layout.addWidget(QLabel("Repeat Detection Disable"))
        self.vehicle_cooldown_spinbox = QSpinBox()
        self.vehicle_cooldown_spinbox.setRange(1, 300)
        self.vehicle_cooldown_spinbox.setValue(self.config.get("vehicle_cooldown_seconds", 10))
        self.vehicle_cooldown_spinbox.valueChanged.connect(self.update_vehicle_cooldown_time)
        vehicle_time_layout.addWidget(self.vehicle_cooldown_spinbox)
        vehicle_time_layout.addStretch()
        vehicle_layout.addLayout(vehicle_time_layout)
        
        vehicle_group.setLayout(vehicle_layout)
        main_layout.addWidget(vehicle_group)
        
        # --- MODIFIED SECTION: Reset All + Send Message buttons side by side ---
        bottom_btn_layout = QHBoxLayout()

        reset_all_btn = QPushButton("Reset All Repeat Detection Disables for All Views")
        reset_all_btn.clicked.connect(self.reset_all_cooldowns)
        reset_all_btn.setStyleSheet("background-color: #F44336; color: white; padding: 15px; font-size: 14px; font-weight: bold;")
        bottom_btn_layout.addWidget(reset_all_btn, stretch=3)  # 75% width

        send_message_btn = QPushButton("Send Message")
        send_message_btn.clicked.connect(self.send_message)
        send_message_btn.setStyleSheet("background-color: #607D8B; color: white; padding: 15px; font-size: 14px; font-weight: bold;")
        bottom_btn_layout.addWidget(send_message_btn, stretch=1)  # 25% width

        main_layout.addLayout(bottom_btn_layout)
        # --- END MODIFIED SECTION ---

        # Activity Log
        log_group = QGroupBox("Activity Log")
        log_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        log_layout.addWidget(self.log_text)
        
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)
        
        # Initial log
        self.log_action("Control panel initialized")
    
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
            "person_cooldown_enabled": True,
            "person_cooldown_minutes": 30,
            "vehicle_cooldown_enabled": True,
            "vehicle_cooldown_seconds": 10
        }
    
    def save_config(self):
        """Save configuration to file"""
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def send_command(self, command_dict):
        """Send command to detection core via JSON file"""
        try:
            command_dict["timestamp"] = datetime.now().isoformat()
            with open(COMMAND_FILE, 'w') as f:
                json.dump(command_dict, f)
        except Exception as e:
            print(f"Error sending command: {e}")
    
    def log_action(self, message):
        """Log action to text widget"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        self.log_text.append(log_message)
        
        # Auto-scroll to bottom 
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def browse_video(self):
        """Browse for video file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select Video File", 
            "", 
            "Video Files (*.mp4 *.avi *.mkv *.mov);;All Files (*)"
        )
        if file_path:
            self.video_path_input.setText(file_path)
            self.log_action(f"Selected video: {file_path}")
    
    def save_and_start(self):
        """Save video path and start detection"""
        video_path = self.video_path_input.text().strip()
        
        if not video_path:
            QMessageBox.warning(self, "Warning", "Please enter a video path or RTSP URL!")
            return
        
        # Update config
        self.config["video_path"] = video_path
        self.save_config()
        
        self.log_action(f"Video path saved: {video_path}")
        
        # Start detection
        self.start_detection()
    
    def start_detection(self):
        """Start detection in separate thread"""
        if self.detection_running:
            QMessageBox.warning(self, "Warning", "Detection is already running!")
            return
        
        video_path = self.config.get("video_path", "")
        if not video_path:
            QMessageBox.warning(self, "Warning", "Please configure video path first!")
            return
        
        try:
            # Create detection core instance
            self.detection_core = DetectionCore()
            
            # Start detection in separate thread
            self.detection_thread = threading.Thread(
                target=self.detection_core.start,
                daemon=True
            )
            self.detection_thread.start()
            
            self.detection_running = True
            self.detection_status_label.setText("RUNNING")
            self.detection_status_label.setStyleSheet("color: green; font-weight: bold; padding: 5px;")
            self.save_path_btn.setEnabled(False)
            self.toggle_display_btn.setEnabled(True)
            
            self.log_action("Detection started successfully")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start detection: {str(e)}")
            self.log_action(f"Detection start failed: {str(e)}")
    
    def stop_detection_gracefully(self):
        """Stop detection gracefully"""
        if not self.detection_running:
            return
        
        try:
            self.log_action("Stopping detection...")
            
            if self.detection_core:
                # Signal detection to stop
                self.detection_core.stop_event.set()
                
                # Wait for thread to finish with timeout
                if self.detection_thread and self.detection_thread.is_alive():
                    self.detection_thread.join(timeout=3.0)
                    
                    # If thread is still alive after timeout, log warning
                    if self.detection_thread.is_alive():
                        self.log_action("Warning: Detection thread did not stop cleanly")
                
                # Call stop method for final cleanup
                # Note: Don't destroy OpenCV windows here - they're destroyed in the detection thread
                if self.detection_core:
                    self.detection_core.stop()
                
                self.log_action("Detection stopped successfully")
                
            # Update UI state
            self.detection_running = False
            self.detection_status_label.setText("STOPPED")
            self.detection_status_label.setStyleSheet("color: red; font-weight: bold; padding: 5px;")
            self.save_path_btn.setEnabled(True)
            self.toggle_display_btn.setEnabled(False)
            self.toggle_display_btn.setText("Show Live Detection Window")
            self.toggle_display_btn.setStyleSheet("background-color: #9C27B0; color: white; padding: 12px; font-size: 13px; font-weight: bold;")
            
        except Exception as e:
            self.log_action(f"Error during cleanup: {e}")
        finally:
            self.detection_core = None
            self.detection_thread = None
    
    def toggle_display(self):
        """Toggle live detection window visibility"""
        if not self.detection_running or not self.detection_core:
            return
        
        # Toggle display state
        current_state = self.detection_core.show_display
        new_state = not current_state
        
        # Send command to detection core
        self.send_command({
            "action": "toggle_display",
            "show": new_state
        })
        
        # Update button text
        if new_state:
            self.toggle_display_btn.setText("Hide Live Detection Window")
            self.toggle_display_btn.setStyleSheet("background-color: #E91E63; color: white; padding: 12px; font-size: 13px; font-weight: bold;")
            self.log_action("Live detection window shown")
        else:
            self.toggle_display_btn.setText("Show Live Detection Window")
            self.toggle_display_btn.setStyleSheet("background-color: #9C27B0; color: white; padding: 12px; font-size: 13px; font-weight: bold;")
            self.log_action("Live detection window hidden")
    
    def stop_alarm(self):
        """Stop alarm"""
        if self.detection_core and self.detection_core.alarm_player:
            self.detection_core.alarm_player.stop()
            self.log_action("Alarm acknowledged")
        else:
            # Send command even if detection not running
            self.send_command({
                "action": "stop_alarm"
            })
            self.log_action("Alarm acknowledge command sent")
    
    def update_person_cooldown_state(self, state):
        """Update person cooldown enabled state"""
        enabled = (state == Qt.Checked)
        self.config["person_cooldown_enabled"] = enabled
        self.save_config()
        self.send_command({
            "action": "set_person_cooldown_enabled",
            "enabled": enabled
        })
        status = "enabled" if enabled else "disabled"
        self.log_action(f"Person repeat detection disable {status}")
    
    def update_person_cooldown_time(self, value):
        """Update person cooldown time"""
        self.config["person_cooldown_minutes"] = value
        self.save_config()
        self.send_command({
            "action": "set_person_cooldown_time",
            "minutes": value
        })
        self.log_action(f"Person repeat detection disable time set to {value} minutes")
    
    def update_vehicle_cooldown_state(self, state):
        """Update vehicle cooldown enabled state"""
        enabled = (state == Qt.Checked)
        self.config["vehicle_cooldown_enabled"] = enabled
        self.save_config()
        self.send_command({
            "action": "set_vehicle_cooldown_enabled",
            "enabled": enabled
        })
        status = "enabled" if enabled else "disabled"
        self.log_action(f"Vehicle repeat detection disable {status}")
    
    def update_vehicle_cooldown_time(self, value):
        """Update vehicle cooldown time"""
        self.config["vehicle_cooldown_seconds"] = value
        self.save_config()
        self.send_command({
            "action": "set_vehicle_cooldown_time",
            "seconds": value
        })
        self.log_action(f"Vehicle repeat detection disable time set to {value} seconds")
    
    def reset_person_cooldown(self, roi_index):
        """Reset person cooldown for specific ROI"""
        roi_names = ["Tank View", "Road View"]
        self.send_command({
            "action": "reset_person_cooldown",
            "roi_index": roi_index
        })
        self.log_action(f"Reset person repeat detection disable for {roi_names[roi_index]}")
        QMessageBox.information(self, "Success", f"Person repeat detection disable reset for {roi_names[roi_index]}")
    
    def reset_vehicle_cooldown(self, roi_index):
        """Reset vehicle cooldown for specific ROI"""
        roi_names = ["Tank View", "Road View"]
        self.send_command({
            "action": "reset_vehicle_cooldown",
            "roi_index": roi_index
        })
        self.log_action(f"Reset vehicle repeat detection disable for {roi_names[roi_index]}")
        QMessageBox.information(self, "Success", f"Vehicle repeat detection disable reset for {roi_names[roi_index]}")
    
    def reset_all_cooldowns(self):
        """Reset all cooldowns for all ROIs"""
        reply = QMessageBox.question(
            self, "Confirm Reset", 
            "Are you sure you want to reset all repeat detection disables for all ROIs?",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.send_command({
                "action": "reset_all_cooldowns"
            })
            self.log_action("Reset all repeat detection disables for all ROIs")
            QMessageBox.information(self, "Success", "All repeat detection disables reset for all ROIs")

    def send_message(self):
        """Send SMS and Email notifications"""
        try:
            message1 = "A Person Detected near FB7029A/B"
            mobile_nos = '9448626741,9606903614'
            send_sms(message1, mobile_nos)
            self.log_action("SMS sent successfully")
        except Exception as e:
            self.log_action(f"SMS sending failed: {e}")

        try:
            html_string = "Alert!! A Person Detected near FB7029A/B"
            smtp_server = "172.16.11.22"
            email_ids = ["thilakaraj@mrpl.co.in"]

            time1 = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            attachment_path = r'sample_test.jpg'
            if not os.path.exists(attachment_path):
                attachment_path = None
            email_coke(html_string, smtp_server, email_ids, time1, attachment_path)
            self.log_action("Email sent successfully")
        except Exception as e:
            self.log_action(f"Email sending failed: {e}")

    def update_status_display(self):
        """Update status display with current config"""
        # Update alarm status
        if self.detection_core and self.detection_core.alarm_player:
            if self.detection_core.alarm_player.is_playing():
                self.stop_alarm_btn.setStyleSheet("background-color: #FF0000; color: white; padding: 15px; font-size: 14px; font-weight: bold;")
            else:
                self.stop_alarm_btn.setStyleSheet("background-color: #FF5722; color: white; padding: 15px; font-size: 14px; font-weight: bold;")
    
    def closeEvent(self, event):
        """Handle window close event"""
        if self.detection_running:
            reply = QMessageBox.question(
                self, "Confirm Exit", 
                "Detection is still running. Do you want to stop it and exit?",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Stop timer first
                self.status_timer.stop()
                
                # Stop detection gracefully
                self.stop_detection_gracefully()
                
                # Process any remaining events
                QApplication.processEvents()
                
                # Small delay to ensure everything completes
                import time
                time.sleep(0.5)
                
                event.accept()
            else:
                event.ignore()
        else:
            # Stop timer
            self.status_timer.stop()
            event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    icon = QIcon(resource_path(r'output_logo.ico'))
    app.setWindowIcon(icon)
    
    window = ControlPanel()
    window.setWindowIcon(icon)
    window.show()
    window.setWindowIcon(icon)  # Set again after show() so taskbar picks it up
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()