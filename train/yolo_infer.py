import os
import cv2
import numpy as np
from ultralytics import YOLO
from tqdm import tqdm

# ---------------- Settings (edit these) ----------------
VIDEO_PATH = "/home/masoud/Desktop/projects/volleyball_analytics/videos/2026_s.mp4"
MODEL_PATH = "/home/masoud/Desktop/projects/volleyball_analytics/src/vb_gui/vb_annotator/train/runs/volleyball_court-2/weights/best.pt"   # segmentation or detection model
OUTPUT_DIR = "/home/masoud/Desktop/projects/volleyball_analytics/src/vb_gui/vb_annotator/train/inference_output"
CONF = 0.25
MASK_ALPHA = 0.4
BATCH_SIZE = 256
# --------------------------------------------------------


def color_for(class_id):
    """Deterministic color per class."""
    rng = np.random.RandomState(class_id * 7 + 3)
    return tuple(int(c) for c in rng.randint(50, 255, 3))


def draw_label(frame, text, x, y, color):
    (tw, th), base = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    y = max(y, th + base)
    cv2.rectangle(frame, (x, y - th - base), (x + tw, y + base // 2), color, -1)
    cv2.putText(frame, text, (x, y - base // 2), cv2.FONT_HERSHEY_SIMPLEX,
                0.5, (255, 255, 255), 1, cv2.LINE_AA)


def draw_results(frame, result, names):
    # Segmentation model: draw masks + label names
    if result.masks is not None:
        overlay = frame.copy()
        classes = result.boxes.cls.int().tolist()
        polygons = result.masks.xy  # list of Nx2 arrays in pixel coords

        for poly, cls in zip(polygons, classes):
            if len(poly) == 0:
                continue
            cv2.fillPoly(overlay, [poly.astype(np.int32)], color_for(cls))
        frame = cv2.addWeighted(overlay, MASK_ALPHA, frame, 1 - MASK_ALPHA, 0)

        for poly, cls in zip(polygons, classes):
            if len(poly) == 0:
                continue
            color = color_for(cls)
            pts = poly.astype(np.int32)
            cv2.polylines(frame, [pts], True, color, 2)
            x, y = pts[:, 0].min(), pts[:, 1].min()
            draw_label(frame, names[cls], int(x), int(y), color)

    # Detection model: draw bounding boxes + label names
    elif result.boxes is not None:
        for box in result.boxes:
            cls = int(box.cls[0])
            conf = float(box.conf[0])
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            color = color_for(cls)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            draw_label(frame, f"{names[cls]} {conf:.2f}", x1, y1, color)

    return frame


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    model = YOLO(MODEL_PATH)

    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        raise IOError(f"Cannot open video: {VIDEO_PATH}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or None

    name = os.path.splitext(os.path.basename(VIDEO_PATH))[0]
    out_path = os.path.join(OUTPUT_DIR, f"{name}_result.mp4")
    writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

    def process_batch(frames):
        results = model.predict(frames, conf=CONF, batch=BATCH_SIZE, verbose=False)
        for frame, result in zip(frames, results):
            writer.write(draw_results(frame, result, model.names))
        pbar.update(len(frames))

    with tqdm(total=total, desc="Processing", unit="frame") as pbar:
        batch = []
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            batch.append(frame)
            if len(batch) == BATCH_SIZE:
                process_batch(batch)
                batch = []

        if batch:  # leftover frames (last partial batch)
            process_batch(batch)

    cap.release()
    writer.release()
    print(f"Done. Saved to {out_path}")


if __name__ == "__main__":
    main()
