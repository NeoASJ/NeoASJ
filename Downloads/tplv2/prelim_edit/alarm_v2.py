import winsound
import time
import threading
import os
import sys

def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class AlarmPlayer:
    def __init__(self, wav_path, cooldown=30):
        self.wav_path = resource_path(wav_path)
        self.cooldown = cooldown
        self.last_played = 0
        self.lock = threading.Lock()
        self.playing = False
        self._stop_event = threading.Event()  # For clean thread control 

    def play_alarm(self): 
        with self.lock:
            now = time.time()
            if self.playing:
                return
            if now - self.last_played < self.cooldown:
                return

            self.playing = True 
            self.last_played = now 
            self._stop_event.clear()   # Reset stop signal

        threading.Thread(target=self._play_thread, daemon=True).start()

    def _play_thread(self):
        # 🔊 Play with infinite loop until stop()
        winsound.PlaySound(
            self.wav_path,
            winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP
        )
        # Wait until stop() signals or process ends
        self._stop_event.wait()
        winsound.PlaySound(None, winsound.SND_PURGE)
        
        with self.lock:
            self.playing = False
            
    def stop(self):
        with self.lock:
            self._stop_event.set()  # Signal thread to stop waiting
            winsound.PlaySound(None, winsound.SND_PURGE)
            self.playing = False
    
    def is_playing(self):
        with self.lock:
            return self.playing
        