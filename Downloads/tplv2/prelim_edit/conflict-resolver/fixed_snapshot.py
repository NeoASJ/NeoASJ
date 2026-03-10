def run_ppe_fixed_snapshot(self, frame, frame_id):
    if frame_id % PPE_FRAME_SKIP != 0:
        return

    snapshot_ratios = [0.2, 0.5, 0.8]

    for i in range(len(self.ROIs_FOR_PROCESSING)):
        if self.roi_state[i] != "MONITORING":
            continue

        elapsed = time.time() - self.monitor_start_time[i]

        if elapsed > MONITOR_DURATION:
            self.finalize_person(i)
            continue

        progress = elapsed / MONITOR_DURATION
        should_capture = any(
            abs(progress - ratio) < (PPE_FRAME_SKIP / 30) / MONITOR_DURATION
            for ratio in snapshot_ratios
            if ratio not in self.snapshot_captured[i]
        )

        if not should_capture:
            continue

        for ratio in snapshot_ratios:
            if abs(progress - ratio) < (PPE_FRAME_SKIP / 30) / MONITOR_DURATION:
                if ratio not in self.snapshot_captured[i]:
                    self.snapshot_captured[i].add(ratio)

        x1, y1, x2, y2 = self.ROIs_FOR_PROCESSING[i]
        roi_img = frame[y1:y2, x1:x2]

        ppe_res = self.ppe_model.predict(
            roi_img,
            imgsz=yaml_config['model']['ppe_detection']['imgsz'],
            conf=yaml_config['model']['ppe_detection']['conf'],
            device=0, half=False, verbose=False
        )[0]

        annotated = frame.copy()

        for b in ppe_res.boxes:
            name = ppe_res.names[int(b.cls[0])]
            if name not in ["helmet", "vest"]:
                continue
            conf = float(b.conf[0])
            self.ppe_confidence[i][name] = max(self.ppe_confidence[i][name], conf)
            bx1, by1, bx2, by2 = map(int, b.xyxy[0])
            bx1 += x1; bx2 += x1
            by1 += y1; by2 += y1
            color = (255, 0, 0) if name == "helmet" else (0, 255, 255)
            cv2.rectangle(annotated, (bx1, by1), (bx2, by2), color, 2)

        person_res = self.person_model.predict(
            roi_img,
            imgsz=yaml_config['model']['person_detection']['imgsz'],
            conf=yaml_config['model']['person_detection']['conf'],
            device=0, half=False, verbose=False
        )[0]

        for pb in person_res.boxes:
            if person_res.names[int(pb.cls[0])] != "person":
                continue
            px1, py1, px2, py2 = map(int, pb.xyxy[0])
            px1 += x1; px2 += x1
            py1 += y1; py2 += y1
            cv2.rectangle(annotated, (px1, py1), (px2, py2), (0, 0, 255), 2)

        self.snapshot_frames[i].append(annotated)


def init_snapshot_state(self):
    self.snapshot_frames = {i: [] for i in range(len(ROIs_DISPLAY))}
    self.snapshot_captured = {i: set() for i in range(len(ROIs_DISPLAY))}


def reset_snapshot_state(self, roi):
    self.snapshot_frames[roi] = []
    self.snapshot_captured[roi] = set()
