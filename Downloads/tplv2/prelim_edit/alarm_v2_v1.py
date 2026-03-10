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

        # Track which ROIs are actively alarming so multiple ROIs can each
        # independently request the alarm. stop() silences the sound while
        # leaving the door open for the next legitimate trigger.
        self._active_roi_alarms = set()

    def play_alarm(self, roi_index=None):
        """
        Trigger the alarm.
        roi_index: optional int identifying which ROI triggered (0, 1, ...).
                   When provided, the ROI is registered so stop() knows
                   how many sources are active.
        """
        with self.lock:
            now = time.time()

            # Register this ROI as an active alarm source (if supplied)
            if roi_index is not None:
                self._active_roi_alarms.add(roi_index)

            # Already playing — winsound keeps looping, nothing more needed
            if self.playing:
                return

            # Cooldown guard: only applies between *automatic* re-triggers,
            # NOT after a manual stop/acknowledge (last_played is reset then).
            if now - self.last_played < self.cooldown:
                return

            self.playing = True
            self.last_played = now
            self._stop_event.clear()   # Reset stop signal

        threading.Thread(target=self._play_thread, daemon=True).start()

    def _play_thread(self):
        # Play with infinite loop until stop()
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
        """
        Acknowledge / stop the alarm.
        Resets last_played to 0 so the next detection event can trigger
        the alarm immediately — no 30-second silence after an acknowledge.
        """
        with self.lock:
            self._stop_event.set()           # Signal play thread to exit
            winsound.PlaySound(None, winsound.SND_PURGE)
            self.playing = False
            # KEY FIX: reset last_played so the cooldown does NOT block the
            # next real alarm after the user has manually acknowledged.
            self.last_played = 0
            # Clear all ROI registrations — fresh slate after acknowledge
            self._active_roi_alarms.clear()

    def clear_roi(self, roi_index):
        """
        Called when a specific ROI finishes its MONITORING phase (enters COOLDOWN).
        Removes it from the active set but does NOT stop the alarm — another
        ROI may still be alarming.
        """
        with self.lock:
            self._active_roi_alarms.discard(roi_index)

    def is_playing(self):
        with self.lock:
            return self.playing