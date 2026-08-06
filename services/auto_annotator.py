from ultralytics import YOLO


class AutoAnnotator:
    def __init__(self, db):
        self.db = db
        self.models = {}

    def ensure_loaded(self, key):
        if key in self.models:
            return self.models[key]

        path = self.db.get_model_path(key)

        if not path:
            return None

        model = YOLO(path)
        self.models[key] = model
        return model

    def predict(self, key, image):
        model = self.ensure_loaded(key)

        if model is None:
            raise RuntimeError(f"Model '{key}' is not configured.")

        return model(image, verbose=False)[0]
