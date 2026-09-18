from ultralytics import YOLO

from ultralytics import YOLO

try:
    import torch

    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False


class AutoAnnotator:
    def __init__(self, db):
        self.db = db
        self.models = {}  # key -> (path, YOLO instance)

    # ------------------------------------------------------------------
    # Configuration checks
    # ------------------------------------------------------------------

    def is_configured(self, key) -> bool:
        return bool(self.db.get_model_path(key))

    def ensure_loaded(self, key):
        path = self.db.get_model_path(key)

        if not path:
            return None

        cached = self.models.get(key)
        if cached is not None and cached[0] == path:
            return cached[1]

        model = YOLO(path)
        self.models[key] = (path, model)
        return model

    # ------------------------------------------------------------------
    # Single-frame (existing behaviour, kept for pose preview etc.)
    # ------------------------------------------------------------------

    def predict(self, key, image):
        model = self.ensure_loaded(key)

        if model is None:
            raise RuntimeError(f"Model '{key}' is not configured.")

        return model(image, verbose=False)[0]

    # ------------------------------------------------------------------
    # GPU / VRAM helpers
    # ------------------------------------------------------------------

    @staticmethod
    def gpu_available() -> bool:
        return _TORCH_AVAILABLE and torch.cuda.is_available()

    @staticmethod
    def free_vram_bytes() -> int:
        """
        Free VRAM on the current device in bytes, or 0 if no CUDA GPU is
        available. Uses mem_get_info() (free, total) which reflects what
        the driver can actually hand out right now — much more reliable
        than total VRAM, since other processes (viewer, browser, other
        Python kernels) may already be holding a chunk.
        """
        if not AutoAnnotator.gpu_available():
            return 0
        try:
            free, _total = torch.cuda.mem_get_info()
            return int(free)
        except Exception:
            return 0

    @staticmethod
    def _model_input_size(model) -> int:
        """
        Best-effort extraction of the model's inference imgsz. Falls back
        to 640, which is what Ultralytics uses when nothing is specified.
        """
        try:
            return int(model.model.args.get("imgsz", 640))
        except Exception:
            return 640

    @staticmethod
    def _is_segmentation(model) -> bool:
        """Segmentation checkpoints are heavier per-image than detection
        ones because of the mask head and protos."""
        try:
            return model.task == "segment"
        except Exception:
            return False

    def estimate_batch_size(
            self,
            key: str,
            safety_fraction: float = 0.7,
            min_batch: int = 1,
            max_batch: int = 64,
    ) -> int:
        """
        Pick a batch size that fits comfortably in current free VRAM.

        Approach: reserve `safety_fraction` of free VRAM for activations
        (the rest is cuDNN workspace, fragmentation, and whatever else the
        app is holding). Estimate per-image cost from image size and task
        type, then floor free_budget / per_image_cost.

        These per-image constants are deliberately conservative: for
        YOLOv8/v11 at 640px, a detection pass costs roughly 80–120 MB of
        peak activation memory per image on top of the weights, and a
        segmentation pass is ~2x that because of the mask head. If you
        swap in a much larger model, these numbers should be revisited.
        """
        if not self.gpu_available():
            return min_batch

        model = self.ensure_loaded(key)
        if model is None:
            return min_batch

        free = self.free_vram_bytes()
        if free <= 0:
            return min_batch

        imgsz = self._model_input_size(model)
        scale = (imgsz / 640.0) ** 2  # memory scales with pixel count

        base_mb = 120.0  # detection @ 640
        if self._is_segmentation(model):
            base_mb *= 2.0  # mask head + protos

        per_image_bytes = base_mb * scale * 1024 * 1024
        budget = free * safety_fraction

        estimate = int(budget // per_image_bytes)
        return max(min_batch, min(max_batch, estimate))

    # ------------------------------------------------------------------
    # Batched prediction
    # ------------------------------------------------------------------

    def predict_batch(self, key, images, batch_size: int = None, stream: bool = True):
        """
        Run inference on a list of images in batches.

        `images` is any iterable of numpy arrays (BGR, as read by cv2).

        Yields (image_index, result) pairs so the caller can map each
        result back to its source frame without needing to know how the
        batching was chunked internally.

        `stream=True` lets Ultralytics return results lazily as each
        batch finishes, which keeps peak memory low and lets the caller
        interleave DB writes with inference instead of waiting for the
        whole list to be done.

        If `batch_size` is None, it's auto-tuned to the current free VRAM.
        """
        model = self.ensure_loaded(key)

        if model is None:
            raise RuntimeError(f"Model '{key}' is not configured.")

        images = list(images)
        if not images:
            return

        if batch_size is None or batch_size < 1:
            batch_size = self.estimate_batch_size(key)

        for start in range(0, len(images), batch_size):
            chunk = images[start:start + batch_size]

            results = model(
                chunk,
                verbose=False,
                stream=stream,
                batch=len(chunk),
            )

            for offset, result in enumerate(results):
                yield start + offset, result
