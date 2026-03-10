import cv2
import time
import torch
import numpy as np
import tracemalloc
from ultralytics import YOLO
from datetime import datetime


PERSON_MODEL_PATH = "yolov8n.pt"
PPE_MODEL_PATH    = "yolov8n.pt"
TEST_VIDEO_PATH   = ""
ROI              = (100, 100, 600, 500)
RUNS             = 100


def load_models_full():
    person = YOLO(PERSON_MODEL_PATH).to("cuda")
    ppe    = YOLO(PPE_MODEL_PATH).to("cuda")
    return person, ppe


def load_models_half():
    person = YOLO(PERSON_MODEL_PATH).to("cuda")
    ppe    = YOLO(PPE_MODEL_PATH).to("cuda")
    dummy  = np.zeros((416, 416, 3), dtype=np.uint8)
    person.predict(dummy, imgsz=640, conf=0.3, device=0, half=True, verbose=False)
    ppe.predict(dummy,    imgsz=640, conf=0.3, device=0, half=True, verbose=False)
    return person, ppe


def run_inference_full(model, roi_crop):
    return model.predict(
        roi_crop,
        imgsz=640,
        conf=0.3,
        device=0,
        half=False,
        verbose=False
    )[0]


def run_inference_half(model, roi_crop):
    return model.predict(
        roi_crop,
        imgsz=640,
        conf=0.3,
        device=0,
        half=True,
        verbose=False
    )[0]


def sliding_window_buffer(best_frames, roi_index, score, annotated_frame):
    buffer = best_frames[roi_index]
    if len(buffer) < 3:
        buffer.append({"score": score, "frame": annotated_frame})
        buffer.sort(key=lambda x: x["score"], reverse=True)
    elif score > buffer[-1]["score"]:
        buffer[-1] = {"score": score, "frame": annotated_frame}
        buffer.sort(key=lambda x: x["score"], reverse=True)
    best_frames[roi_index] = buffer


def init_frame_pool(h, w, pool_size=3):
    return [np.zeros((h, w, 3), dtype=np.uint8) for _ in range(pool_size)]


def get_pooled_frame(pool, pool_index, source):
    idx = pool_index % len(pool)
    np.copyto(pool[idx], source)
    return pool[idx]


def frame_pool_buffer(best_frames, pool, pool_index, roi_index, score, source_frame):
    buffer = best_frames[roi_index]
    if len(buffer) < 3:
        pooled = get_pooled_frame(pool, pool_index[roi_index], source_frame)
        pool_index[roi_index] += 1
        buffer.append({"score": score, "frame": pooled})
        buffer.sort(key=lambda x: x["score"], reverse=True)
    elif score > buffer[-1]["score"]:
        pooled = get_pooled_frame(pool, pool_index[roi_index], source_frame)
        pool_index[roi_index] += 1
        buffer[-1] = {"score": score, "frame": pooled}
        buffer.sort(key=lambda x: x["score"], reverse=True)
    best_frames[roi_index] = buffer


def get_vram_mb():
    return torch.cuda.memory_allocated() / 1024 / 1024


def get_vram_peak_mb():
    return torch.cuda.max_memory_allocated() / 1024 / 1024


def benchmark(label, model, roi_crop, use_half, use_pool, frame_h, frame_w):
    print(f"\n--- {label} ---")

    torch.cuda.reset_peak_memory_stats()
    torch.cuda.empty_cache()
    tracemalloc.start()

    best_frames = {0: []}
    pool        = init_frame_pool(frame_h, frame_w) if use_pool else None
    pool_index  = {0: 0}

    times = []

    for run in range(RUNS):
        t0 = time.perf_counter()

        if use_half:
            res = run_inference_half(model, roi_crop)
        else:
            res = run_inference_full(model, roi_crop)

        score = float(run) / RUNS

        if use_pool:
            frame_pool_buffer(best_frames, pool, pool_index, 0, score, roi_crop)
        else:
            annotated = roi_crop.copy()
            sliding_window_buffer(best_frames, 0, score, annotated)

        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000)

    current_ram, peak_ram = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    avg_ms    = sum(times) / len(times)
    min_ms    = min(times)
    max_ms    = max(times)
    vram_mb   = get_vram_mb()
    vram_peak = get_vram_peak_mb()
    ram_peak  = peak_ram / 1024 / 1024

    print(f"Avg inference : {avg_ms:.2f} ms")
    print(f"Min inference : {min_ms:.2f} ms")
    print(f"Max inference : {max_ms:.2f} ms")
    print(f"VRAM current  : {vram_mb:.1f} MB")
    print(f"VRAM peak     : {vram_peak:.1f} MB")
    print(f"RAM peak      : {ram_peak:.2f} MB")

    return {
        "label":      label,
        "avg_ms":     avg_ms,
        "min_ms":     min_ms,
        "max_ms":     max_ms,
        "vram_mb":    vram_mb,
        "vram_peak":  vram_peak,
        "ram_peak_mb": ram_peak
    }


def print_summary(results):
    print("\n")
    print("=" * 65)
    print(f"{'Approach':<30} {'Avg ms':>8} {'VRAM MB':>10} {'RAM MB':>10}")
    print("=" * 65)
    for r in results:
        print(f"{r['label']:<30} {r['avg_ms']:>8.2f} {r['vram_peak']:>10.1f} {r['ram_peak_mb']:>10.2f}")
    print("=" * 65)

    fastest  = min(results, key=lambda x: x['avg_ms'])
    low_vram = min(results, key=lambda x: x['vram_peak'])
    low_ram  = min(results, key=lambda x: x['ram_peak_mb'])

    print(f"\nFastest inference : {fastest['label']} ({fastest['avg_ms']:.2f} ms)")
    print(f"Lowest VRAM       : {low_vram['label']} ({low_vram['vram_peak']:.1f} MB)")
    print(f"Lowest RAM        : {low_ram['label']} ({low_ram['ram_peak_mb']:.2f} MB)")


def main():
    if TEST_VIDEO_PATH:
        cap   = cv2.VideoCapture(TEST_VIDEO_PATH)
        ret, frame = cap.read()
        cap.release()
        if not ret:
            print("Could not read video, using dummy frame")
            frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    else:
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

    x1, y1, x2, y2 = ROI
    roi_crop        = frame[y1:y2, x1:x2]
    frame_h, frame_w = frame.shape[:2]

    print("Loading models ")
    model_full = load_models_full()
    model_half = load_models_half()

    print(f"Running {RUNS} inference passes per approach...")

    results = []

    results.append(benchmark(
        "Full precision + copy",
        model_full[0], roi_crop,
        use_half=False, use_pool=False,
        frame_h=frame_h, frame_w=frame_w
    ))

    results.append(benchmark(
        "Half precision + copy",
        model_half[0], roi_crop,
        use_half=True, use_pool=False,
        frame_h=frame_h, frame_w=frame_w
    ))

    results.append(benchmark(
        "Full precision + pool",
        model_full[0], roi_crop,
        use_half=False, use_pool=True,
        frame_h=frame_h, frame_w=frame_w
    ))

    results.append(benchmark(
        "Half precision + pool",
        model_half[0], roi_crop,
        use_half=True, use_pool=True,
        frame_h=frame_h, frame_w=frame_w
    ))

    print_summary(results)


if __name__ == "__main__":
    main()