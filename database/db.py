import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from sqlalchemy import create_engine, func, inspect, text
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

GAME_ON_STATES = {"service", "play"}
MIN_GAP_SECONDS = 3
min_gap_allowed = 90  # frames

def _line_intersection(p1, p2, p3, p4):
    """
    Intersection of the INFINITE line through p1,p2 with the infinite
    line through p3,p4 (standard two-line determinant formula). Returns
    [x, y], or None if the lines are parallel (denominator ~0) — callers
    fall back to the original point in that case rather than crashing.
    """
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    x4, y4 = p4

    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-9:
        return None

    px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / denom
    py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / denom
    return [px, py]


def _net_top_endpoints(net_geometries):
    """
    Given the geometries stored under the "net" label (normally just
    one shape, but every net-labeled annotation is included), returns
    [left_point, right_point] for the net's TOP edge — the vertices
    with the smallest y across all net shapes, sorted left-to-right by
    x. Works whether the net was drawn as a rectangle or a polygon.
    Returns None if there aren't at least two points to work with.
    """
    points = []
    for geom in net_geometries:
        if isinstance(geom, dict):  # rectangle: {"x", "y", "width", "height"}
            x, y, w, h = geom["x"], geom["y"], geom["width"], geom["height"]
            points.append((x, y))
            points.append((x + w, y))
        else:  # polygon: list of [x, y] pairs
            points.extend((p[0], p[1]) for p in geom)

    if len(points) < 2:
        return None

    min_y = min(p[1] for p in points)
    # A small tolerance around the minimum y treats a slightly-tilted
    # net (perspective) as still "the top edge" rather than requiring
    # an exact match.
    tolerance = 2.0
    top_points = [p for p in points if p[1] <= min_y + tolerance]

    if len(top_points) < 2:
        top_points = sorted(points, key=lambda p: p[1])[:2]

    top_points.sort(key=lambda p: p[0])  # left-to-right
    return [list(top_points[0]), list(top_points[-1])]


# TODO: Build a utils for dataset folder.
def compute_full_court_polygon(back_zone_polygons, frame_width, frame_height, net_geometries=None):
    """
    Builds the whole-court polygon from the two back-zone shapes, same
    as before (closest back-zone point to each image corner). Then, if
    net geometry is available, REPLACES the two top corners with where
    the court's left/right SIDE edges actually cross the net's top
    line — since the back zone is usually drawn well short of the net,
    its "closest to top corner" point is just the far end of that
    shape, not where the court boundary truly meets the net.

    Returns a 4-point polygon [top-left, bottom-left, bottom-right,
    top-right], or None if there's nothing to build from.
    """
    points = [tuple(p) for poly in back_zone_polygons for p in poly]
    if not points:
        return None

    corners = [
        (0, 0),
        (0, frame_height),
        (frame_width, frame_height),
        (frame_width, 0),
    ]

    polygon = []
    for cx, cy in corners:
        closest = min(points, key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2)
        polygon.append([closest[0], closest[1]])

    top_left, bottom_left, bottom_right, top_right = polygon

    if not net_geometries:
        return polygon

    net_line = _net_top_endpoints(net_geometries)
    if net_line is None:
        return polygon

    net_left, net_right = net_line

    # Each side edge is the line from the bottom corner up through the
    # back-zone-derived top corner on the same side — extended until it
    # crosses the net's top line. That crossing point is the real top
    # corner of the court.
    new_top_left = _line_intersection(bottom_left, top_left, net_left, net_right)
    new_top_right = _line_intersection(bottom_right, top_right, net_left, net_right)

    if new_top_left is not None:
        top_left = new_top_left
    if new_top_right is not None:
        top_right = new_top_right

    return [top_left, bottom_left, bottom_right, top_right]


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

        with self.engine.begin() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA synchronous=NORMAL"))  # WAL makes full fsync-per-commit unnecessary

        Base.metadata.create_all(self.engine)
        self._migrate_schema()

        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)

        self._create_default_data()

    # ------------------------------------------------------------------
    # Default volleyball layers
    # ------------------------------------------------------------------

    def _migrate_schema(self):
        inspector = inspect(self.engine)
        existing_cols = {col["name"] for col in inspector.get_columns("annotations")}
        media_cols = {col["name"] for col in inspector.get_columns("media")}
        with self.engine.begin() as conn:
            if "track_id" not in existing_cols:
                conn.execute(text("ALTER TABLE annotations ADD COLUMN track_id INTEGER"))
            if "team_id" not in existing_cols:
                conn.execute(text("ALTER TABLE annotations ADD COLUMN team_id INTEGER"))
            if "court_coordinates" not in media_cols:
                conn.execute(text("ALTER TABLE media ADD COLUMN court_coordinates TEXT"))

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
                        track_id=r.track_id,
                        team_id=r.team_id,
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
                    track_id=ann.track_id,
                    team_id=ann.team_id,
                )
                session.add(record)
                session.commit()

        if layer.name == "court":
            self.cache_court_coordinates(media_path, frame_number)

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
                        track_id=r.track_id,
                        team_id=r.team_id,
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

    def insert_ai_annotations(self, media_path, media_type, width, height, layer,
                              frame_number, annotations):
        """
        Insert a batch of AI-generated annotations immediately — unlike
        save_annotations(), this does NOT wipe existing rows for the
        frame/layer first. Every row is flagged is_ai_generated=True,
        confirmed=False.

        Returns the DB ids assigned, in the same order as `annotations`,
        so the caller (BulkCreateAnnotationCommand) can undo exactly this
        batch by id, without touching anything a human confirmed later.
        """
        annotations = remove_duplicate_annotations(annotations)

        with self.Session() as session:
            media = session.query(Media).filter(Media.path == media_path).first()
            if media is None:
                media = Media(path=media_path, media_type=media_type, width=width, height=height)
                session.add(media)
                session.commit()
                session.refresh(media)

            existing = {
                (label_id, shape_type, json.dumps(json.loads(geometry), sort_keys=True))
                for label_id, shape_type, geometry in session.query(
                    SQLAAnnotation.label_id, SQLAAnnotation.shape_type, SQLAAnnotation.geometry
                ).filter(
                    SQLAAnnotation.media_id == media.id,
                    SQLAAnnotation.layer_id == layer.layer_id,
                    SQLAAnnotation.frame_number == frame_number,
                )
            }

            ids, skipped = [], 0
            for ann in annotations:
                sig = (ann.label.label_id, ann.shape_type, json.dumps(ann.geometry, sort_keys=True))
                if sig in existing:
                    ids.append(None)  # keeps ids aligned 1:1 with `annotations` for the caller
                    skipped += 1
                    continue
                record = SQLAAnnotation(
                    media_id=media.id, layer_id=layer.layer_id, label_id=ann.label.label_id,
                    frame_number=frame_number, shape_type=ann.shape_type,
                    geometry=json.dumps(ann.geometry), is_ai_generated=True, confirmed=False,
                    track_id=ann.track_id, team_id=ann.team_id
                )
                session.add(record)
                session.commit()
                session.refresh(record)
                ids.append(record.id)
                existing.add(sig)

            if skipped:
                print(f"[auto-annotate] skipped {skipped} duplicate annotation(s) "
                      f"already present for layer={layer.name} frame={frame_number}")

            self._reset_frame_review(session, media.id, layer.layer_id, frame_number)
            return ids, skipped

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

            layer_row = session.get(SQLALayer, layer_id)
            is_court_layer = bool(layer_row and layer_row.name == "court")

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

        if is_court_layer:
            self.cache_court_coordinates(media_path, frame_number)

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

    def get_frame_layer_statuses(self, media_path: str, frame_number: Optional[int]) -> dict:
        """
        For every layer, resolve one of "none" | "ai" | "user" | "confirmed"
        for the (media, frame) pair:
          - "confirmed" wins outright if a human explicitly hit Confirm
            (FrameReview.confirmed) for that layer/frame.
          - Otherwise "ai" if any stored annotation there is AI-generated
            (still needs review).
          - Otherwise "user" if annotations exist and are all human-drawn.
          - Otherwise "none".
        """
        with self.Session() as session:
            layers = session.query(SQLALayer).all()
            media = session.query(Media).filter(Media.path == media_path).first()

            statuses = {}

            if media is None:
                for layer in layers:
                    statuses[layer.name] = "none"
                return statuses

            for layer in layers:
                review = (
                    session.query(FrameReview)
                    .filter(
                        FrameReview.media_id == media.id,
                        FrameReview.layer_id == layer.id,
                        FrameReview.frame_number == frame_number,
                    )
                    .first()
                )

                if review and review.confirmed:
                    statuses[layer.name] = "confirmed"
                    continue

                records = (
                    session.query(SQLAAnnotation)
                    .filter(
                        SQLAAnnotation.media_id == media.id,
                        SQLAAnnotation.layer_id == layer.id,
                        SQLAAnnotation.frame_number == frame_number,
                    )
                    .all()
                )

                if not records:
                    statuses[layer.name] = "none"
                elif any(r.is_ai_generated for r in records):
                    statuses[layer.name] = "ai"
                else:
                    statuses[layer.name] = "user"

            return statuses

    def get_annotation_counts(self) -> dict:
        """
        Returns {layer_name: {label_name: count}} across ALL media and
        frames — used by the statistics dialog. Uses an outer join so
        labels with zero annotations still show up with count 0.
        """
        with self.Session() as session:
            rows = (
                session.query(SQLALayer.name, LayerLabel.name, func.count(SQLAAnnotation.id))
                .join(LayerLabel, LayerLabel.layer_id == SQLALayer.id)
                .outerjoin(SQLAAnnotation, SQLAAnnotation.label_id == LayerLabel.id)
                .group_by(SQLALayer.name, LayerLabel.name)
                .all()
            )

            result = {}
            for layer_name, label_name, count in rows:
                result.setdefault(layer_name, {})[label_name] = count
            return result

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
                track_id=annotation.track_id,  # NEW
                team_id=annotation.team_id,  # NEW
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

            self._trim_segments_for_range(session, media.id, start_frame, end_frame)

            for seg in segments:
                session.add(SQLAGameStateSegment(
                    media_id=media.id,
                    start_frame=seg.start_frame,
                    end_frame=seg.end_frame,
                    state=seg.state,
                    confidence=seg.confidence,
                    source=getattr(seg, "source", "model"),
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

    def get_segments_overlapping_range(
            self, media_path: str, start_frame: int, end_frame: int,
    ) -> List[GameStateSegment]:
        """Every segment whose range intersects [start_frame, end_frame] at
        all — partial or full overlap — used to warn the user before an AI
        classification run would overwrite existing data in that range."""
        with self.Session() as session:
            media = session.query(Media).filter(Media.path == media_path).first()
            if media is None:
                return []

            records = (
                session.query(SQLAGameStateSegment)
                .filter(
                    SQLAGameStateSegment.media_id == media.id,
                    SQLAGameStateSegment.start_frame <= end_frame,
                    SQLAGameStateSegment.end_frame >= start_frame,
                )
                .order_by(SQLAGameStateSegment.start_frame)
                .all()
            )

            return [
                GameStateSegment(
                    segment_id=r.id, media_name=media_path,
                    start_frame=r.start_frame, end_frame=r.end_frame,
                    state=r.state, confidence=r.confidence, source=r.source,
                )
                for r in records
            ]

    @staticmethod
    def _trim_segments_for_range(session, media_id, start_frame, end_frame):
        """
        Remove/trim every existing segment that overlaps [start_frame,
        end_frame] so a fresh write into that range never leaves stale or
        duplicate coverage behind:
          - fully inside the range           -> deleted
          - overlaps only one edge           -> trimmed to sit outside the range
          - fully spans the range on both sides -> split into a left and
            a right remainder, with the middle (the overwritten part) gone
        """
        overlapping = (
            session.query(SQLAGameStateSegment)
            .filter(
                SQLAGameStateSegment.media_id == media_id,
                SQLAGameStateSegment.start_frame <= end_frame,
                SQLAGameStateSegment.end_frame >= start_frame,
            )
            .all()
        )

        for seg in overlapping:
            starts_before = seg.start_frame < start_frame
            ends_after = seg.end_frame > end_frame

            if starts_before and ends_after:
                right_start = end_frame + 1
                right_end = seg.end_frame
                seg.end_frame = start_frame - 1
                session.add(SQLAGameStateSegment(
                    media_id=media_id, start_frame=right_start, end_frame=right_end,
                    state=seg.state, confidence=seg.confidence, source=seg.source,
                ))
            elif starts_before:
                seg.end_frame = start_frame - 1
            elif ends_after:
                seg.start_frame = end_frame + 1
            else:
                session.delete(seg)

        session.flush()

    def has_ai_annotations(self, media_path: str, layer_id: int, frame_number: Optional[int]) -> bool:
        """
        Cheap existence check for batch inference's 'keep existing' mode —
        True if this (media, layer, frame) already has any AI-generated row,
        confirmed or not.
        """
        with self.Session() as session:
            media = session.query(Media).filter(Media.path == media_path).first()
            if media is None:
                return False
            return session.query(
                session.query(SQLAAnnotation.id).filter(
                    SQLAAnnotation.media_id == media.id,
                    SQLAAnnotation.layer_id == layer_id,
                    SQLAAnnotation.frame_number == frame_number,
                    SQLAAnnotation.is_ai_generated == True,  # noqa: E712
                ).exists()
            ).scalar()

    def replace_ai_annotations(self, media_path, media_type, width, height, layer, frame_number, annotations):
        annotations = remove_duplicate_annotations(annotations)

        with self.Session() as session:
            media = session.query(Media).filter(Media.path == media_path).first()
            if media is None:
                media = Media(path=media_path, media_type=media_type, width=width, height=height)
                session.add(media)
                session.flush()  # gets media.id without committing yet

            session.query(SQLAAnnotation).filter(
                SQLAAnnotation.media_id == media.id,
                SQLAAnnotation.layer_id == layer.layer_id,
                SQLAAnnotation.frame_number == frame_number,
                SQLAAnnotation.confirmed == False,
                SQLAAnnotation.is_ai_generated == True,
            ).delete(synchronize_session=False)

            existing = {...}  # unchanged

            ids, skipped, records = [], 0, []
            for ann in annotations:
                sig = (ann.label.label_id, ann.shape_type, json.dumps(ann.geometry, sort_keys=True))
                if sig in existing:
                    skipped += 1
                    continue
                record = SQLAAnnotation(
                    media_id=media.id, layer_id=layer.layer_id, label_id=ann.label.label_id,
                    frame_number=frame_number, shape_type=ann.shape_type,
                    geometry=json.dumps(ann.geometry), is_ai_generated=True, confirmed=False,
                    track_id=ann.track_id, team_id=ann.team_id,
                )
                session.add(record)
                records.append(record)
                existing.add(sig)

            self._reset_frame_review(session, media.id, layer.layer_id, frame_number)
            session.commit()  # ONE commit for the whole frame
            ids = [r.id for r in records]
            return ids, skipped

    def update_annotation_track(self, annotation_id: int, track_id, team_id):
        """Persist a track-id/team-id edit immediately for an already-saved
        row, same rationale as update_annotation_label."""
        with self.Session() as session:
            session.query(SQLAAnnotation).filter(
                SQLAAnnotation.id == annotation_id
            ).update({"track_id": track_id, "team_id": team_id}, synchronize_session=False)
            session.commit()

    # Court

    def get_court_annotations(
            self, media_path: str, frame_number: Optional[int],
    ) -> List[Annotation]:
        """Court-layer annotations for a single frame — the source
        geometry used when propagating a court layout to other frames."""
        with self.Session() as session:
            layer = (
                session.query(SQLALayer)
                .filter(SQLALayer.name == "court")
                .first()
            )
            if layer is None:
                return []

        return self.load_annotations(
            media_path=media_path,
            layer_id=layer.id,
            frame_number=frame_number,
        )

    def get_game_on_frames(self, media_path: str) -> List[int]:
        """Every frame inside a Service or In-Play segment, sorted and
        de-duplicated. Empty list if the video has no game-state tags."""
        with self.Session() as session:
            media = session.query(Media).filter(Media.path == media_path).first()
            if media is None:
                return []

            rows = (
                session.query(
                    SQLAGameStateSegment.start_frame,
                    SQLAGameStateSegment.end_frame,
                )
                .filter(
                    SQLAGameStateSegment.media_id == media.id,
                    SQLAGameStateSegment.state.in_(GAME_ON_STATES),
                )
                .order_by(SQLAGameStateSegment.start_frame)
                .all()
            )

        frames: set[int] = set()
        for start, end in rows:
            frames.update(range(start, end + 1))
        return sorted(frames)

    def count_frames_with_court_annotations(
            self, media_path: str, frame_numbers: List[int],
    ) -> int:
        """How many of `frame_numbers` already have at least one court
        row. Used to warn the user before a bulk overwrite."""
        if not frame_numbers:
            return 0

        with self.Session() as session:
            media = session.query(Media).filter(Media.path == media_path).first()
            if media is None:
                return 0

            layer = session.query(SQLALayer).filter(SQLALayer.name == "court").first()
            if layer is None:
                return 0

            count = (
                session.query(func.count(func.distinct(SQLAAnnotation.frame_number)))
                .filter(
                    SQLAAnnotation.media_id == media.id,
                    SQLAAnnotation.layer_id == layer.id,
                    SQLAAnnotation.frame_number.in_(frame_numbers),
                )
                .scalar()
            )
            return int(count or 0)

    def copy_court_annotations_to_frames(
            self,
            media_path: str,
            media_type: str,
            width: int,
            height: int,
            source_frame: Optional[int],
            target_frames: List[int],
            mode: str = "replace",  # "replace" | "skip_existing"
    ) -> dict:
        """Copy every court-layer annotation from `source_frame` to each
        frame in `target_frames`. All work happens in one transaction.

        `mode`:
          - "replace":       overwrite court rows already on a target.
          - "skip_existing": leave frames that already have court rows.

        Returns {"copied": int, "frames_written": int, "frames_skipped": int}.
        """
        stats = {"copied": 0, "frames_written": 0, "frames_skipped": 0}

        source = self.get_court_annotations(media_path, source_frame)
        if not source:
            return stats

        # Never rewrite the frame the user is currently looking at.
        targets = [f for f in target_frames if f != source_frame]
        if not targets:
            return stats

        with self.Session() as session:
            media = session.query(Media).filter(Media.path == media_path).first()
            if media is None:
                media = Media(
                    path=media_path, media_type=media_type,
                    width=width, height=height,
                )
                session.add(media)
                session.commit()
                session.refresh(media)

            layer = session.query(SQLALayer).filter(SQLALayer.name == "court").first()
            if layer is None:
                return stats

            if mode == "skip_existing":
                existing_rows = (
                    session.query(SQLAAnnotation.frame_number)
                    .filter(
                        SQLAAnnotation.media_id == media.id,
                        SQLAAnnotation.layer_id == layer.id,
                        SQLAAnnotation.frame_number.in_(targets),
                    )
                    .distinct()
                    .all()
                )
                has_court = {fn for (fn,) in existing_rows}
            else:
                has_court = set()

            for frame in targets:
                if frame in has_court:
                    stats["frames_skipped"] += 1
                    continue

                if mode == "replace":
                    session.query(SQLAAnnotation).filter(
                        SQLAAnnotation.media_id == media.id,
                        SQLAAnnotation.layer_id == layer.id,
                        SQLAAnnotation.frame_number == frame,
                    ).delete(synchronize_session=False)

                for ann in source:
                    session.add(SQLAAnnotation(
                        media_id=media.id,
                        layer_id=layer.id,
                        label_id=ann.label.label_id,
                        frame_number=frame,
                        shape_type=ann.shape_type,
                        geometry=json.dumps(ann.geometry),
                        is_ai_generated=False,  # not model output
                        confirmed=False,  # not visually verified here
                        track_id=ann.track_id,
                        team_id=ann.team_id,
                    ))
                    stats["copied"] += 1

                self._reset_frame_review(session, media.id, layer.id, frame)
                stats["frames_written"] += 1

            session.commit()

        self.cache_court_coordinates(media_path, source_frame)

        return stats

    def cache_court_coordinates(self, media_path: str, frame_number: Optional[int]):
        """
        Recomputes this media's canonical court-geometry cache from the
        court-layer annotations at `frame_number`, grouped by label name
        ("back zone" -> "back_zone", etc.), and stores it on the Media row —
        so any caller can get it with one Media lookup instead of a
        per-frame annotation query.
        """
        court_annotations = self.get_court_annotations(media_path, frame_number)
        if not court_annotations:
            return

        grouped: dict[str, list] = {}
        for ann in court_annotations:
            key = ann.label.name.replace(" ", "_")
            grouped.setdefault(key, []).append(ann.geometry)

        with self.Session() as session:
            media = session.query(Media).filter(Media.path == media_path).first()
            if media is None:
                return
            media.court_coordinates = json.dumps(grouped)
            session.commit()

    def get_media_court_coordinates(self, media_path: str) -> Optional[dict]:
        """The cached {"back_zone": [...], "attack_zone": [...], "net": [...]}
        dict for this media, or None if no court has been cached yet."""
        with self.Session() as session:
            media = session.query(Media).filter(Media.path == media_path).first()
            if media is None or not media.court_coordinates:
                return None
            return json.loads(media.court_coordinates)

    def get_media_court_polygon(self, media_path: str) -> Optional[list]:
        """The whole-court polygon (see compute_full_court_polygon), built
        from this media's cached back-zone shapes and, if drawn, the net's
        top line. None if no court has been drawn/published for this media
        yet."""
        coords = self.get_media_court_coordinates(media_path)
        if not coords or not coords.get("back_zone"):
            return None

        media = self.get_media(media_path)
        if media is None:
            return None

        return compute_full_court_polygon(
            coords["back_zone"], media.width, media.height,
            net_geometries=coords.get("net"),
        )

    def fill_short_game_state_gaps(
            self,
            media_path: str,
            fps: float = 30.0,
            min_gap_seconds: float = 3.0,
            play_start_extension_seconds: float = 1.0,
    ) -> int:
        """
        Fill short implicit no-play gaps between game-state segments.

        The DB does not contain explicit records for these gaps.
        The gap between:

            current.end_frame
            and
            next.start_frame

        is therefore considered the missing/no-play region.

        Supported transitions:

            service -> service
            service -> play
            play    -> play

        Rules:

            service -> service:
                Merge the second service into the first service.

            service -> play:
                Extend the play backwards to immediately after the
                service:

                    play.start_frame = service.end_frame + 1

                The service and play remain separate segments.

            play -> play:
                Merge the second play into the first play.

                The first play keeps its original start.
                The second play's end becomes the new end.
                The merged play is then extended forward by
                min_gap_allowed - 1 frames.

            After all of the above smoothing is complete:

                If a play segment does not have a service segment
                immediately before it, extend its beginning backwards
                by play_start_extension_seconds.

                This is deliberately performed as a SECOND PASS so
                that it cannot interfere with the gap-filling logic.
        """

        segments = self.get_game_state_segments(media_path)

        if not segments:
            return 0

        fps = fps if fps and fps > 0 else 30.0

        # -------------------------------------------------------------
        # Gap configuration.
        # -------------------------------------------------------------

        min_gap_allowed = int(round(min_gap_seconds * fps))

        # Example:
        #
        # 3 seconds * 30 FPS = 90 frames
        # 90 - 1 = 89 frames
        #
        # Used when extending a merged play -> play.
        extension_frames = max(0, min_gap_allowed - 1)

        # -------------------------------------------------------------
        # Second-pass play-start extension configuration.
        # -------------------------------------------------------------

        play_start_extension_frames = int(
            round(play_start_extension_seconds * fps)
        )

        # Always traverse a stable snapshot of the original DB result.
        segments = sorted(
            segments,
            key=lambda s: (s.start_frame, s.end_frame),
        )

        # -------------------------------------------------------------
        # FIRST PASS
        #
        # Fill short implicit gaps and merge segments.
        #
        # Do not modify/remove anything from `segments` while
        # traversing it.
        # -------------------------------------------------------------

        delete_ids = set()

        # segment_id -> (start_frame, end_frame, state)
        updates = {}

        i = 0

        while i + 1 < len(segments):

            current = segments[i]
            next_segment = segments[i + 1]

            # ---------------------------------------------------------
            # Calculate the implicit gap between consecutive segments.
            # ---------------------------------------------------------

            gap_frames = (
                    next_segment.start_frame
                    - current.end_frame
                    - 1
            )

            # No valid gap.
            if gap_frames < 0:
                i += 1
                continue

            # Only process gaps strictly shorter than the configured
            # minimum allowed gap.
            if gap_frames >= min_gap_allowed:
                i += 1
                continue

            # ---------------------------------------------------------
            # CASE 1:
            #
            # service -> service
            #
            # Merge the second service into the first service.
            #
            # Example:
            #
            # service 100 - 200
            # gap     201 - 230
            # service 231 - 300
            #
            # becomes:
            #
            # service 100 - 300
            # ---------------------------------------------------------

            if (
                    current.state == "service"
                    and next_segment.state == "service"
            ):
                updates[current.segment_id] = (
                    current.start_frame,
                    next_segment.end_frame,
                    "service",
                )

                # The second service has been absorbed.
                if next_segment.segment_id is not None:
                    delete_ids.add(next_segment.segment_id)

                # Skip both original segments.
                i += 2
                continue

            # ---------------------------------------------------------
            # CASE 2:
            #
            # service -> play
            #
            # Extend the beginning of play backwards to immediately
            # after the service.
            #
            # Example:
            #
            # service 100 - 200
            # gap     201 - 230
            # play    231 - 400
            #
            # becomes:
            #
            # service 100 - 200
            # play    201 - 400
            #
            # The service itself is not changed.
            # The play segment is not deleted.
            # ---------------------------------------------------------

            if (
                    current.state == "service"
                    and next_segment.state == "play"
            ):
                updates[next_segment.segment_id] = (
                    current.end_frame + 1,
                    next_segment.end_frame,
                    "play",
                )

                # Both segments have now been handled.
                i += 2
                continue

            # ---------------------------------------------------------
            # CASE 3:
            #
            # play -> play
            #
            # Merge the second play into the first.
            #
            # Example:
            #
            # play 100 - 200
            # gap  201 - 230
            # play 231 - 400
            #
            # becomes:
            #
            # play 100 - 489
            #
            # at 30 FPS / 3 seconds:
            #
            # 400 + (90 - 1) = 489
            # ---------------------------------------------------------

            if (
                    current.state == "play"
                    and next_segment.state == "play"
            ):
                merged_end = (
                        next_segment.end_frame
                        + extension_frames
                )

                updates[current.segment_id] = (
                    current.start_frame,
                    merged_end,
                    "play",
                )

                # The second play has been absorbed.
                if next_segment.segment_id is not None:
                    delete_ids.add(next_segment.segment_id)

                # Skip both original segments.
                i += 2
                continue

            # ---------------------------------------------------------
            # Any other transition is left untouched.
            # ---------------------------------------------------------

            i += 1

        # -------------------------------------------------------------
        # Persist FIRST PASS.
        # -------------------------------------------------------------

        changed = 0

        with self.Session() as session:

            # Delete absorbed segments.
            for segment_id in delete_ids:
                session.query(SQLAGameStateSegment).filter(
                    SQLAGameStateSegment.id == segment_id
                ).delete(
                    synchronize_session=False
                )

                changed += 1

            # Apply collected updates.
            for segment_id, (start_frame, end_frame, state) in updates.items():

                if segment_id in delete_ids:
                    continue

                record = session.get(
                    SQLAGameStateSegment,
                    segment_id,
                )

                if record is None:
                    continue

                record.start_frame = start_frame
                record.end_frame = end_frame
                record.state = state

                changed += 1

            session.commit()

        # -------------------------------------------------------------
        # SECOND PASS
        #
        # Reload the final state AFTER smoothing.
        #
        # This is important because the first pass may have:
        #
        #   - merged service segments
        #   - merged play segments
        #   - deleted absorbed segments
        #   - extended play segments
        #
        # We now determine which play segments do not have a service
        # immediately before them.
        # -------------------------------------------------------------

        segments = self.get_game_state_segments(media_path)

        if not segments:
            return changed

        segments = sorted(
            segments,
            key=lambda s: (s.start_frame, s.end_frame),
        )

        start_updates = {}

        for index, segment in enumerate(segments):

            # Only play segments are relevant.
            if segment.state != "play":
                continue

            # ---------------------------------------------------------
            # If this is the first segment in the video, there is no
            # service before it.
            # ---------------------------------------------------------

            if index == 0:

                new_start = max(
                    0,
                    segment.start_frame - play_start_extension_frames,
                )

                if new_start < segment.start_frame:
                    start_updates[segment.segment_id] = (
                        new_start,
                        segment.end_frame,
                    )

                continue

            previous = segments[index - 1]

            # ---------------------------------------------------------
            # If a service exists immediately before this play,
            # service -> play smoothing has already handled it.
            #
            # Do not extend this play backwards again.
            # ---------------------------------------------------------

            if previous.state == "service":
                continue

            # ---------------------------------------------------------
            # No service immediately precedes this play.
            #
            # Extend the beginning backwards by 1 second.
            #
            # This catches cases such as:
            #
            #   play
            #
            # or:
            #
            #   no-play/blank (implicit)
            #   play
            #
            # where the beginning of the rally may have been missed.
            # ---------------------------------------------------------

            new_start = max(
                0,
                segment.start_frame - play_start_extension_frames,
            )

            if new_start < segment.start_frame:
                start_updates[segment.segment_id] = (
                    new_start,
                    segment.end_frame,
                )

        # -------------------------------------------------------------
        # Persist SECOND PASS.
        # -------------------------------------------------------------

        if start_updates:

            with self.Session() as session:

                for segment_id, (start_frame, end_frame) in start_updates.items():

                    record = session.get(
                        SQLAGameStateSegment,
                        segment_id,
                    )

                    if record is None:
                        continue

                    record.start_frame = start_frame
                    record.end_frame = end_frame

                    changed += 1

                session.commit()

        return changed