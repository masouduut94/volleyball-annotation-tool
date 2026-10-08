"""
Inference for the VideoMAE checkpoints produced by train_videomae_unified.py (v1 or v2).

For every input video it writes a video with the SAME NAME into OUTPUT_DIR where each
1-second block is classified and the prediction (class + confidence) is drawn at the
top of the screen. A per-second CSV with all class probabilities is saved next to it.

How a video is processed (streaming, so long matches are fine):
    - the video is cut into consecutive 1-second blocks (round(fps) frames)
    - 16 frames are sampled from each block (segment centres, same as validation)
    - blocks are classified in batches of BATCH_SIZE (one forward pass for several seconds)
    - the block's frames are written with the label overlay
    - a last block shorter than 1 s is classified using the final 1 s of the video

Install:
    pip install torch torchvision transformers timm opencv-python numpy
    (optional) ffmpeg on PATH -> output is re-encoded to H.264 so it plays everywhere

Usage: edit the settings in the `if __name__ == "__main__":` block and run
    python infer_videomae.py
"""
import csv
import shutil
import subprocess
import time
from collections import deque
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
from torchvision.transforms import v2 as T
from transformers import AutoConfig, AutoModel, VideoMAEForVideoClassification

VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
DEFAULT_CLASSES = ["in_play", "no_play", "service"]
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)
# BGR colours cycled per class index
PALETTE = [(60, 200, 60), (170, 170, 170), (0, 165, 255), (255, 120, 40), (200, 60, 200), (60, 60, 230)]


# =========================================================================== #
# Model (same layout / attribute names as in the training script -> same state_dict keys)
# =========================================================================== #
class VideoMAEClassifier(nn.Module):
    """forward(x): x is (B, T, C, H, W) -> logits (B, num_classes)."""

    def __init__(self, version, model_name, classes, num_frames=16, image_size=224, dropout=0.1):
        super().__init__()
        assert version in (1, 2), "version must be 1 or 2"
        self.version, self.num_frames, self.image_size = version, num_frames, image_size
        num_classes = len(classes)

        if version == 1:
            self.model = VideoMAEForVideoClassification.from_pretrained(
                model_name, num_labels=num_classes,
                id2label=dict(enumerate(classes)), label2id={c: i for i, c in enumerate(classes)},
                ignore_mismatched_sizes=True)
            self.num_frames = self.model.config.num_frames
            self.image_size = self.model.config.image_size
        else:
            config = AutoConfig.from_pretrained(model_name, trust_remote_code=True)
            self.backbone = AutoModel.from_pretrained(model_name, config=config, trust_remote_code=True)
            if hasattr(self.backbone, "head"):
                self.backbone.head = nn.Identity()
            self.backbone.eval()
            with torch.no_grad():
                feat_dim = self.backbone(torch.zeros(1, 3, num_frames, image_size, image_size)).shape[-1]
            self.head = nn.Sequential(nn.Dropout(dropout), nn.Linear(feat_dim, num_classes))

    def forward(self, x):
        if self.version == 1:
            return self.model(pixel_values=x).logits
        return self.head(self.backbone(x.permute(0, 2, 1, 3, 4)))


def load_model(checkpoint, device):
    """Rebuild the architecture from the checkpoint metadata and load the fine-tuned weights.
    (The base pretrained weights are fetched from the HF cache first, then overwritten.)"""
    ckpt = torch.load(checkpoint, map_location="cpu", weights_only=False)
    classes = ckpt.get("classes", DEFAULT_CLASSES)
    model = VideoMAEClassifier(
        ckpt["version"], ckpt["model_name"], classes,
        ckpt.get("num_frames", 16), ckpt.get("image_size", 224))
    model.load_state_dict(ckpt["state_dict"])
    model.to(device).eval()
    meta = {"classes": classes, "version": ckpt["version"], "model_name": ckpt["model_name"],
            "mean": ckpt.get("mean", IMAGENET_MEAN), "std": ckpt.get("std", IMAGENET_STD)}
    print(f"Loaded VideoMAE v{meta['version']} ({meta['model_name']}) | classes={classes} | "
          f"{model.num_frames} frames @ {model.image_size}px"
          + (f" | trained epoch {ckpt['epoch']}, val_acc {ckpt['val_acc']:.4f}" if "epoch" in ckpt else ""))
    return model, meta


# =========================================================================== #
# Pre-processing (identical to validation in the training script)
# =========================================================================== #
def sample_indices(n_avail, num_frames):
    seg = n_avail / num_frames
    return [min(max(int(seg * i + seg / 2), 0), n_avail - 1) for i in range(num_frames)]


class Preprocessor:
    def __init__(self, num_frames, image_size, mean, std):
        self.num_frames = num_frames
        short = int(image_size * 256 / 224)
        self.tf = T.Compose([T.Resize(short, antialias=True), T.CenterCrop(image_size)])
        self.mean = torch.tensor(mean).view(1, 3, 1, 1)
        self.std = torch.tensor(std).view(1, 3, 1, 1)

    def __call__(self, frames_bgr):
        """frames_bgr: list of BGR uint8 frames (the 1-s context) -> (1, T, C, H, W) tensor."""
        idx = sample_indices(len(frames_bgr), self.num_frames)
        clip = np.stack([cv2.cvtColor(frames_bgr[i], cv2.COLOR_BGR2RGB) for i in idx])
        clip = torch.from_numpy(clip).permute(0, 3, 1, 2)
        clip = self.tf(clip).float() / 255.0
        return ((clip - self.mean) / self.std).unsqueeze(0)


# =========================================================================== #
# Drawing
# =========================================================================== #
def draw_overlay(frame, label, conf, color, t_start, t_end, probs_line=None):
    """Dark banner at the top with the prediction; returns a new frame."""
    out = frame.copy()
    h, w = out.shape[:2]
    scale = max(0.5, h / 720.0)
    thick = max(1, int(round(2 * scale)))
    main = f"{label}  {conf * 100:.1f}%"
    sub = f"{t_start:.0f}s - {t_end:.0f}s" + (f"   |   {probs_line}" if probs_line else "")

    (mw, mh), _ = cv2.getTextSize(main, cv2.FONT_HERSHEY_SIMPLEX, 1.1 * scale, thick + 1)
    sub_scale = 0.55 * scale
    (sw, sh), _ = cv2.getTextSize(sub, cv2.FONT_HERSHEY_SIMPLEX, sub_scale, max(1, thick - 1))
    if sw > w - 20:                                   # shrink the second line to fit narrow videos
        sub_scale *= (w - 20) / sw
        (sw, sh), _ = cv2.getTextSize(sub, cv2.FONT_HERSHEY_SIMPLEX, sub_scale, max(1, thick - 1))

    pad = int(10 * scale)
    banner_h = pad * 3 + mh + sh
    out[:banner_h] = (out[:banner_h] * 0.35).astype(np.uint8)
    cv2.putText(out, main, (pad, pad + mh), cv2.FONT_HERSHEY_SIMPLEX, 1.1 * scale, color,
                thick + 1, cv2.LINE_AA)
    cv2.putText(out, sub, (pad, pad * 2 + mh + sh), cv2.FONT_HERSHEY_SIMPLEX, sub_scale,
                (255, 255, 255), max(1, thick - 1), cv2.LINE_AA)
    return out


def reencode_h264(tmp_path, final_path, audio_source):
    """Optional: H.264 re-encode (+ original audio when present). Returns True on success."""
    if shutil.which("ffmpeg") is None:
        return False
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp_path), "-i", str(audio_source),
           "-map", "0:v:0", "-map", "1:a:0?", "-c:v", "libx264", "-pix_fmt", "yuv420p",
           "-crf", "20", "-c:a", "aac", "-shortest", str(final_path)]
    return subprocess.run(cmd).returncode == 0


# =========================================================================== #
# Inference on one video
# =========================================================================== #
@torch.inference_mode()
def process_video(
    model, 
    meta, 
    pre, 
    video_path, 
    output_dir, 
    device, 
    window_seconds=1.0,
    show_all_probs=True, 
    reencode=True, 
    use_fp16=True, 
    batch_size=8
    ):
    video_path, output_dir = Path(video_path), Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / (video_path.stem + ".mp4")            # same name as the input
    if out_path.resolve() == video_path.resolve():                # never overwrite the source
        out_path = output_dir / (video_path.stem + "_pred.mp4")
    csv_path = out_path.with_name(out_path.stem + "_predictions.csv")
    classes = meta["classes"]

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    fps = fps if fps and fps > 1 else 30.0
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    win = max(1, int(round(fps * window_seconds)))
    n_windows = int(np.ceil(total_frames / win)) if total_frames > 0 else 0

    tmp_path = out_path.with_name(out_path.stem + "_tmp.mp4")
    writer = cv2.VideoWriter(str(tmp_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

    buffer, recent = [], deque(maxlen=win)      # frames of the current block / last `win` frames
    pending = []                                # finished blocks waiting for a batched forward pass
    records, frame_no, t0 = [], 0, time.time()
    autocast = torch.autocast("cuda", dtype=torch.float16, enabled=use_fp16 and device == "cuda")

    def flush():
        """ONE forward pass over all pending blocks, then write them out in order."""
        if not pending:
            return
        x = torch.cat([p["x"] for p in pending]).to(device, non_blocking=True)   # (B,T,C,H,W)
        with autocast:
            logits = model(x)
        probs_all = torch.softmax(logits.float(), -1).cpu().numpy()               # (B,C)
        for p, probs in zip(pending, probs_all):
            k = int(probs.argmax())
            label, conf = classes[k], float(probs[k])
            start_f, end_f = p["start"], p["start"] + len(p["frames"])
            t_start, t_end = start_f / fps, end_f / fps
            probs_line = "  ".join(f"{c}:{q:.2f}" for c, q in zip(classes, probs)) if show_all_probs else None
            color = PALETTE[k % len(PALETTE)]
            for f in p["frames"]:
                writer.write(draw_overlay(f, label, conf, color, t_start, t_end, probs_line))

            records.append({"block": len(records), "start_frame": start_f, "end_frame": end_f - 1,
                            "start_s": round(t_start, 3), "end_s": round(t_end, 3),
                            "label": label, "confidence": round(conf, 4),
                            **{f"p_{c}": round(float(q), 4) for c, q in zip(classes, probs)}})
            print(f"  block {len(records):4d}/{n_windows or '?'}  {t_start:7.1f}s-{t_end:7.1f}s  "
                  f"{label:12s} {conf * 100:5.1f}%")
        pending.clear()

    print(f"\n{video_path.name}: {w}x{h} @ {fps:.2f} fps, {total_frames} frames, "
          f"~{n_windows} x {window_seconds:g}s blocks, batch={batch_size}")
    frame_no = 0
    while True:
        ok, frame = cap.read()
        if ok:
            buffer.append(frame)
            recent.append(frame)
        if buffer and (len(buffer) == win or not ok):
            # 1-s context ending at this block (the tail block reuses the last full second)
            pending.append({"frames": buffer, "x": pre(list(recent)), "start": frame_no})
            frame_no += len(buffer)
            buffer = []
            if len(pending) >= batch_size:
                flush()
        if not ok:
            break
    flush()                                     # remaining blocks (incl. the tail block)
    cap.release()
    writer.release()

    if records:
        with open(csv_path, "w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=list(records[0].keys()))
            wr.writeheader()
            wr.writerows(records)

    if reencode and reencode_h264(tmp_path, out_path, video_path):
        tmp_path.unlink(missing_ok=True)
    else:
        if reencode:
            print("  (ffmpeg not available / failed: keeping the mp4v file, no audio)")
        tmp_path.replace(out_path)

    dt = time.time() - t0
    print(f"  saved {out_path}  |  {csv_path.name}  |  {dt:.0f}s ({len(records) / max(dt, 1e-9):.2f} blocks/s)")
    return records


# =========================================================================== #
# Run
# =========================================================================== #
if __name__ == "__main__":
    # ---- settings: edit these ------------------------------------------------
    CHECKPOINT = "/home/masoud/Desktop/projects/volleyball_analytics/src/vb_gui/vb_annotator/train/videomae_torchvideo_v1_volleyball.pt"   # .pt from the training script (v1 or v2)
    VIDEO_PATH = "/home/masoud/Desktop/projects/volleyball_analytics/videos/full_matches/out.mp4"              # a video file, or a folder of videos
    OUTPUT_DIR = "inference_output"                      # annotated videos are written here
    WINDOW_SECONDS = 1.0                                 # classify block by block
    SHOW_ALL_PROBS = True                                # also print every class probability
    REENCODE_H264 = True                                 # needs ffmpeg on PATH; else mp4v is kept
    USE_FP16 = True                                      # half precision on GPU
    BATCH_SIZE = 64                                       # 1-s blocks per forward pass. RAM ~ BATCH_SIZE x fps x
                                                         # frame size (1080p@30fps ~ 0.18 GB per block); lower it for 4K
    DEVICE = None                                        # None = auto (cuda if available)
    # --------------------------------------------------------------------------

    device = DEVICE or ("cuda" if torch.cuda.is_available() else "cpu")
    model, meta = load_model(CHECKPOINT, device)
    pre = Preprocessor(model.num_frames, model.image_size, meta["mean"], meta["std"])

    src = Path(VIDEO_PATH)
    videos = sorted(p for p in src.rglob("*") if p.suffix.lower() in VIDEO_EXTS) if src.is_dir() else [src]
    if not videos:
        raise SystemExit(f"No videos found in {src}")

    for v in videos:
        process_video(model, meta, pre, v, OUTPUT_DIR, device, WINDOW_SECONDS,
                      SHOW_ALL_PROBS, REENCODE_H264, USE_FP16, BATCH_SIZE)