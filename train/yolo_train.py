"""
Train YOLO26 segmentation on volleyball court + volleyball lines.
Edit the settings below, then run:  python train_yolo26_seg_v3.py

Classes (defined in your data.yaml): volleyball_court, volleyball_lines

Why the parameters are set the way they are:
  - Court = one huge region, lines = very thin structures lying ON TOP of the court.
  - Lines are only a few pixels wide -> high imgsz and full-res masks (MASK_RATIO=1).
  - Lines overlap the court mask -> OVERLAP_MASK=False, otherwise the merged
    training mask punches holes in the court wherever a line is drawn.
  - Mosaic chops a court into pieces, which hurts the big-region class,
    so it is turned off earlier (CLOSE_MOSAIC) and scale jitter is moderate.
  - Cameras see the court in perspective, so small rotation/perspective/shear is
    useful, but vertical flips are not (a court is never upside down).
"""

from pathlib import Path

from ultralytics import YOLO

# ------------------------------------------------------------------
# Settings
# ------------------------------------------------------------------
DATA = "/home/masoud/Desktop/volleyball_datasets/Jersey Number detection yolov8/data.yaml"   # existing data.yaml

MODEL = "yolov8n.pt"      # yolo26n / s / m / l / x -seg.pt
RESUME_FROM = None            # e.g. "runs/segment/volleyball_court/weights/last.pt"

EPOCHS = 150
IMGSZ = 480                  # try 1280 if lines score low and VRAM allows
BATCH = -1                    # -1 = auto
DEVICE = "0"                  # "0", "0,1", "cpu", "mps"
WORKERS = 8
PATIENCE = 30
SEED = 0
CACHE = False                 # False, "ram" or "disk"
AMP = True

OPTIMIZER = "auto"
LR0 = 0.01
LRF = 0.01
MOMENTUM = 0.937
WEIGHT_DECAY = 0.0005
WARMUP_EPOCHS = 3.0
COS_LR = True                 # smooth decay helps fine-detail (lines) convergence

# # Segmentation
# OVERLAP_MASK = False          # lines overlap the court -> keep each mask separate
# MASK_RATIO = 1                # full-res masks (default 4 erases thin lines)

# Augmentation
HSV_H = 0.015                 # court colors vary by venue, but keep hue shifts small
HSV_S = 0.6
HSV_V = 0.4                   # lighting differences (indoor lights, sun glare)
DEGREES = 5.0                 # camera tilt
TRANSLATE = 0.1
SCALE = 0.4
SHEAR = 2.0
PERSPECTIVE = 0.0005          # court seen at an angle
FLIPUD = 0.0                  # never flip a court upside down
FLIPLR = 0.5                  # court is left/right symmetric
MOSAIC = 1.0
MIXUP = 0.0                   # blending images blurs thin lines
CLOSE_MOSAIC = 20             # last N epochs on full, un-mosaiced images

# Output
PROJECT = "/home/masoud/Desktop/projects/volleyball_analytics/src/vb_gui/vb_annotator/train/runs"
RUN_NAME = "volleyball_court"

# Post-training
RUN_FINAL_VAL = True
EXPORT_FORMAT = None          # e.g. "onnx", "engine", "openvino"; None to skip


# ------------------------------------------------------------------
# Script
# ------------------------------------------------------------------
def main():
    if RESUME_FROM:
        YOLO(RESUME_FROM).train(resume=True)
        return

    model = YOLO(MODEL)

    results = model.train(
        task="detect",
        data=DATA,
        epochs=EPOCHS,
        imgsz=IMGSZ,
        batch=BATCH,
        device=DEVICE,
        workers=WORKERS,
        patience=PATIENCE,
        seed=SEED,
        cache=CACHE,
        amp=AMP,
        optimizer=OPTIMIZER,
        lr0=LR0,
        lrf=LRF,
        momentum=MOMENTUM,
        weight_decay=WEIGHT_DECAY,
        warmup_epochs=WARMUP_EPOCHS,
        cos_lr=COS_LR,
        # overlap_mask=OVERLAP_MASK,
        # mask_ratio=MASK_RATIO,
        hsv_h=HSV_H,
        hsv_s=HSV_S,
        hsv_v=HSV_V,
        degrees=DEGREES,
        translate=TRANSLATE,
        scale=SCALE,
        shear=SHEAR,
        perspective=PERSPECTIVE,
        flipud=FLIPUD,
        fliplr=FLIPLR,
        mosaic=MOSAIC,
        mixup=MIXUP,
        close_mosaic=CLOSE_MOSAIC,
        project=PROJECT,
        name=RUN_NAME,
        plots=True,
    )

    best = Path(results.save_dir) / "weights" / "best.pt"
    print(f"\nBest weights: {best}")

    if RUN_FINAL_VAL and best.exists():
        metrics = YOLO(str(best)).val(data=DATA, imgsz=IMGSZ, device=DEVICE)
        print(f"Mask mAP50-95: {metrics.seg.map:.4f} | mAP50: {metrics.seg.map50:.4f}")

    if EXPORT_FORMAT and best.exists():
        print("Exported:", YOLO(str(best)).export(format=EXPORT_FORMAT, imgsz=IMGSZ))


if __name__ == "__main__":
    main()