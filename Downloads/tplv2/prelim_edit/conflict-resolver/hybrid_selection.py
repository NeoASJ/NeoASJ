def select_violation_frames_hybrid(self, roi):
    all_frames = self.violation_frames[roi]

    if not all_frames:
        return []

    total = len(all_frames)

    if total <= 3:
        return all_frames

    third = total // 3

    early = all_frames[:third]
    mid = all_frames[third:third * 2]
    late = all_frames[third * 2:]

    def best_in_segment(segment):
        if not segment:
            return None
        return max(segment, key=lambda x: x['helmet_conf'] + x['vest_conf'])

    results = []
    for segment in [early, mid, late]:
        pick = best_in_segment(segment)
        if pick is not None:
            results.append(pick)

    return results
