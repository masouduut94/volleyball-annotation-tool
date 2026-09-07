import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, joinedload, selectinload

from .schema import (
    Base,
    LayerLabel,
    Media,
    ModelConfig,
    FrameReview,
    Annotation as SQLAAnnotation,
    Layer as SQLALayer,
    GameStateSegment as SQLAGameStateSegment
)
from .data import Label, Layer, Annotation, GameStateSegment


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
                "ball": [
                    ("ball", "#6CF527"),
                ],
                "actions": [
                    ("spike", "#F5276C"),
                    ("block", "#F5B027"),
                    ("set", "#F54927"),
                    ("receive", "#7b00ff"),
                ],
                "players": [
                    ("player", "#27D3F5"),
                    ("libero", "#B027F5"),
                    ("referee", "ff0080"),
                ],
                "court": [
                    ("net", "#4927F5"),
                    ("attack zone", "#128DE5"),
                    ("back zone", "#FFD814"),
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

    def get_media_annotations(self, media_path: str) -> List[Annotation]:

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
                        is_ai_generated=r.is_ai_generated,
                        confirmed=r.confirmed,
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
                        is_ai_generated=r.is_ai_generated,
                        confirmed=r.confirmed,
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
    # AI provenance / frame review
    # ------------------------------------------------------------------

    def insert_ai_annotations(
            self,
            media_path: str,
            media_type: str,
            width: int,
            height: int,
            layer: Layer,
            frame_number: Optional[int],
            annotations: List[Annotation],
    ) -> List[int]:
        """
        Insert a batch of AI-generated annotations immediately — unlike
        save_annotations(), this does NOT wipe existing rows for the
        frame/layer first. Every row is flagged is_ai_generated=True,
        confirmed=False.

        Returns the DB ids assigned, in the same order as `annotations`,
        so the caller (BulkCreateAnnotationCommand) can undo exactly this
        batch by id, without touching anything a human confirmed later.
        """
        with self.Session() as session:
            media = session.query(Media).filter(Media.path == media_path).first()

            if media is None:
                media = Media(path=media_path, media_type=media_type, width=width, height=height)
                session.add(media)
                session.commit()
                session.refresh(media)

            ids = []
            for ann in annotations:
                record = SQLAAnnotation(
                    media_id=media.id,
                    layer_id=layer.layer_id,
                    label_id=ann.label.label_id,
                    frame_number=frame_number,
                    shape_type=ann.shape_type,
                    geometry=json.dumps(ann.geometry),
                    is_ai_generated=True,
                    confirmed=False,
                )
                session.add(record)
                session.commit()
                session.refresh(record)
                ids.append(record.id)

            # New unconfirmed detections invalidate any prior human sign-off
            self._reset_frame_review(session, media.id, layer.layer_id, frame_number)

            return ids

    def delete_annotations_by_ids(self, ids: List[int]):
        """Delete specific annotation rows by id — used to undo an AI batch
        without touching anything else in the frame/layer."""
        if not ids:
            return
        with self.Session() as session:
            session.query(SQLAAnnotation).filter(
                SQLAAnnotation.id.in_(ids)
            ).delete(synchronize_session=False)
            session.commit()

    def confirm_frame(self, media_path: str, layer_id: int, frame_number: Optional[int]):
        """
        Human sign-off: mark every annotation currently stored for this
        media/layer/frame as confirmed, and upsert a FrameReview row.
        """
        with self.Session() as session:
            media = session.query(Media).filter(Media.path == media_path).first()
            if media is None:
                return

            session.query(SQLAAnnotation).filter(
                SQLAAnnotation.media_id == media.id,
                SQLAAnnotation.layer_id == layer_id,
                SQLAAnnotation.frame_number == frame_number,
            ).update({"confirmed": True}, synchronize_session=False)

            review = (
                session.query(FrameReview)
                .filter(
                    FrameReview.media_id == media.id,
                    FrameReview.layer_id == layer_id,
                    FrameReview.frame_number == frame_number,
                )
                .first()
            )

            if review is None:
                review = FrameReview(
                    media_id=media.id, layer_id=layer_id, frame_number=frame_number,
                    confirmed=True, confirmed_at=datetime.utcnow(),
                )
                session.add(review)
            else:
                review.confirmed = True
                review.confirmed_at = datetime.utcnow()

            session.commit()

    def is_frame_confirmed(self, media_path: str, layer_id: int, frame_number: Optional[int]) -> bool:
        with self.Session() as session:
            media = session.query(Media).filter(Media.path == media_path).first()
            if media is None:
                return False

            review = (
                session.query(FrameReview)
                .filter(
                    FrameReview.media_id == media.id,
                    FrameReview.layer_id == layer_id,
                    FrameReview.frame_number == frame_number,
                )
                .first()
            )
            return bool(review and review.confirmed)

    @staticmethod
    def _reset_frame_review(session, media_id, layer_id, frame_number):
        review = (
            session.query(FrameReview)
            .filter(
                FrameReview.media_id == media_id,
                FrameReview.layer_id == layer_id,
                FrameReview.frame_number == frame_number,
            )
            .first()
        )
        if review is not None and review.confirmed:
            review.confirmed = False
            session.commit()

    def insert_annotation(self, media_path, media_type, width, height,
                          layer: Layer, frame_number, annotation: Annotation) -> int:
        """
        Insert exactly one annotation row and return its id, preserving
        is_ai_generated/confirmed. Used by DeleteAnnotationCommand.undo()
        to restore a deleted row exactly as it was — not as a fresh
        human-drawn one — regardless of how it originally got there.
        """
        with self.Session() as session:
            media = session.query(Media).filter(Media.path == media_path).first()
            if media is None:
                media = Media(path=media_path, media_type=media_type, width=width, height=height)
                session.add(media)
                session.commit()
                session.refresh(media)

            record = SQLAAnnotation(
                media_id=media.id,
                layer_id=layer.layer_id,
                label_id=annotation.label.label_id,
                frame_number=frame_number,
                shape_type=annotation.shape_type,
                geometry=json.dumps(annotation.geometry),
                is_ai_generated=annotation.is_ai_generated,
                confirmed=annotation.confirmed,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record.id

    def update_annotation_label(self, annotation_id: int, label_id: int):
        """Persist a label change immediately for an already-saved row, so
        switching layers/frames doesn't silently revert it (same class of
        bug as the delete-reappear issue, applied to label edits)."""
        with self.Session() as session:
            session.query(SQLAAnnotation).filter(
                SQLAAnnotation.id == annotation_id
            ).update({"label_id": label_id}, synchronize_session=False)
            session.commit()

    def unconfirm_frame(self, media_path: str, layer_id: int, frame_number: Optional[int]):
        with self.Session() as session:
            media = session.query(Media).filter(Media.path == media_path).first()
            if media is None:
                return
            self._reset_frame_review(session, media.id, layer_id, frame_number)

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

    def save_game_state_segments(
            self, media_path, media_type, width, height,
            start_frame, end_frame, segments,
    ):
        with self.Session() as session:
            media = session.query(Media).filter(Media.path == media_path).first()
            if media is None:
                media = Media(path=media_path, media_type=media_type, width=width, height=height)
                session.add(media)
                session.commit()
                session.refresh(media)

            session.query(SQLAGameStateSegment).filter(
                SQLAGameStateSegment.media_id == media.id,
                SQLAGameStateSegment.start_frame >= start_frame,
                SQLAGameStateSegment.end_frame <= end_frame,
            ).delete(synchronize_session=False)

            for seg in segments:
                session.add(SQLAGameStateSegment(
                    media_id=media.id,
                    start_frame=seg.start_frame,
                    end_frame=seg.end_frame,
                    state=seg.state,
                    confidence=seg.confidence,
                    source=getattr(seg, "source", "model"),  # NEW
                ))

            session.commit()

    def save_manual_game_state_segment(
            self, media_path: str, media_type: str, width: int, height: int,
            start_frame: int, end_frame: int, state: str,
    ):
        """
        Persist one human-tagged ground-truth segment. Reuses the same
        replace-in-range logic as the AI job, so a manual tag cleanly
        overwrites whatever the classifier (or an earlier tag) put there —
        nothing is written until both a start and an end frame exist.
        """
        segment = GameStateSegment(
            media_name=media_path,
            start_frame=start_frame,
            end_frame=end_frame,
            state=state,
            confidence=1.0,
            source="manual",
        )
        self.save_game_state_segments(
            media_path=media_path, media_type=media_type, width=width, height=height,
            start_frame=start_frame, end_frame=end_frame, segments=[segment],
        )

    def get_game_state_segments(self, media_path: str) -> List[GameStateSegment]:
        with self.Session() as session:
            media = session.query(Media).filter(Media.path == media_path).first()
            if media is None:
                return []

            records = (
                session.query(SQLAGameStateSegment)
                .filter(SQLAGameStateSegment.media_id == media.id)
                .order_by(SQLAGameStateSegment.start_frame)
                .all()
            )

            return [
                GameStateSegment(
                    segment_id=r.id, media_name=media_path,
                    start_frame=r.start_frame, end_frame=r.end_frame,
                    state=r.state, confidence=r.confidence, source=r.source,  # NEW
                )
                for r in records
            ]

    def clear_game_state_segments(self, media_path: str):
        with self.Session() as session:
            media = session.query(Media).filter(Media.path == media_path).first()
            if media is None:
                return
            session.query(SQLAGameStateSegment).filter(
                SQLAGameStateSegment.media_id == media.id
            ).delete(synchronize_session=False)
            session.commit()

    def get_segment_at_frame(self, media_path: str, frame_number: int) -> Optional[GameStateSegment]:
        """Return the segment (if any) whose range contains this frame."""
        with self.Session() as session:
            media = session.query(Media).filter(Media.path == media_path).first()
            if media is None:
                return None

            record = (
                session.query(SQLAGameStateSegment)
                .filter(
                    SQLAGameStateSegment.media_id == media.id,
                    SQLAGameStateSegment.start_frame <= frame_number,
                    SQLAGameStateSegment.end_frame >= frame_number,
                )
                .first()
            )

            if record is None:
                return None

            return GameStateSegment(
                segment_id=record.id,
                media_name=media_path,
                start_frame=record.start_frame,
                end_frame=record.end_frame,
                state=record.state,
                confidence=record.confidence,
                source=record.source,
            )

    def update_game_state_segment(
            self, segment_id: int, start_frame: int, end_frame: int, state: str,
    ) -> Optional[str]:
        """
        Apply an edit to an existing segment. Marks it "manual" since a human
        touched it, regardless of how it originally got created.

        Returns None on success, or an error message string on failure (e.g.
        the new range collides with another row's exact start/end pair).
        """
        if start_frame > end_frame:
            start_frame, end_frame = end_frame, start_frame

        with self.Session() as session:
            record = session.get(SQLAGameStateSegment, segment_id)
            if record is None:
                return "Tag no longer exists."

            record.start_frame = start_frame
            record.end_frame = end_frame
            record.state = state
            record.source = "manual"

            try:
                session.commit()
            except Exception as e:
                session.rollback()
                return f"Could not save changes: {e}"

        return None

    def delete_game_state_segment(self, segment_id: int):
        with self.Session() as session:
            session.query(SQLAGameStateSegment).filter(
                SQLAGameStateSegment.id == segment_id
            ).delete(synchronize_session=False)
            session.commit()
