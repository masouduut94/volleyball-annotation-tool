from collections import OrderedDict
from pathlib import Path

import cv2
import yaml


class YOLOExporter:

    def __init__(self, db):

        self.db = db
        self.captures = {}

    # ==========================================================
    # Public API
    # ==========================================================

    def export(
            self,
            output_dir,
            mode,
            output_format,
            selected_layers,
            selected_labels,
            selected_videos,
    ):

        try:
            output_dir = Path(output_dir)

            output_dir.mkdir(
                parents=True,
                exist_ok=True
            )

            label_set = {
                (layer, label)
                for layer, label in selected_labels
            }

            if mode == "combined":

                self._export_dataset(
                    dataset_dir=output_dir / "dataset",
                    output_format=output_format,
                    selected_layers=selected_layers,
                    selected_labels=label_set,
                    selected_videos=selected_videos,
                )

            else:

                for layer_name in selected_layers:

                    layer_labels = {
                        (layer, label)
                        for layer, label in label_set
                        if layer == layer_name
                    }

                    if not layer_labels:
                        continue

                    self._export_dataset(
                        dataset_dir=(
                                output_dir / layer_name
                        ),
                        output_format=output_format,
                        selected_layers=[layer_name],
                        selected_labels=layer_labels,
                        selected_videos=selected_videos,
                    )

        finally:
            self._release_captures()

    # ==========================================================
    # Dataset
    # ==========================================================

    def _export_dataset(
            self,
            dataset_dir,
            output_format,
            selected_layers,
            selected_labels,
            selected_videos,
    ):

        dataset_dir.mkdir(parents=True, exist_ok=True)

        images_dir = (dataset_dir / "images")
        labels_dir = (dataset_dir / "labels")
        images_dir.mkdir(exist_ok=True)
        labels_dir.mkdir(exist_ok=True)

        # ------------------------------------------------------
        # Collect annotations
        # ------------------------------------------------------

        all_annotations = []

        for video_path in selected_videos:

            annotations = self.db.get_media_annotations(video_path)

            for ann in annotations:

                if ann.layer.name not in selected_layers:
                    continue

                if (ann.layer.name, ann.label.name) not in selected_labels:
                    continue

                all_annotations.append(ann)

        if not all_annotations:
            return

        # ------------------------------------------------------
        # Class mapping
        # ------------------------------------------------------

        class_names = OrderedDict()

        for ann in all_annotations:

            key = ann.label.name

            if key not in class_names:
                class_names[key] = len(class_names)

        # ------------------------------------------------------
        # Group by video + frame
        # ------------------------------------------------------

        grouped = {}

        for ann in all_annotations:
            key = (ann.media_name, ann.frame_number)

            grouped.setdefault(key, []).append(ann)

        # ------------------------------------------------------
        # Export frames
        # ------------------------------------------------------

        for frame_index, (
                (video_path, frame_number),
                annotations,
        ) in enumerate(grouped.items()):

            image_name = self._image_name(video_path, frame_number, frame_index)

            image_path = (images_dir / image_name)

            label_path = (labels_dir / f"{Path(image_name).stem}.txt")

            width, height = self._export_frame(video_path,frame_number,image_path)

            if width is None:
                continue

            lines = []

            for ann in annotations:

                class_id = class_names[ann.label.name]

                if output_format == "segmentation":

                    points = self._polygon_points(ann)

                    if len(points) < 3:
                        continue

                    values = [str(class_id)]

                    for x, y in points:
                        values.append(self._fmt(x / width))

                        values.append(self._fmt(y / height))

                    lines.append(" ".join(values))

                else:

                    bbox = self._bbox(ann, width, height)

                    if bbox is None:
                        continue

                    xc, yc, w, h = bbox

                    lines.append(
                        " ".join(
                            [
                                str(class_id),
                                self._fmt(xc),
                                self._fmt(yc),
                                self._fmt(w),
                                self._fmt(h),
                            ]
                        )
                    )

            if lines:
                label_path.write_text("\n".join(lines), encoding="utf-8")
            else:
                # Do not keep an image with no
                # valid annotations.
                if image_path.exists():
                    image_path.unlink()

        # ------------------------------------------------------
        # data.yaml
        # ------------------------------------------------------

        data = {
            "path": str(dataset_dir.resolve()),
            "train": "images",
            "val": "images",
            "names": dict(class_names),
        }

        if output_format == 'segmentation':
            data["task"] = "segment"
        else:
            data["task"] = "detect"

        with open(dataset_dir / "data.yaml", "w", encoding="utf-8") as f:

            yaml.safe_dump(data, f, sort_keys=False)

    # ==========================================================
    # Frame extraction
    # ==========================================================

    def _export_frame(
            self,
            video_path,
            frame_number,
            output_path,
    ):
        if video_path not in self.captures:
            self.captures[video_path] = cv2.VideoCapture(video_path)

        cap = self.captures[video_path]

        if not cap.isOpened():
            return None, None

        cap.set(
            cv2.CAP_PROP_POS_FRAMES,
            frame_number,
        )

        ok, frame = cap.read()

        if not ok or frame is None:
            return None, None

        height, width = frame.shape[:2]

        cv2.imwrite(
            str(output_path),
            frame,
        )

        return width, height

    def _release_captures(self):
        for cap in self.captures.values():
            if cap is not None:
                cap.release()

        self.captures.clear()

    # ==========================================================
    # Geometry
    # ==========================================================

    @staticmethod
    def _polygon_points(ann):

        if ann.shape_type == "polygon":
            return [
                (float(x), float(y))
                for x, y in ann.geometry
            ]

        if ann.shape_type == "rectangle":
            g = ann.geometry

            x = float(g["x"])
            y = float(g["y"])
            w = float(g["width"])
            h = float(g["height"])

            return [
                (x, y),
                (x + w, y),
                (x + w, y + h),
                (x, y + h),
            ]

        return []

    @staticmethod
    def _bbox(ann, width, height):

        if ann.shape_type == "rectangle":

            g = ann.geometry

            x = float(g["x"])
            y = float(g["y"])
            w = float(g["width"])
            h = float(g["height"])

        elif ann.shape_type == "polygon":

            points = [
                (float(x), float(y))
                for x, y in ann.geometry
            ]

            if len(points) < 3:
                return None

            xs = [p[0] for p in points]
            ys = [p[1] for p in points]

            x = min(xs)
            y = min(ys)
            w = max(xs) - x
            h = max(ys) - y

        else:

            return None

        if width <= 0 or height <= 0:
            return None

        xc = (x + w / 2) / width
        yc = (y + h / 2) / height

        wn = w / width
        hn = h / height

        return xc, yc, wn, hn

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def _fmt(value):
        return f"{value:.6f}"

    @staticmethod
    def _image_name(video_path, frame_number, index):
        stem = Path(video_path).stem
        return f"{stem}_frame_{frame_number:06d}_{index:06d}.jpg"
