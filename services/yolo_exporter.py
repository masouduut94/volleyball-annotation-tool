from collections import OrderedDict
from pathlib import Path
import random

import cv2
import yaml


class YOLOExporter:

    def __init__(self, db):

        self.db = db
        self.captures = {}

        # Fixed seed gives reproducible train/val splits.
        self.random = random.Random(42)

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
            augmentations=None,
            validation_ratio=0.0,
            progress_callback=None,
            cancel_callback=None,
    ):

        output_dir = Path(output_dir)

        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        augmentations = augmentations or []

        label_set = {
            (layer, label)
            for layer, label in selected_labels
        }

        try:

            if mode == "combined":

                self._export_dataset(
                    dataset_dir=(
                        output_dir / "dataset"
                    ),
                    output_format=output_format,
                    selected_layers=selected_layers,
                    selected_labels=label_set,
                    selected_videos=selected_videos,
                    augmentations=augmentations,
                    validation_ratio=validation_ratio,
                    progress_callback=progress_callback,
                    cancel_callback=cancel_callback,
                )

            else:

                for layer_name in selected_layers:

                    if self._is_cancelled(
                        cancel_callback
                    ):
                        return False

                    layer_labels = {
                        (layer, label)
                        for layer, label
                        in label_set
                        if layer == layer_name
                    }

                    if not layer_labels:
                        continue

                    self._export_dataset(
                        dataset_dir=(
                            output_dir / layer_name
                        ),
                        output_format=output_format,
                        selected_layers=[
                            layer_name
                        ],
                        selected_labels=layer_labels,
                        selected_videos=selected_videos,
                        augmentations=augmentations,
                        validation_ratio=validation_ratio,
                        progress_callback=progress_callback,
                        cancel_callback=cancel_callback,
                    )

            return True

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
            augmentations,
            validation_ratio,
            progress_callback,
            cancel_callback,
    ):

        dataset_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        images_train_dir = (
            dataset_dir
            / "images"
            / "train"
        )

        labels_train_dir = (
            dataset_dir
            / "labels"
            / "train"
        )

        images_val_dir = (
            dataset_dir
            / "images"
            / "val"
        )

        labels_val_dir = (
            dataset_dir
            / "labels"
            / "val"
        )

        images_train_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        labels_train_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        if validation_ratio > 0:

            images_val_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            labels_val_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

        # ------------------------------------------------------
        # Collect annotations
        # ------------------------------------------------------

        all_annotations = []

        for video_path in selected_videos:

            if self._is_cancelled(
                cancel_callback
            ):
                return

            annotations = (
                self.db.get_media_annotations(
                    video_path
                )
            )

            for ann in annotations:

                if (
                    ann.layer.name
                    not in selected_layers
                ):
                    continue

                if (
                    ann.layer.name,
                    ann.label.name,
                ) not in selected_labels:
                    continue

                all_annotations.append(ann)

        if not all_annotations:
            return

        # ------------------------------------------------------
        # Class mapping
        # ------------------------------------------------------

        class_names = OrderedDict()

        for ann in all_annotations:

            if ann.label.name not in class_names:

                class_names[
                    ann.label.name
                ] = len(class_names)

        # ------------------------------------------------------
        # Group by video + frame
        # ------------------------------------------------------

        grouped = {}

        for ann in all_annotations:

            key = (
                ann.media_name,
                ann.frame_number,
            )

            grouped.setdefault(
                key,
                [],
            ).append(ann)

        samples = list(
            grouped.items()
        )

        # ------------------------------------------------------
        # Split original frames into train / val
        # ------------------------------------------------------

        self.random.shuffle(samples)

        if validation_ratio > 0:

            val_count = int(
                len(samples)
                * validation_ratio
            )

            # At least one validation frame when
            # the requested ratio is > 0 and there
            # are enough samples.
            if val_count == 0 and len(samples) > 1:
                val_count = 1

            val_samples = samples[
                :val_count
            ]

            train_samples = samples[
                val_count:
            ]

        else:

            train_samples = samples
            val_samples = []

        # ------------------------------------------------------
        # Total work
        #
        # Original training sample = 1
        # Each selected augmentation = +1
        #
        # Validation samples are NOT augmented.
        # ------------------------------------------------------

        augmentation_count = len(
            augmentations
        )

        total_work = (
            len(train_samples)
            * (1 + augmentation_count)
            + len(val_samples)
        )

        completed = 0

        # ------------------------------------------------------
        # Export training samples
        # ------------------------------------------------------

        for sample_index, (
            (video_path, frame_number),
            annotations,
        ) in enumerate(train_samples):

            if self._is_cancelled(
                cancel_callback
            ):
                return

            # Original image.
            result = self._export_sample(
                video_path=video_path,
                frame_number=frame_number,
                annotations=annotations,
                class_names=class_names,
                output_format=output_format,
                image_dir=images_train_dir,
                label_dir=labels_train_dir,
                suffix="",
            )

            completed += 1

            self._report_progress(
                progress_callback,
                completed,
                total_work,
            )

            if result is None:
                continue

            original_image, original_labels = result

            # --------------------------------------------------
            # Augmented copies
            # --------------------------------------------------

            for aug_index, augmentation in enumerate(
                augmentations,
                start=1,
            ):

                if self._is_cancelled(
                    cancel_callback
                ):
                    return

                self._export_augmented_sample(
                    video_path=video_path,
                    frame_number=frame_number,
                    annotations=annotations,
                    class_names=class_names,
                    output_format=output_format,
                    image_dir=images_train_dir,
                    label_dir=labels_train_dir,
                    augmentation=augmentation,
                    augmentation_index=aug_index,
                )

                completed += 1

                self._report_progress(
                    progress_callback,
                    completed,
                    total_work,
                )

        # ------------------------------------------------------
        # Export validation samples
        # ------------------------------------------------------

        for (
            (video_path, frame_number),
            annotations,
        ) in val_samples:

            if self._is_cancelled(
                cancel_callback
            ):
                return

            self._export_sample(
                video_path=video_path,
                frame_number=frame_number,
                annotations=annotations,
                class_names=class_names,
                output_format=output_format,
                image_dir=images_val_dir,
                label_dir=labels_val_dir,
                suffix="",
            )

            completed += 1

            self._report_progress(
                progress_callback,
                completed,
                total_work,
            )

        # ------------------------------------------------------
        # data.yaml
        # ------------------------------------------------------

        data = {
            "path": str(
                dataset_dir.resolve()
            ),
            "train": "images/train",
            "names": dict(class_names),
        }

        if validation_ratio > 0:

            data["val"] = "images/val"

        data["task"] = (
            "segment"
            if output_format == "segmentation"
            else "detect"
        )

        with open(
            dataset_dir / "data.yaml",
            "w",
            encoding="utf-8",
        ) as f:

            yaml.safe_dump(
                data,
                f,
                sort_keys=False,
            )

    # ==========================================================
    # Export original sample
    # ==========================================================

    def _export_sample(
            self,
            video_path,
            frame_number,
            annotations,
            class_names,
            output_format,
            image_dir,
            label_dir,
            suffix="",
    ):

        image_name = self._image_name(
            video_path,
            frame_number,
            suffix,
        )

        image_path = (
            image_dir / image_name
        )

        label_path = (
            label_dir
            / f"{Path(image_name).stem}.txt"
        )

        frame = self._read_frame(
            video_path,
            frame_number,
        )

        if frame is None:
            return None

        height, width = frame.shape[:2]

        lines = self._build_yolo_labels(
            annotations=annotations,
            class_names=class_names,
            output_format=output_format,
            width=width,
            height=height,
        )

        if not lines:
            return None

        cv2.imwrite(
            str(image_path),
            frame,
        )

        label_path.write_text(
            "\n".join(lines),
            encoding="utf-8",
        )

        return frame, lines

    # ==========================================================
    # Augmented sample
    # ==========================================================

    def _export_augmented_sample(
            self,
            video_path,
            frame_number,
            annotations,
            class_names,
            output_format,
            image_dir,
            label_dir,
            augmentation,
            augmentation_index,
    ):

        frame = self._read_frame(
            video_path,
            frame_number,
        )

        if frame is None:
            return

        height, width = frame.shape[:2]

        # Copy annotations so geometry can be modified
        # for horizontal flip without changing DB data.
        transformed_annotations = []

        for ann in annotations:

            transformed_annotations.append(
                self._copy_annotation(ann)
            )

        # ------------------------------------------------------
        # Apply augmentation
        # ------------------------------------------------------

        if augmentation == "brightness_contrast":

            frame = self._augment_brightness_contrast(
                frame
            )

        elif augmentation == "color_jitter":

            frame = self._augment_color_jitter(
                frame
            )

        elif augmentation == "horizontal_flip":

            frame = cv2.flip(
                frame,
                1,
            )

            for ann in transformed_annotations:

                self._flip_annotation_horizontal(
                    ann,
                    width,
                )

        lines = self._build_yolo_labels(
            annotations=transformed_annotations,
            class_names=class_names,
            output_format=output_format,
            width=width,
            height=height,
        )

        if not lines:
            return

        image_name = self._image_name(
            video_path,
            frame_number,
            f"_aug_{augmentation_index}",
        )

        image_path = (
            image_dir / image_name
        )

        label_path = (
            label_dir
            / f"{Path(image_name).stem}.txt"
        )

        cv2.imwrite(
            str(image_path),
            frame,
        )

        label_path.write_text(
            "\n".join(lines),
            encoding="utf-8",
        )

    # ==========================================================
    # YOLO labels
    # ==========================================================

    def _build_yolo_labels(
            self,
            annotations,
            class_names,
            output_format,
            width,
            height,
    ):

        lines = []

        for ann in annotations:

            class_id = class_names[
                ann.label.name
            ]

            # --------------------------------------------------
            # Segmentation
            # --------------------------------------------------

            if output_format == "segmentation":

                points = self._polygon_points(
                    ann
                )

                if len(points) < 3:
                    continue

                values = [
                    str(class_id)
                ]

                for x, y in points:

                    x = max(
                        0.0,
                        min(float(x), width)
                    )

                    y = max(
                        0.0,
                        min(float(y), height)
                    )

                    values.append(
                        self._fmt(
                            x / width
                        )
                    )

                    values.append(
                        self._fmt(
                            y / height
                        )
                    )

                lines.append(
                    " ".join(values)
                )

            # --------------------------------------------------
            # Detection
            # --------------------------------------------------

            else:

                bbox = self._bbox(
                    ann,
                    width,
                    height,
                )

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

        return lines

    # ==========================================================
    # Frame extraction
    # ==========================================================

    def _read_frame(
            self,
            video_path,
            frame_number,
    ):

        if video_path not in self.captures:

            self.captures[
                video_path
            ] = cv2.VideoCapture(
                video_path
            )

        cap = self.captures[
            video_path
        ]

        if not cap.isOpened():
            return None

        cap.set(
            cv2.CAP_PROP_POS_FRAMES,
            frame_number,
        )

        ok, frame = cap.read()

        if not ok or frame is None:
            return None

        return frame

    def _release_captures(self):

        for cap in self.captures.values():

            if cap is not None:
                cap.release()

        self.captures.clear()

    # ==========================================================
    # Augmentation
    # ==========================================================

    def _augment_brightness_contrast(
            self,
            image,
    ):

        # Random but deliberately moderate values.
        alpha = self.random.uniform(
            0.85,
            1.15,
        )

        beta = self.random.uniform(
            -25,
            25,
        )

        return cv2.convertScaleAbs(
            image,
            alpha=alpha,
            beta=beta,
        )

    def _augment_color_jitter(
            self,
            image,
    ):

        hsv = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2HSV,
        )

        # Moderate random changes.
        saturation_scale = self.random.uniform(
            0.85,
            1.15,
        )

        value_scale = self.random.uniform(
            0.90,
            1.10,
        )

        hue_shift = self.random.randint(
            -8,
            8,
        )

        hsv = hsv.astype("float32")

        hsv[:, :, 0] += hue_shift

        hsv[:, :, 1] *= saturation_scale

        hsv[:, :, 2] *= value_scale

        hsv[:, :, 0] = (
            hsv[:, :, 0] % 180
        )

        hsv[:, :, 1] = (
            hsv[:, :, 1].clip(0, 255)
        )

        hsv[:, :, 2] = (
            hsv[:, :, 2].clip(0, 255)
        )

        hsv = hsv.astype("uint8")

        return cv2.cvtColor(
            hsv,
            cv2.COLOR_HSV2BGR,
        )

    # ==========================================================
    # Annotation transformations
    # ==========================================================

    @staticmethod
    def _copy_annotation(ann):

        import copy

        return copy.deepcopy(ann)

    @staticmethod
    def _flip_annotation_horizontal(
            ann,
            image_width,
    ):

        if ann.shape_type == "rectangle":

            g = ann.geometry

            x = float(g["x"])
            width = float(g["width"])

            g["x"] = (
                image_width
                - x
                - width
            )

        elif ann.shape_type == "polygon":

            flipped = []

            for x, y in ann.geometry:

                flipped.append(
                    (
                        image_width - float(x),
                        float(y),
                    )
                )

            ann.geometry = flipped

    # ==========================================================
    # Geometry
    # ==========================================================

    @staticmethod
    def _polygon_points(ann):

        if ann.shape_type == "polygon":

            return [
                (
                    float(x),
                    float(y),
                )
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
    def _bbox(
            ann,
            width,
            height,
    ):

        if ann.shape_type == "rectangle":

            g = ann.geometry

            x = float(g["x"])
            y = float(g["y"])
            w = float(g["width"])
            h = float(g["height"])

        elif ann.shape_type == "polygon":

            points = [
                (
                    float(x),
                    float(y),
                )
                for x, y in ann.geometry
            ]

            if len(points) < 3:
                return None

            xs = [
                p[0]
                for p in points
            ]

            ys = [
                p[1]
                for p in points
            ]

            x = min(xs)
            y = min(ys)

            w = max(xs) - x
            h = max(ys) - y

        else:

            return None

        if width <= 0 or height <= 0:
            return None

        # Clamp the box to the image.
        x1 = max(0.0, x)
        y1 = max(0.0, y)

        x2 = min(
            float(width),
            x + w,
        )

        y2 = min(
            float(height),
            y + h,
        )

        if x2 <= x1 or y2 <= y1:
            return None

        xc = (
            (x1 + x2) / 2
        ) / width

        yc = (
            (y1 + y2) / 2
        ) / height

        wn = (
            x2 - x1
        ) / width

        hn = (
            y2 - y1
        ) / height

        return (
            xc,
            yc,
            wn,
            hn,
        )

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def _fmt(value):
        return f"{value:.6f}"

    @staticmethod
    def _image_name(
            video_path,
            frame_number,
            suffix="",
    ):

        stem = Path(
            video_path
        ).stem

        return (
            f"{stem}_"
            f"frame_{frame_number:06d}"
            f"{suffix}.jpg"
        )

    @staticmethod
    def _is_cancelled(
            cancel_callback,
    ):

        if cancel_callback is None:
            return False

        return bool(
            cancel_callback()
        )

    @staticmethod
    def _report_progress(
            callback,
            completed,
            total,
    ):

        if callback is None:
            return

        if total <= 0:
            callback(100)
            return

        percentage = int(
            completed * 100 / total
        )

        callback(
            min(100, percentage)
        )