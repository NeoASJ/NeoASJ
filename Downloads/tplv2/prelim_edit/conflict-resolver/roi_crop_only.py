def run_person_roi_only(self, frame, frame_id):
    if frame_id % FRAME_SKIP != 0:
        return

    for i, (rx1, ry1, rx2, ry2) in enumerate(self.ROIs_FOR_PROCESSING):
        if self.person_cooldown_enabled and self.roi_state[i] == "COOLDOWN":
            continue

        roi_crop = frame[ry1:ry2, rx1:rx2]

        results = self.person_model.predict(
            roi_crop,
            imgsz=yaml_config['model']['person_detection']['imgsz'],
            conf=yaml_config['model']['person_detection']['conf'],
            device=0,
            half=False,
            verbose=False
        )[0]

        for box in results.boxes:
            if results.names[int(box.cls[0])] != "person":
                continue

            person_conf = float(box.conf[0])
            if person_conf < ROI_PERSON_CONFIDENCE[i]:
                continue

            self.roi_last_seen[i] = time.time()

            bx1, by1, bx2, by2 = map(int, box.xyxy[0])
            fx1 = bx1 + rx1
            fy1 = by1 + ry1
            fx2 = bx2 + rx1
            fy2 = by2 + ry1

            cv2.rectangle(frame, (fx1, fy1), (fx2, fy2), (0, 255, 0), 2)

            if self.roi_state[i] == "IDLE":
                self.roi_state[i] = "MONITORING"
                self.person_lock[i] = True
                self.monitor_start_time[i] = time.time()
                self.alarm_player.play_alarm(roi_index=i)

                snapshot = frame.copy()
                self.draw_timestamp(snapshot)
                filename = f"{datetime.now().strftime('%H-%M-%S')}_PERSON_DETECTED.jpg"
                cv2.imwrite(
                    os.path.join(self.get_today_roi_dir(i), filename),
                    snapshot,
                    [cv2.IMWRITE_JPEG_QUALITY, image_quality]
                )


def run_ppe_roi_only(self, frame, frame_id):
    if frame_id % PPE_FRAME_SKIP != 0:
        return

    for i in range(len(self.ROIs_FOR_PROCESSING)):
        if self.roi_state[i] != "MONITORING":
            continue

        elapsed = time.time() - self.monitor_start_time[i]

        if elapsed > MONITOR_DURATION:
            self.finalize_person(i)
            continue

        x1, y1, x2, y2 = self.ROIs_FOR_PROCESSING[i]
        roi_img = frame[y1:y2, x1:x2]

        ppe_res = self.ppe_model.predict(
            roi_img,
            imgsz=yaml_config['model']['ppe_detection']['imgsz'],
            conf=yaml_config['model']['ppe_detection']['conf'],
            device=0,
            half=False,
            verbose=False
        )[0]

        frame_helmet_conf = 0.0
        frame_vest_conf = 0.0
        has_detection = False

        for b in ppe_res.boxes:
            name = ppe_res.names[int(b.cls[0])]
            if name not in ["helmet", "vest"]:
                continue
            conf = float(b.conf[0])
            has_detection = True
            self.ppe_confidence[i][name] = max(self.ppe_confidence[i][name], conf)
            if name == "helmet":
                frame_helmet_conf = max(frame_helmet_conf, conf)
            else:
                frame_vest_conf = max(frame_vest_conf, conf)

        frame_score = frame_helmet_conf + frame_vest_conf if has_detection else 0.01

        buffer = self.best_frames[i]
        if len(buffer) < 3 or frame_score > buffer[-1]["score"]:
            annotated = frame.copy()

            for b in ppe_res.boxes:
                name = ppe_res.names[int(b.cls[0])]
                if name not in ["helmet", "vest"]:
                    continue
                conf = float(b.conf[0])
                bx1, by1, bx2, by2 = map(int, b.xyxy[0])
                bx1 += x1; bx2 += x1
                by1 += y1; by2 += y1
                color = (255, 0, 0) if name == "helmet" else (0, 255, 255)
                cv2.rectangle(annotated, (bx1, by1), (bx2, by2), color, 2)

            person_res = self.person_model.predict(
                roi_img,
                imgsz=yaml_config['model']['person_detection']['imgsz'],
                conf=yaml_config['model']['person_detection']['conf'],
                device=0,
                half=False,
                verbose=False
            )[0]

            for pb in person_res.boxes:
                if person_res.names[int(pb.cls[0])] != "person":
                    continue
                px1, py1, px2, py2 = map(int, pb.xyxy[0])
                px1 += x1; px2 += x1
                py1 += y1; py2 += y1
                cv2.rectangle(annotated, (px1, py1), (px2, py2), (0, 0, 255), 2)

            self.update_ppe_buffer(i, frame_score, annotated)
