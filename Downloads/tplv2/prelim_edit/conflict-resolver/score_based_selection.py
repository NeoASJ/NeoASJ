def select_violation_frames_score(self, roi):
    all_frames = self.violation_frames[roi]

    if not all_frames:
        return []

    scored = []
    for entry in all_frames:
        total = entry['helmet_conf'] + entry['vest_conf']
        scored.append((total, entry))

    scored.sort(key=lambda x: x[0], reverse=True)

    return [x[1] for x in scored[:3]]
