import json
from datetime import datetime
from pathlib import Path
from sqlalchemy.exc import IntegrityError
from typing import List, Optional, Dict, Tuple
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, joinedload, selectinload
from sqlalchemy import func

from .schema import (
    Base,
    Layer as SQLALayer,
    LayerLabel,
    Media,
    Annotation as SQLAAnnotation,
    ModelConfig,
)
from .data import Label, Layer, Annotation


def annotation_key(ann: Annotation):
    return (
        ann.media_name,
        ann.layer.layer_id,
        ann.frame_number,
        ann.label.label_id,
        ann.shape_type,
        json.dumps(ann.geometry, sort_keys=True),
    )


def remove_duplicate_annotations(annotations: list[Annotation]) -> list[Annotation]:
    seen = set()
    unique = []

    for ann in annotations:
        key = annotation_key(ann)
        if key not in seen:
            seen.add(key)
            unique.append(ann)

    return unique


class DatabaseManager:
    def __init__(self, db_path: str = "annotations.db"):
        self.db_path = Path(db_path)

        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            future=True,
            echo=False,
        )

        Base.metadata.create_all(self.engine)

        self.Session = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )

        self._create_default_data()

    # ------------------------------------------------------------------
    # Default volleyball layers
    # ------------------------------------------------------------------

    def _create_default_data(self):
        with self.Session() as session:
            if session.query(SQLALayer).count() > 0:
                return

            layers = {
                "court": [
                    ("net", "#4927F5"),
                    ("attack zone", "#128DE5"),
                    ("back zone", "#FFD814"),
                ],
                "players": [
                    ("player", "#27D3F5"),
                    ("libero", "#B027F5"),
                ],
                "ball": [
                    ("ball", "#6CF527"),
                ],
                "actions": [
                    ("spike", "#F5276C"),
                    ("block", "#F5B027"),
                    ("set", "#F54927"),
                    ("receive", "#FFAA00"),
                ],
            }

            for layer_name, labels in layers.items():
                layer = SQLALayer(name=layer_name)

                layer.labels = [
                    LayerLabel(
                        name=name,
                        color=color,
                    )
                    for name, color in labels
                ]

                session.add(layer)

            session.commit()

    # ------------------------------------------------------------------
    # Layers - Updated to return dataclasses
    # ------------------------------------------------------------------

    def get_layers(self) -> List[Layer]:
        """Get all layers with their labels pre-loaded."""
        with self.Session() as session:
            layers = session.query(SQLALayer).options(
                selectinload(SQLALayer.labels)
            ).all()

            return [
                Layer(
                    layer_id=layer.id,
                    name=layer.name,
                    labels=[
                        Label(
                            name=label.name,
                            color=label.color,
                            layer=layer.name,
                            label_id=label.id
                        )
                        for label in layer.labels
                    ]
                )
                for layer in layers
            ]

    def get_layer(self, layer_name: str) -> Layer:
        with self.Session() as session:
            layer = (
                session.query(SQLALayer)
                .options(selectinload(SQLALayer.labels))
                .filter(SQLALayer.name == layer_name)
                .first()
            )

            return Layer(
                layer_id=layer.id,
                name=layer.name,
                labels=[
                    Label(
                        name=label.name,
                        color=label.color,
                        layer=layer.name,
                        label_id=label.id
                    )
                    for label in layer.labels
                ]
            )

    # ------------------------------------------------------------------
    # Media
    # ------------------------------------------------------------------

    def get_or_create_media(self, path: str, media_type: str, width: int, height: int) -> Media:
        with self.Session() as session:
            media = (
                session.query(Media)
                .filter(Media.path == path)
                .first()
            )

            if media:
                return media

            media = Media(
                path=path,
                media_type=media_type,
                width=width,
                height=height,
            )

            session.add(media)
            session.commit()
            session.refresh(media)

            return media

    def get_media(self, path: str) -> Optional[Media]:
        with self.Session() as session:
            return session.query(Media).filter(Media.path == path).first()

    def get_all_media(self) -> List[Media]:
        with self.Session() as session:
            return session.query(Media).order_by(Media.created_at.desc()).all()

    def get_media_annotations(
            self,
            media_path: str,
    ) -> List[Annotation]:

        with self.Session() as session:

            media = (
                session.query(Media)
                .filter(Media.path == media_path)
                .first()
            )

            if media is None:
                return []

            records = (
                session.query(SQLAAnnotation)
                .options(
                    joinedload(SQLAAnnotation.layer),
                    joinedload(SQLAAnnotation.label),
                )
                .filter(
                    SQLAAnnotation.media_id == media.id
                )
                .all()
            )

            annotations = []

            for r in records:
                layer_dc = Layer(
                    layer_id=r.layer.id,
                    name=r.layer.name,
                    labels=[],
                )

                label_dc = Label(
                    label_id=r.label.id,
                    name=r.label.name,
                    color=r.label.color,
                    layer=r.layer.name,
                )

                annotations.append(
                    Annotation(
                        annotation_id=r.id,
                        media_name=media_path,
                        layer=layer_dc,
                        label=label_dc,
                        frame_number=r.frame_number,
                        shape_type=r.shape_type,
                        geometry=json.loads(r.geometry),
                    )
                )

            return annotations

    # ------------------------------------------------------------------
    # Annotations - Updated with dataclass support.
    # ------------------------------------------------------------------

    def save_annotations(
            self,
            media_path: str,
            media_type: str,
            width: int,
            height: int,
            layer: Layer,
            frame_number: Optional[int],
            annotations: List[Annotation],
    ):

        annotations = remove_duplicate_annotations(annotations)

        with self.Session() as session:
            media = (
                session.query(Media)
                .filter(Media.path == media_path)
                .first()
            )

            if media is None:
                media = Media(
                    path=media_path,
                    media_type=media_type,
                    width=width,
                    height=height,
                )
                session.add(media)
                session.commit()
                session.refresh(media)

            session.query(SQLAAnnotation).filter(
                SQLAAnnotation.media_id == media.id,
                SQLAAnnotation.layer_id == layer.layer_id,
                SQLAAnnotation.frame_number == frame_number,
            ).delete()

            for ann in annotations:
                record = SQLAAnnotation(
                    media_id=media.id,
                    layer_id=layer.layer_id,
                    label_id=ann.label.label_id,
                    frame_number=frame_number,
                    shape_type=ann.shape_type,
                    geometry=json.dumps(ann.geometry),
                )
                session.add(record)
                session.commit()

    def load_annotations(
            self,
            media_path: str,
            layer_id: int,
            frame_number: Optional[int],
    ) -> List[Annotation]:

        with self.Session() as session:
            media = (
                session.query(Media)
                .filter(Media.path == media_path)
                .first()
            )

            if media is None:
                return []

            records = (
                session.query(SQLAAnnotation)
                .options(
                    joinedload(SQLAAnnotation.layer).joinedload(SQLALayer.labels),
                    joinedload(SQLAAnnotation.label),
                )
                .filter(
                    SQLAAnnotation.media_id == media.id,
                    SQLAAnnotation.layer_id == layer_id,
                    SQLAAnnotation.frame_number == frame_number,
                )
                .all()
            )

            annotations = []

            for r in records:
                layer_dc = Layer(
                    layer_id=r.layer.id,
                    name=r.layer.name,
                    labels=[
                        Label(
                            label_id=l.id,
                            name=l.name,
                            color=l.color,
                            layer=r.layer.name,
                        )
                        for l in r.layer.labels
                    ],
                )

                label_dc = Label(
                    label_id=r.label.id,
                    name=r.label.name,
                    color=r.label.color,
                    layer=r.layer.name,
                )

                annotations.append(
                    Annotation(
                        annotation_id=r.id,
                        media_name=media_path,
                        layer=layer_dc,
                        label=label_dc,
                        frame_number=r.frame_number,
                        shape_type=r.shape_type,
                        geometry=json.loads(r.geometry),
                    )
                )

            return annotations

    def delete_annotations(self, media_path: str, layer_id: int, frame_number: Optional[int]):
        with self.Session() as session:
            media = (
                session.query(Media)
                .filter(Media.path == media_path)
                .first()
            )

            if media is None:
                return

            session.query(SQLAAnnotation).filter(
                SQLAAnnotation.media_id == media.id,
                SQLAAnnotation.layer_id == layer_id,
                SQLAAnnotation.frame_number == frame_number,
            ).delete()

            session.commit()

    # ------------------------------------------------------------------
    # AI models
    # ------------------------------------------------------------------

    def get_model_path(self, key: str):
        with self.Session() as session:
            config = session.get(ModelConfig, key)
            return config.path if config else None

    def set_model_path(self, key: str, path: str):
        with self.Session() as session:
            config = session.get(ModelConfig, key)

            if config is None:
                config = ModelConfig(
                    key=key,
                    path=path,
                )
                session.add(config)
            else:
                config.path = path

            session.commit()
