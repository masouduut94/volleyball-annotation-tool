from ultralytics import YOLO


class AutoAnnotator:
    def __init__(self, db):
        self.db = db
        self.models = {}       # key -> (path, YOLO instance)

    def is_configured(self, key) -> bool:
        """
        Cheap check for UI status indicators (sidebar checkmarks). Reads
        only the DB path — never loads the model into memory. Previously
        this reused ensure_loaded(), which had the side effect of loading
        a full YOLO model purely to answer a yes/no question, and (worse)
        permanently caching whatever happened to be at that path at the
        time — see ensure_loaded() below for why that mattered.
        """
        return bool(self.db.get_model_path(key))

    def ensure_loaded(self, key):
        path = self.db.get_model_path(key)

        if not path:
            return None

        cached = self.models.get(key)
        # Reload if never loaded, OR if the configured path has changed
        # since the cached model was loaded. Without this check, changing
        # a model's path via ConfigDialog / the sidebar's inline picker
        # had no effect until the app was restarted — every Run kept
        # hitting the old model silently, which is exactly how you can
        # get a detection-only (boxes) result out of what the DB says is
        # a segmentation checkpoint.
        if cached is not None and cached[0] == path:
            return cached[1]

        model = YOLO(path)
        self.models[key] = (path, model)
        return model

    def predict(self, key, image):
        model = self.ensure_loaded(key)

        if model is None:
            raise RuntimeError(f"Model '{key}' is not configured.")

        return model(image, verbose=False)[0]