def get_adaptive_buffer_size(self, roi):
    helmet_conf = self.ppe_confidence[roi]["helmet"]
    vest_conf = self.ppe_confidence[roi]["vest"]
    combined = helmet_conf + vest_conf

    if combined == 0.0:
        return 3
    elif combined > 1.4:
        return 1
    elif combined > 0.9:
        return 2
    else:
        return 3


def update_adaptive_buffer(self, roi_index, score, annotated_frame):
    max_size = self.get_adaptive_buffer_size(roi_index)
    buffer = self.best_frames[roi_index]

    buffer.append({"score": score, "frame": annotated_frame})
    buffer.sort(key=lambda x: x["score"], reverse=True)

    while len(buffer) > max_size:
        buffer.pop()

    self.best_frames[roi_index] = buffer


def finalize_person_adaptive(self, roi):
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
            img = entry["frame"].copy()
            self.draw_timestamp(img)
            cv2.imwrite(
                os.path.join(save_dir, f"{ts}_{prefix}_{idx}.jpg"),
                img, [cv2.IMWRITE_JPEG_QUALITY, image_quality]
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
    self.alarm_player.clear_roi(roi)
