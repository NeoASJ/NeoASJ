import numpy as np


def init_frame_pool(self, frame_h, frame_w, pool_size=3):
    self.frame_pool = [
        np.zeros((frame_h, frame_w, 3), dtype=np.uint8)
        for _ in range(pool_size)
    ]
    self.frame_pool_index = {i: 0 for i in range(len(ROIs_DISPLAY))}


def get_pooled_frame(self, roi_index, source_frame):
    pool_idx = self.frame_pool_index[roi_index] % len(self.frame_pool)
    np.copyto(self.frame_pool[pool_idx], source_frame)
    self.frame_pool_index[roi_index] += 1
    return self.frame_pool[pool_idx]


def update_ppe_buffer_pooled(self, roi_index, score, source_frame):
    buffer = self.best_frames[roi_index]

    if len(buffer) < 3:
        pooled = self.get_pooled_frame(roi_index, source_frame)
        buffer.append({"score": score, "frame": pooled})
        buffer.sort(key=lambda x: x["score"], reverse=True)

    elif score > buffer[-1]["score"]:
        pooled = self.get_pooled_frame(roi_index, source_frame)
        buffer[-1] = {"score": score, "frame": pooled}
        buffer.sort(key=lambda x: x["score"], reverse=True)

    self.best_frames[roi_index] = buffer


def finalize_person_pooled(self, roi):
    helmet = self.ppe_confidence[roi]["helmet"] > yaml_config['ppe']['helmet_confidence']
    vest = self.ppe_confidence[roi]["vest"] > yaml_config['ppe']['vest_confidence']

    status = (
        "FULLY_COMPLIANT" if helmet and vest else
        "PARTIAL_PPE" if helmet or vest else
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

    if status != "FULLY_COMPLIANT":
        prefix = "no_ppe" if status == "NO_PPE" else "partial_ppe"
        for idx, entry in enumerate(self.best_frames[roi], start=1):
            save_img = entry["frame"].copy()
            self.draw_timestamp(save_img)
            cv2.imwrite(
                os.path.join(save_dir, f"{ts}_{prefix}_{idx}.jpg"),
                save_img,
                [cv2.IMWRITE_JPEG_QUALITY, image_quality]
            )

    if self.person_cooldown_enabled:
        self.roi_state[roi] = "COOLDOWN"
        self.person_cooldown_until[roi] = time.time() + self.PERSON_COOLDOWN
    else:
        self.roi_state[roi] = "OCCUPIED"

    self.person_lock[roi] = False
    self.monitor_start_time[roi] = None
    self.ppe_confidence[roi] = {"helmet": 0.0, "vest": 0.0}
    self.best_frames[roi] = []
    self.frame_pool_index[roi] = 0
    self.alarm_player.clear_roi(roi)
