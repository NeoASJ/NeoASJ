import cv2
import time
import threading
from imutils.video import VideoStream
from datetime import datetime

RTSP_URL = input("Enter RTSP URL: ").strip()
TEST_DURATION = 30  # seconds to test each method

# ─────────────────────────────────────────────
# RESULTS STORAGE
# ─────────────────────────────────────────────
results = {
    "opencv": {
        "frames_read":    0,
        "frames_dropped": 0,
        "read_times":     [],
        "start_time":     None,
    },
    "imutils": {
        "frames_read":    0,
        "frames_dropped": 0,
        "read_times":     [],
        "start_time":     None,
    }
}

# ─────────────────────────────────────────────
# TEST 1 — OpenCV direct read
# ─────────────────────────────────────────────
def test_opencv():
    print("\n" + "="*50)
    print("TESTING: OpenCV cv2.VideoCapture")
    print("="*50)

    cap = cv2.VideoCapture(RTSP_URL)

    if not cap.isOpened():
        print("[ERROR] Could not open stream with OpenCV")
        return

    results["opencv"]["start_time"] = time.time()
    end_time = results["opencv"]["start_time"] + TEST_DURATION

    while time.time() < end_time:
        t1 = time.time()
        ret, frame = cap.read()
        t2 = time.time()

        if ret and frame is not None:
            results["opencv"]["frames_read"] += 1
            results["opencv"]["read_times"].append(t2 - t1)
        else:
            results["opencv"]["frames_dropped"] += 1

    cap.release()
    print(f"[OpenCV] Done — {results['opencv']['frames_read']} frames read, "
          f"{results['opencv']['frames_dropped']} dropped")


# ─────────────────────────────────────────────
# TEST 2 — imutils VideoStream (threaded)
# ─────────────────────────────────────────────
def test_imutils():
    print("\n" + "="*50)
    print("TESTING: imutils VideoStream (threaded)")
    print("="*50)

    try:
        vs = VideoStream(src=RTSP_URL).start()
        time.sleep(2.0)  # warm up the stream thread
    except Exception as e:
        print(f"[ERROR] Could not open stream with imutils: {e}")
        return

    results["imutils"]["start_time"] = time.time()
    end_time = results["imutils"]["start_time"] + TEST_DURATION
    prev_frame = None

    while time.time() < end_time:
        t1 = time.time()
        frame = vs.read()
        t2 = time.time()

        if frame is not None:
            # imutils returns last cached frame even when stream drops —
            # detect repeated frames as a dropped indicator
            if prev_frame is not None:
                diff = cv2.absdiff(frame, prev_frame)
                if diff.sum() < 100:
                    results["imutils"]["frames_dropped"] += 1
                else:
                    results["imutils"]["frames_read"] += 1
                    results["imutils"]["read_times"].append(t2 - t1)
            else:
                results["imutils"]["frames_read"] += 1
                results["imutils"]["read_times"].append(t2 - t1)
            prev_frame = frame.copy()
        else:
            results["imutils"]["frames_dropped"] += 1

    vs.stop()
    print(f"[imutils] Done — {results['imutils']['frames_read']} frames read, "
          f"{results['imutils']['frames_dropped']} dropped")


# ─────────────────────────────────────────────
# REPORT
# ─────────────────────────────────────────────
def print_report():
    print("\n")
    print("=" * 60)
    print("           RTSP STREAM BENCHMARK REPORT")
    print(f"           URL : {RTSP_URL}")
    print(f"           Duration tested : {TEST_DURATION}s each")
    print("=" * 60)

    for method in ["opencv", "imutils"]:
        r = results[method]
        total = r["frames_read"] + r["frames_dropped"]
        packet_loss = (r["frames_dropped"] / total * 100) if total > 0 else 0
        avg_read_ms = (sum(r["read_times"]) / len(r["read_times"]) * 1000) if r["read_times"] else 0
        fps = r["frames_read"] / TEST_DURATION

        print(f"\n  [{method.upper()}]")
        print(f"    Frames Read        : {r['frames_read']}")
        print(f"    Frames Dropped     : {r['frames_dropped']}")
        print(f"    Total Frames       : {total}")
        print(f"    Packet Loss        : {packet_loss:.2f}%")
        print(f"    Avg FPS            : {fps:.2f}")
        print(f"    Avg Read Time      : {avg_read_ms:.2f} ms")

        # Performance rating
        if packet_loss < 5:
            rating = "EXCELLENT ✅"
        elif packet_loss < 15:
            rating = "GOOD ✅"
        elif packet_loss < 30:
            rating = "AVERAGE ⚠️"
        else:
            rating = "POOR ❌"

        print(f"    Performance Rating : {rating}")

    print("\n" + "=" * 60)
    print("  RECOMMENDATION")
    print("=" * 60)

    ocv_loss = results["opencv"]["frames_dropped"] / max(1, results["opencv"]["frames_read"] + results["opencv"]["frames_dropped"]) * 100
    imu_loss = results["imutils"]["frames_dropped"] / max(1, results["imutils"]["frames_read"] + results["imutils"]["frames_dropped"]) * 100
    ocv_fps  = results["opencv"]["frames_read"] / TEST_DURATION
    imu_fps  = results["imutils"]["frames_read"] / TEST_DURATION

    if imu_fps > ocv_fps and imu_loss <= ocv_loss:
        print("  → Use imutils (higher FPS, lower/equal packet loss)")
    elif ocv_fps >= imu_fps and ocv_loss <= imu_loss:
        print("  → Use OpenCV (stable, lower/equal packet loss)")
    else:
        print("  → Use imutils (threaded read generally smoother for RTSP)")

    print("=" * 60)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n[INFO] Starting benchmark — {TEST_DURATION}s per method")
    print(f"[INFO] Total test time ~ {TEST_DURATION * 2}s\n")
    # Making a calll for both  result compared last 
    test_opencv()
    test_imutils()
    print_report()
