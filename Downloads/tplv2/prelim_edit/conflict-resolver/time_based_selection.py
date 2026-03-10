def select_violation_frames_time(self, roi):
    all_frames = self.violation_frames[roi]

    if not all_frames:
        return []

    total = len(all_frames)

    if total <= 3:
        return all_frames

    indices = [
        0,
        total // 2,
        total - 1
    ]

    return [all_frames[idx] for idx in indices]
