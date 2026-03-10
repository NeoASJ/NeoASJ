def update_ppe_buffer(self, roi_index, score, annotated_frame):
    buffer = self.best_frames[roi_index]

    if len(buffer) < 3:
        buffer.append({"score": score, "frame": annotated_frame})
        buffer.sort(key=lambda x: x["score"], reverse=True)
    elif score > buffer[-1]["score"]:
        buffer[-1] = {"score": score, "frame": annotated_frame}
        buffer.sort(key=lambda x: x["score"], reverse=True)

    self.best_frames[roi_index] = buffer


def finalize_person(self, roi):
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

    if status == "FULLY_COMPLIANT":
        print(f"{ROI_NAMES[roi]} fully compliant, no images saved")

    elif status == "PARTIAL_PPE":
        for idx, entry in enumerate(self.best_frames[roi], start=1):
            img = entry["frame"].copy()
            self.draw_timestamp(img)
            cv2.imwrite(
                os.path.join(save_dir, f"{ts}_partial_ppe_{idx}.jpg"),
                img, [cv2.IMWRITE_JPEG_QUALITY, image_quality]
            )

    elif status == "NO_PPE":
        for idx, entry in enumerate(self.best_frames[roi], start=1):
            img = entry["frame"].copy()
            self.draw_timestamp(img)
            cv2.imwrite(
                os.path.join(save_dir, f"{ts}_no_ppe_{idx}.jpg"),
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
