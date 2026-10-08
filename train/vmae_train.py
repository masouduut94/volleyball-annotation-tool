"""
VideoMAE (v1 or v2) fine-tuning on volleyball events, following the PyTorchVideo
classification tutorial (https://pytorchvideo.org/docs/tutorial_classification).

Splits: train / val / test (stratified per class).
    HOLDOUT_RATIO = fraction of all videos kept out of training
    VAL_FRAC      = share of the hold-out used for validation   (e.g. 0.3)
    TEST_FRAC     = share of the hold-out used for testing      (e.g. 0.7)
    VAL_FRAC + TEST_FRAC must equal 1.

Outputs (under OUTPUT_DIR):
    splits.json                      which video is in train / val / test
    checkpoints/                     best Lightning checkpoint (by val_acc)
    epoch_01/ epoch_02/ ...          per-epoch: metrics.json, confusion_val.csv,
                                     per_class_val.csv, (optional) model.pt
    history.csv                      one row per epoch
    test/                            metrics.json, confusion_test.csv, per_class_test.csv
    <OUTPUT_PATH>                    best model exported as a single file

Install:
    pip install torch torchvision transformers timm av pytorchvideo pytorch_lightning

Usage: edit the settings in the `if __name__ == "__main__":` block and run
    python train_videomae_pytorchvideo.py
"""
import csv
import json
import math
import random
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

# --- compatibility shim ------------------------------------------------------
# The PyPI release of pytorchvideo imports `torchvision.transforms.functional_tensor`,
# which was removed in torchvision >= 0.17. Alias it so the import works.
try:
    import torchvision.transforms.functional_tensor  # noqa: F401
except ImportError:
    import torchvision.transforms.functional as _tvF
    sys.modules["torchvision.transforms.functional_tensor"] = _tvF
# -----------------------------------------------------------------------------

import pytorch_lightning as pl
from pytorch_lightning.callbacks import Callback, ModelCheckpoint
from pytorchvideo.data import LabeledVideoDataset, make_clip_sampler
from pytorchvideo.data.clip_sampling import UniformClipSampler
from pytorchvideo.transforms import (
    ApplyTransformToKey,
    Normalize,
    RandomShortSideScale,
    ShortSideScale,
    UniformTemporalSubsample,
)
from torch.utils.data import DataLoader, RandomSampler, SequentialSampler
from torchvision.transforms import CenterCrop, Compose, Lambda, RandomCrop, RandomHorizontalFlip
from transformers import AutoConfig, AutoModel, VideoMAEForVideoClassification

CLASSES = ["in_play", "no_play", "service"]
VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
IMAGENET_MEAN = (0.485, 0.456, 0.406)   # VideoMAE uses ImageNet stats (the tutorial's 0.45/0.225 is for ResNet)
IMAGENET_STD = (0.229, 0.224, 0.225)
DEFAULT_MODELS = {1: "MCG-NJU/videomae-base", 2: "OpenGVLab/VideoMAEv2-Base"}


# =========================================================================== #
# Data
# =========================================================================== #
def list_videos(root):
    items = []
    for label, cls in enumerate(CLASSES):
        files = sorted(p for p in (Path(root) / cls).rglob("*") if p.suffix.lower() in VIDEO_EXTS)
        items += [(str(p), label) for p in files]
        print(f"{cls:12s}: {len(files)} videos")
    return items


def stratified_split_3way(items, holdout_ratio, val_frac, test_frac, seed):
    """Per class: take `holdout_ratio` of the videos out of training, then split that
    hold-out into val (`val_frac`) and test (`test_frac`). Each class keeps at least
    one video in val and one in test when it has enough videos."""
    assert abs(val_frac + test_frac - 1.0) < 1e-6, "val_frac + test_frac must equal 1"
    rng = random.Random(seed)
    train, val, test = [], [], []
    for label in range(len(CLASSES)):
        cls_items = [it for it in items if it[1] == label]
        rng.shuffle(cls_items)
        n_hold = min(len(cls_items), max(2, int(round(len(cls_items) * holdout_ratio))))
        n_val = max(1, int(round(n_hold * val_frac)))
        n_val = min(n_val, max(1, n_hold - 1))
        val += cls_items[:n_val]
        test += cls_items[n_val:n_hold]
        train += cls_items[n_hold:]
    return train, val, test


# Transforms are module-level callables (not lambdas) so DataLoader workers can pickle them.
class RandomFrameSubsample:
    """Train-time temporal sampling for a (C,T,H,W) clip: split the ~30 frames of the
    1-second clip into `n` segments and pick one random frame per segment."""

    def __init__(self, n):
        self.n = n

    def __call__(self, x):
        t = x.shape[1]
        seg = t / self.n
        idx = [min(int(seg * i + random.random() * seg), t - 1) for i in range(self.n)]
        return x[:, idx]


def to_float01(x):
    return x.float() / 255.0


class VolleyballDataModule(pl.LightningDataModule):
    def __init__(self, data_root, num_frames=16, image_size=224, clip_duration=1.0,
                 batch_size=8, num_workers=4, holdout_ratio=0.1, val_frac=0.3, test_frac=0.7,
                 seed=42, decoder="pyav"):
        super().__init__()
        self.data_root, self.num_frames, self.image_size = data_root, num_frames, image_size
        self.clip_duration, self.batch_size, self.num_workers = clip_duration, batch_size, num_workers
        self.holdout_ratio, self.val_frac, self.test_frac = holdout_ratio, val_frac, test_frac
        self.seed, self.decoder = seed, decoder
        self.train_items = self.val_items = self.test_items = None

    def setup(self, stage=None):
        if self.train_items is not None:
            return
        items = list_videos(self.data_root)
        self.train_items, self.val_items, self.test_items = stratified_split_3way(
            items, self.holdout_ratio, self.val_frac, self.test_frac, self.seed)
        n = len(items)
        print(f"train={len(self.train_items)} ({len(self.train_items)/n:.1%})  "
              f"val={len(self.val_items)} ({len(self.val_items)/n:.1%})  "
              f"test={len(self.test_items)} ({len(self.test_items)/n:.1%})")

    def save_splits(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump({name: [{"path": p, "label": CLASSES[l]} for p, l in items]
                       for name, items in [("train", self.train_items), ("val", self.val_items),
                                           ("test", self.test_items)]}, f, indent=2)

    @staticmethod
    def _as_labeled_paths(items):
        # (path, {"label": int}) -> each clip dict gets a "label" key, as in the tutorial
        return [(p, {"label": l}) for p, l in items]

    def _transform(self, train):
        short = int(self.image_size * 256 / 224)
        if train:
            video_tf = Compose([
                RandomFrameSubsample(self.num_frames),                 # 16 of ~30 frames
                Lambda(to_float01),
                Normalize(IMAGENET_MEAN, IMAGENET_STD),
                RandomShortSideScale(min_size=short, max_size=int(short * 1.25)),
                RandomCrop(self.image_size),
                RandomHorizontalFlip(p=0.5),
            ])
        else:
            video_tf = Compose([
                UniformTemporalSubsample(self.num_frames),
                Lambda(to_float01),
                Normalize(IMAGENET_MEAN, IMAGENET_STD),
                ShortSideScale(short),
                CenterCrop(self.image_size),
            ])
        return ApplyTransformToKey(key="video", transform=video_tf)

    def train_dataloader(self):
        ds = LabeledVideoDataset(
            labeled_video_paths=self._as_labeled_paths(self.train_items),
            clip_sampler=make_clip_sampler("random", self.clip_duration),   # random 1-s window
            video_sampler=RandomSampler,
            transform=self._transform(train=True),
            decode_audio=False,
            decoder=self.decoder,
        )
        return DataLoader(ds, batch_size=self.batch_size, num_workers=self.num_workers, pin_memory=True)

    def _eval_loader(self, items):
        # "uniform": every 1-s clip of each video. backpad_last keeps a video that is a
        # hair shorter than 1 s instead of silently dropping it.
        ds = LabeledVideoDataset(
            labeled_video_paths=self._as_labeled_paths(items),
            clip_sampler=UniformClipSampler(clip_duration=self.clip_duration, backpad_last=True),
            video_sampler=SequentialSampler,
            transform=self._transform(train=False),
            decode_audio=False,
            decoder=self.decoder,
        )
        return DataLoader(ds, batch_size=self.batch_size, num_workers=self.num_workers, pin_memory=True)

    def val_dataloader(self):
        return self._eval_loader(self.val_items)

    def test_dataloader(self):
        return self._eval_loader(self.test_items)


# =========================================================================== #
# Unified model (v1 / v2). Input: (B, C, T, H, W) -- the PyTorchVideo layout.
# =========================================================================== #
class VideoMAEClassifier(nn.Module):
    def __init__(self, version, model_name=None, num_classes=len(CLASSES), dropout=0.1,
                 num_frames=16, image_size=224):
        super().__init__()
        assert version in (1, 2), "version must be 1 or 2"
        self.version = version
        self.model_name = model_name or DEFAULT_MODELS[version]
        self.num_frames, self.image_size = num_frames, image_size

        if version == 1:
            self.model = VideoMAEForVideoClassification.from_pretrained(
                self.model_name,
                num_labels=num_classes,
                id2label=dict(enumerate(CLASSES)),
                label2id={c: i for i, c in enumerate(CLASSES)},
                ignore_mismatched_sizes=True,
            )
            self.num_frames = self.model.config.num_frames
            self.image_size = self.model.config.image_size
        else:
            config = AutoConfig.from_pretrained(self.model_name, trust_remote_code=True)
            self.backbone = AutoModel.from_pretrained(self.model_name, config=config,
                                                      trust_remote_code=True)
            if hasattr(self.backbone, "head"):       # we want pooled features, not its own logits
                self.backbone.head = nn.Identity()
            self.backbone.eval()
            with torch.no_grad():
                dummy = torch.zeros(1, 3, self.num_frames, image_size, image_size)
                feat_dim = self.backbone(dummy).shape[-1]
            self.head = nn.Sequential(nn.Dropout(dropout), nn.Linear(feat_dim, num_classes))

    def forward(self, x):                                     # x: (B,C,T,H,W)
        if self.version == 1:
            return self.model(pixel_values=x.permute(0, 2, 1, 3, 4)).logits   # HF wants (B,T,C,H,W)
        return self.head(self.backbone(x))                    # V2 remote code wants (B,C,T,H,W)

    def param_groups(self, lr, head_lr):
        if self.version == 1:
            head = list(self.model.classifier.parameters())
            fc_norm = getattr(self.model, "fc_norm", None)
            if fc_norm is not None:
                head += list(fc_norm.parameters())
        else:
            head = list(self.head.parameters())
        head_ids = {id(p) for p in head}
        body = [p for p in self.parameters() if id(p) not in head_ids]
        return [{"params": body, "lr": lr}, {"params": head, "lr": head_lr}]

    def save(self, path):
        torch.save({"state_dict": self.state_dict(), "version": self.version,
                    "model_name": self.model_name, "classes": CLASSES}, path)


# =========================================================================== #
# Metric helpers
# =========================================================================== #
def per_class_report(conf):
    """conf: (C,C) tensor, rows=true, cols=pred -> list of dict rows + macro-F1."""
    conf = conf.double()
    rows, f1s = [], []
    for i, cls in enumerate(CLASSES):
        tp = conf[i, i].item()
        fp = conf[:, i].sum().item() - tp
        fn = conf[i, :].sum().item() - tp
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        f1s.append(f1)
        rows.append({"class": cls, "precision": prec, "recall": rec, "f1": f1,
                     "support": int(conf[i, :].sum().item())})
    return rows, float(np.mean(f1s))


def write_conf_and_report(folder, stage, conf):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / f"confusion_{stage}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["true\\pred"] + CLASSES)
        for cls, row in zip(CLASSES, conf.tolist()):
            w.writerow([cls] + row)
    rows, macro_f1 = per_class_report(conf)
    with open(folder / f"per_class_{stage}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["class", "precision", "recall", "f1", "support"])
        w.writeheader()
        w.writerows(rows)
    return macro_f1


# =========================================================================== #
# LightningModule (the tutorial's VideoClassificationLightningModule)
# =========================================================================== #
class VideoClassificationLightningModule(pl.LightningModule):
    def __init__(self, version, model_name, class_weights, total_steps, lr=5e-5, head_lr=1e-3,
                 weight_decay=0.05, dropout=0.1, label_smoothing=0.1, num_frames=16, image_size=224):
        super().__init__()
        self.model = VideoMAEClassifier(version, model_name, len(CLASSES), dropout,
                                        num_frames, image_size)
        self.register_buffer("class_weights", class_weights)
        self.total_steps = total_steps
        self.lr, self.head_lr, self.weight_decay = lr, head_lr, weight_decay
        self.label_smoothing = label_smoothing
        self.val_conf = torch.zeros(len(CLASSES), len(CLASSES), dtype=torch.long)
        self.test_conf = torch.zeros(len(CLASSES), len(CLASSES), dtype=torch.long)

    def forward(self, x):
        return self.model(x)

    def _loss(self, logits, y):
        return F.cross_entropy(logits, y, weight=self.class_weights,
                               label_smoothing=self.label_smoothing)

    def training_step(self, batch, batch_idx):
        x, y = batch["video"], batch["label"]                 # (B,C,T,H,W), (B,)
        loss = self._loss(self.model(x), y)
        self.log("train_loss", loss, prog_bar=True, on_step=True, on_epoch=True,
                 batch_size=y.size(0))
        return loss

    # ---- validation ---------------------------------------------------------
    def on_validation_epoch_start(self):
        self.val_conf.zero_()

    def validation_step(self, batch, batch_idx):
        self._eval_step(batch, "val", self.val_conf)

    def on_validation_epoch_end(self):
        if not self.trainer.sanity_checking:
            print(f"\nval confusion (rows=true, cols=pred), order={CLASSES}\n{self.val_conf}")

    # ---- test ---------------------------------------------------------------
    def on_test_epoch_start(self):
        self.test_conf.zero_()

    def test_step(self, batch, batch_idx):
        self._eval_step(batch, "test", self.test_conf)

    def on_test_epoch_end(self):
        print(f"\ntest confusion (rows=true, cols=pred), order={CLASSES}\n{self.test_conf}")

    def _eval_step(self, batch, stage, conf):
        x, y = batch["video"], batch["label"]
        logits = self.model(x)
        loss = self._loss(logits, y)
        preds = logits.argmax(-1)
        for t, p in zip(y.cpu(), preds.cpu()):
            conf[t, p] += 1
        self.log(f"{stage}_loss", loss, prog_bar=True, batch_size=y.size(0))
        self.log(f"{stage}_acc", (preds == y).float().mean(), prog_bar=True, batch_size=y.size(0))

    def configure_optimizers(self):
        opt = torch.optim.AdamW(self.model.param_groups(self.lr, self.head_lr),
                                weight_decay=self.weight_decay)
        warmup = max(1, int(0.1 * self.total_steps))
        total = self.total_steps
        sched = torch.optim.lr_scheduler.LambdaLR(
            opt, lambda s: (s + 1) / warmup if s < warmup
            else 0.5 * (1 + math.cos(math.pi * (s - warmup) / max(1, total - warmup))))
        return {"optimizer": opt, "lr_scheduler": {"scheduler": sched, "interval": "step"}}


# =========================================================================== #
# Per-epoch results: output_dir/epoch_XX/{metrics.json, confusion_val.csv, per_class_val.csv, model.pt}
# =========================================================================== #
class EpochResultsSaver(Callback):
    def __init__(self, output_dir, save_weights=False):
        self.output_dir = Path(output_dir)
        self.save_weights = save_weights
        self.history_path = self.output_dir / "history.csv"

    def on_train_epoch_end(self, trainer, pl_module):
        # runs after validation for this epoch, so val_* and train_loss_epoch are available
        epoch = trainer.current_epoch + 1
        folder = self.output_dir / f"epoch_{epoch:02d}"
        folder.mkdir(parents=True, exist_ok=True)

        metrics = {k: float(v) for k, v in trainer.callback_metrics.items()}
        metrics["epoch"] = epoch
        metrics["val_macro_f1"] = write_conf_and_report(folder, "val", pl_module.val_conf)
        with open(folder / "metrics.json", "w") as f:
            json.dump(metrics, f, indent=2)
        if self.save_weights:
            pl_module.model.save(folder / "model.pt")

        write_header = not self.history_path.exists()
        cols = ["epoch", "train_loss_epoch", "val_loss", "val_acc", "val_macro_f1"]
        with open(self.history_path, "a", newline="") as f:
            w = csv.writer(f)
            if write_header:
                w.writerow(cols)
            w.writerow([metrics.get(c, "") for c in cols])
        print(f"[epoch {epoch}] results saved to {folder}")


# =========================================================================== #
# Run
# =========================================================================== #
if __name__ == "__main__":
    # ---- settings: edit these ------------------------------------------------
    """
    Version 1:
    Model Name                                |    Notes
    MCG-NJU/videomae-base                     |    Self-supervised pretrained only, best default for fine-tuning
    MCG-NJU/videomae-base-finetuned-kinetics  |    Base, already fine-tuned on Kinetics-400
    MCG-NJU/videomae-base-finetuned-ssv2      |    Base, fine-tuned on Something-Something v2 (motion-heavy)
    MCG-NJU/videomae-small-finetuned-kinetics |    Small, lighter and faster
    MCG-NJU/videomae-huge-finetuned-kinetics  |    Huge, heavy

    ==================================================
    Version 2
    Model name                  |   Notes
    OpenGVLab/VideoMAEv2-Base   |   Base, the default in my script
    OpenGVLab/VideoMAEv2-Large  |   Large, pretrained 800 epochs
    OpenGVLab/VideoMAEv2-Huge   |   Huge, pretrained 800 epochs
    OpenGVLab/VideoMAEv2-giant  |   Giant (~4 GB weights), pretrained 1200 epochs
    """

    DATA_ROOT = "/home/masoud/Desktop/volleyball_datasets/Gamestate/ALL_VIDEOS"   # contains active_play/, no_play/, breaks/, service/
    VERSION = 1                                 # 1 -> HF VideoMAE v1, 2 -> VideoMAE V2 (remote code)
    MODEL_NAME = "MCG-NJU/videomae-small-finetuned-kinetics"  # None = default for VERSION
    CLIP_DURATION = 1.0                         # seconds per clip (~30 frames at 30 fps)
    NUM_FRAMES = 16                             # frames fed to the model (keep 16 for V2)
    IMAGE_SIZE = 224                            # keep 224 for V2
    EPOCHS = 5
    BATCH_SIZE = 5
    LR = 5e-5                                   # backbone learning rate
    HEAD_LR = 1e-3                              # learning rate for the new classification head
    WEIGHT_DECAY = 0.05
    DROPOUT = 0.1                               # used by the V2 head
    LABEL_SMOOTHING = 0.1
    # --- splits ---
    HOLDOUT_RATIO = 0.10                        # fraction of all videos NOT used for training
    VAL_FRAC = 0.3                              # share of the hold-out used for validation
    TEST_FRAC = 0.7                             # share of the hold-out used for test (VAL_FRAC + TEST_FRAC = 1)
    # --- outputs ---
    OUTPUT_DIR = f"runs/videomae_v{VERSION}_volleyball"   # everything is saved here
    SAVE_EPOCH_WEIGHTS = True                  # True -> also save model.pt inside every epoch_XX folder
    OUTPUT_PATH = f"{OUTPUT_DIR}/videomae_torchvideo_v{VERSION}_volleyball.pt"
    NUM_WORKERS = 4
    DECODER = "pyav"                            # "pyav", "torchvision" or "decord"
    PRECISION = "16-mixed"                      # "bf16-mixed" on Ampere+; ignored on CPU
    SEED = 42
    # --------------------------------------------------------------------------

    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    pl.seed_everything(SEED, workers=True)

    data_module = VolleyballDataModule(
        DATA_ROOT, NUM_FRAMES, IMAGE_SIZE, CLIP_DURATION, BATCH_SIZE, NUM_WORKERS,
        HOLDOUT_RATIO, VAL_FRAC, TEST_FRAC, SEED, DECODER)
    data_module.setup()
    data_module.save_splits(Path(OUTPUT_DIR) / "splits.json")

    # class-weighted loss for imbalanced classes
    counts = np.bincount([l for _, l in data_module.train_items], minlength=len(CLASSES)).clip(min=1)
    class_weights = torch.tensor(counts.sum() / (len(CLASSES) * counts), dtype=torch.float)

    # PyTorchVideo datasets are iterable (no __len__), so explicitly
    # calculate the number of batches for Lightning's progress bars.
    steps_per_epoch = math.ceil(len(data_module.train_items) / BATCH_SIZE)

    def get_video_duration(path):
        """Return video duration in seconds using PyAV metadata."""
        import av

        container = av.open(path)
        try:
            stream = container.streams.video[0]

            if stream.duration is not None and stream.time_base is not None:
                return float(stream.duration * stream.time_base)

            # Fallback for files without stream.duration.
            if stream.frames and stream.average_rate:
                return float(stream.frames / stream.average_rate)

            # Last-resort fallback: container duration is in microseconds.
            if container.duration is not None:
                return float(container.duration / av.time_base)

            raise RuntimeError(f"Could not determine duration for: {path}")
        finally:
            container.close()

    def count_eval_clips(items, clip_duration):
        """
        Count the clips produced by UniformClipSampler(..., backpad_last=True).

        Validation and test use one clip per clip_duration interval, with the
        final shorter interval kept because backpad_last=True.
        """
        total_clips = 0

        for path, _ in items:
            duration = get_video_duration(path)

            # UniformClipSampler with backpad_last=True keeps the final
            # partial clip, so a video always contributes at least one clip.
            n_clips = max(1, math.ceil(duration / clip_duration))
            total_clips += n_clips

        return total_clips

    # Validation/test datasets use UniformClipSampler, so one video can
    # produce multiple clips. Calculate the actual number of clips first,
    # then convert clips to batches.
    val_clips = count_eval_clips(data_module.val_items, CLIP_DURATION)
    test_clips = count_eval_clips(data_module.test_items, CLIP_DURATION)

    val_batches = math.ceil(val_clips / BATCH_SIZE)
    test_batches = math.ceil(test_clips / BATCH_SIZE)

    print(
        f"batches per epoch: "
        f"train={steps_per_epoch}, "
        f"val={val_batches}, "
        f"test={test_batches}"
    )

    module = VideoClassificationLightningModule(
        VERSION, MODEL_NAME, class_weights, steps_per_epoch * EPOCHS,
        LR, HEAD_LR, WEIGHT_DECAY, DROPOUT, LABEL_SMOOTHING, NUM_FRAMES, IMAGE_SIZE)

    # V1 reads frames/size from the checkpoint config: make the data pipeline match
    data_module.num_frames = module.model.num_frames
    data_module.image_size = module.model.image_size

    ckpt_cb = ModelCheckpoint(dirpath=f"{OUTPUT_DIR}/checkpoints", monitor="val_acc", mode="max",
                              save_top_k=1,
                              filename=f"videomae_v{VERSION}" + "-{epoch:02d}-{val_acc:.3f}")
    epoch_cb = EpochResultsSaver(OUTPUT_DIR, save_weights=SAVE_EPOCH_WEIGHTS)
    use_gpu = torch.cuda.is_available()
    trainer = pl.Trainer(
        max_epochs=EPOCHS,
        accelerator="auto",
        devices=1,
        precision=PRECISION if use_gpu else "32-true",
        gradient_clip_val=1.0,
        callbacks=[ckpt_cb, epoch_cb],
        default_root_dir=OUTPUT_DIR,
        log_every_n_steps=10,

        # LabeledVideoDataset is iterable and has no __len__(), so Lightning
        # cannot infer the total number of batches for the progress bars.
        limit_train_batches=steps_per_epoch,
        limit_val_batches=val_batches,
        limit_test_batches=test_batches,
    )
    trainer.fit(module, data_module)

    # ---- final test with the best (by val_acc) checkpoint --------------------
    if ckpt_cb.best_model_path:
        test_res = trainer.test(module, data_module, ckpt_path="best")[0]
        test_dir = Path(OUTPUT_DIR) / "test"
        test_res["test_macro_f1"] = write_conf_and_report(test_dir, "test", module.test_conf)
        test_res["best_checkpoint"] = ckpt_cb.best_model_path
        with open(test_dir / "metrics.json", "w") as f:
            json.dump(test_res, f, indent=2)

        module.model.save(OUTPUT_PATH)              # weights of the best checkpoint are loaded now
        print(f"Best val_acc={ckpt_cb.best_model_score:.4f}  "
              f"test_acc={test_res.get('test_acc', float('nan')):.4f} -> {OUTPUT_PATH}")