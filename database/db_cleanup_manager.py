from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from .schema import (
    Base,
    Media,
    Layer as SQLALayer,
    Annotation as SQLAAnnotation,
    GameStateSegment as SQLAGameStateSegment,
)


# ----------------------------------------------------------------------
# Result objects
# ----------------------------------------------------------------------

@dataclass
class DatabaseDeleteFilter:
    """
    Describes exactly what should be removed from the database.

    media_path:
        Exactly one video/media file.

    start_frame / end_frame:
        Inclusive frame range.

    delete_all_frames:
        If True, the frame range is ignored and the entire media is used.

    layers:
        Annotation layers to delete:
            "actions"
            "players"
            "ball"
            "court"

        "game-state" is handled separately because it is not an
        annotation layer in the database schema.

    annotation_origins:
        "ai"     -> is_ai_generated=True
        "human"  -> is_ai_generated=False

    annotation_statuses:
        "confirmed"   -> confirmed=True
        "unconfirmed" -> confirmed=False

    game_state_sources:
        "model"  -> source="model"
        "manual" -> source="manual"
    """

    media_path: str

    start_frame: Optional[int] = None
    end_frame: Optional[int] = None
    delete_all_frames: bool = True

    layers: List[str] = None

    annotation_origins: List[str] = None
    annotation_statuses: List[str] = None

    game_state_sources: List[str] = None

    def __post_init__(self):
        if self.layers is None:
            self.layers = []

        if self.annotation_origins is None:
            self.annotation_origins = []

        if self.annotation_statuses is None:
            self.annotation_statuses = []

        if self.game_state_sources is None:
            self.game_state_sources = []


@dataclass
class DatabaseDeletePreview:
    """
    Number of database records that would be deleted.
    """

    annotation_count: int = 0
    game_state_segment_count: int = 0

    @property
    def total(self) -> int:
        return self.annotation_count + self.game_state_segment_count


@dataclass
class DatabaseDeleteResult:
    """
    Number of records actually removed.
    """

    annotation_count: int = 0
    game_state_segment_count: int = 0

    @property
    def total(self) -> int:
        return self.annotation_count + self.game_state_segment_count


# ----------------------------------------------------------------------
# Database Cleanup Manager
# ----------------------------------------------------------------------

class DatabaseCleanupManager:
    """
    Dedicated database-management class for destructive cleanup
    operations.

    This class deliberately does not modify the normal annotation
    workflow. It operates directly on the same SQLAlchemy database
    schema used by DatabaseManager.

    All deletion operations are executed inside one transaction.
    """

    ANNOTATION_LAYERS = (
        "actions",
        "players",
        "ball",
        "court",
    )

    GAME_STATE_NAME = "game-state"

    ALL_CONTENT_TYPES = ANNOTATION_LAYERS + (
        GAME_STATE_NAME,
    )

    ANNOTATION_ORIGINS = (
        "ai",
        "human",
    )

    ANNOTATION_STATUSES = (
        "confirmed",
        "unconfirmed",
    )

    GAME_STATE_SOURCES = (
        "model",
        "manual",
    )

    def __init__(self, db_path: str = "annotations.db"):
        self.db_path = Path(db_path)

        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            future=True,
            echo=False,
        )

        # Do not create a different schema here.
        #
        # The normal DatabaseManager is responsible for creating the
        # application tables. create_all() is harmless for an existing
        # database and also makes this manager usable on a fresh database.
        Base.metadata.create_all(self.engine)

        self.Session = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )

    # ------------------------------------------------------------------
    # Media
    # ------------------------------------------------------------------

    def get_videos(self) -> List[Media]:
        """
        Return all video media ordered by most recently created.
        """

        with self.Session() as session:
            return (
                session.query(Media)
                .filter(Media.media_type == "video")
                .order_by(Media.created_at.desc())
                .all()
            )

    def get_media(self, media_path: str) -> Optional[Media]:
        with self.Session() as session:
            return (
                session.query(Media)
                .filter(Media.path == media_path)
                .first()
            )

    def get_video_frame_count(self, media_path: str) -> int:
        """
        Return the maximum annotated frame number.

        This is useful when the actual video frame count is not stored
        in the database.

        Returns 0 when there are no frame annotations or game-state
        segments.
        """

        with self.Session() as session:
            media = (
                session.query(Media)
                .filter(Media.path == media_path)
                .first()
            )

            if media is None:
                return 0

            annotation_max = (
                session.query(
                    func.max(SQLAAnnotation.frame_number)
                )
                .filter(
                    SQLAAnnotation.media_id == media.id,
                    SQLAAnnotation.frame_number.isnot(None),
                )
                .scalar()
            )

            segment_max = (
                session.query(
                    func.max(SQLAGameStateSegment.end_frame)
                )
                .filter(
                    SQLAGameStateSegment.media_id == media.id
                )
                .scalar()
            )

            values = [
                value
                for value in (annotation_max, segment_max)
                if value is not None
            ]

            if not values:
                return 0

            return max(values)

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def preview_delete(
            self,
            delete_filter: DatabaseDeleteFilter,
    ) -> DatabaseDeletePreview:
        """
        Calculate exactly how many records would be affected.

        Nothing is modified.

        Game-state segments are counted only when "game-state" is
        explicitly selected.
        """



        with self.Session() as session:
            media = (
                session.query(Media)
                .filter(Media.path == delete_filter.media_path)
                .first()
            )

            self._validate_filter(delete_filter)

            if media is None:
                return DatabaseDeletePreview()

            annotation_count = 0
            game_state_count = 0

            # --------------------------------------------------------------
            # Frame-level annotations
            # --------------------------------------------------------------

            annotation_layers = [
                layer
                for layer in delete_filter.layers
                if layer in self.ANNOTATION_LAYERS
            ]

            if annotation_layers:
                annotation_count = self._count_matching_annotations(
                    session,
                    media.id,
                    delete_filter,
                )

            # --------------------------------------------------------------
            # Game state
            # --------------------------------------------------------------

            if self.GAME_STATE_NAME in delete_filter.layers:
                game_state_count = self._count_matching_game_states(
                    session,
                    media.id,
                    delete_filter,
                )

            return DatabaseDeletePreview(
                annotation_count=annotation_count,
                game_state_segment_count=game_state_count,
            )

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete(
            self,
            delete_filter: DatabaseDeleteFilter,
    ) -> DatabaseDeleteResult:
        """
        Delete exactly the database content selected by the filter.

        Frame-level annotations are controlled by `layers`.

        Game-state segments are controlled independently by whether
        "game-state" is present in `layers`.

        The entire operation is transactional:
            successful -> commit
            failure    -> rollback
        """

        with self.Session() as session:
            media = (
                session.query(Media)
                .filter(Media.path == delete_filter.media_path)
                .first()
            )
            self._validate_filter(delete_filter)
            if media is None:
                return DatabaseDeleteResult()

            annotation_count = 0
            game_state_count = 0

            try:
                # ----------------------------------------------------------
                # Frame-level annotations
                #
                # Only the explicitly selected annotation layers are touched.
                # ----------------------------------------------------------

                annotation_layers = [
                    layer
                    for layer in delete_filter.layers
                    if layer in self.ANNOTATION_LAYERS
                ]

                if annotation_layers:
                    annotation_query = self._build_annotation_query(
                        session,
                        media.id,
                        delete_filter,
                    )

                    annotation_count = annotation_query.delete(
                        synchronize_session=False
                    )

                # ----------------------------------------------------------
                # Game-state segments
                #
                # IMPORTANT:
                # Game State is NOT an annotation layer. It must only be
                # touched when explicitly selected by the user.
                # ----------------------------------------------------------

                if self.GAME_STATE_NAME in delete_filter.layers:
                    game_state_count = self._delete_game_state_segments(
                        session,
                        media.id,
                        delete_filter,
                    )

                # ----------------------------------------------------------
                # Commit everything atomically.
                # ----------------------------------------------------------

                session.commit()

                return DatabaseDeleteResult(
                    annotation_count=annotation_count,
                    game_state_segment_count=game_state_count,
                )

            except Exception:
                session.rollback()
                raise

    # ------------------------------------------------------------------
    # Annotation query
    # ------------------------------------------------------------------

    def _build_annotation_query(
            self,
            session,
            media_id: int,
            delete_filter: DatabaseDeleteFilter,
    ):
        """
        Build the SQLAlchemy query for frame-level annotations.
        """

        query = (
            session.query(SQLAAnnotation)
            .filter(
                SQLAAnnotation.media_id == media_id
            )
        )

        # --------------------------------------------------------------
        # Frame range
        # --------------------------------------------------------------

        if not delete_filter.delete_all_frames:
            start_frame, end_frame = self._normalized_range(
                delete_filter
            )

            query = query.filter(
                SQLAAnnotation.frame_number >= start_frame,
                SQLAAnnotation.frame_number <= end_frame,
            )

        # --------------------------------------------------------------
        # Layer selection
        # --------------------------------------------------------------

        selected_layers = [
            layer
            for layer in delete_filter.layers
            if layer in self.ANNOTATION_LAYERS
        ]

        if not selected_layers:
            # No annotation layers selected.
            #
            # Return an always-false condition rather than accidentally
            # deleting annotations.
            return query.filter(SQLAAnnotation.id == -1)

        layer_rows = (
            session.query(SQLALayer.id)
            .filter(
                SQLALayer.name.in_(selected_layers)
            )
            .all()
        )

        layer_ids = [
            layer_id
            for (layer_id,) in layer_rows
        ]

        if not layer_ids:
            return query.filter(SQLAAnnotation.id == -1)

        query = query.filter(
            SQLAAnnotation.layer_id.in_(layer_ids)
        )

        # --------------------------------------------------------------
        # AI / human origin
        # --------------------------------------------------------------

        origin_conditions = []

        if "ai" in delete_filter.annotation_origins:
            origin_conditions.append(
                SQLAAnnotation.is_ai_generated.is_(True)
            )

        if "human" in delete_filter.annotation_origins:
            origin_conditions.append(
                SQLAAnnotation.is_ai_generated.is_(False)
            )

        if origin_conditions:
            from sqlalchemy import or_

            query = query.filter(
                or_(*origin_conditions)
            )
        else:
            # Nothing selected means nothing should be deleted.
            return query.filter(SQLAAnnotation.id == -1)

        # --------------------------------------------------------------
        # Confirmation status
        # --------------------------------------------------------------

        status_conditions = []

        if "confirmed" in delete_filter.annotation_statuses:
            status_conditions.append(
                SQLAAnnotation.confirmed.is_(True)
            )

        if "unconfirmed" in delete_filter.annotation_statuses:
            status_conditions.append(
                SQLAAnnotation.confirmed.is_(False)
            )

        if status_conditions:
            from sqlalchemy import or_

            query = query.filter(
                or_(*status_conditions)
            )
        else:
            return query.filter(SQLAAnnotation.id == -1)

        return query

    def _count_matching_annotations(
            self,
            session,
            media_id: int,
            delete_filter: DatabaseDeleteFilter,
    ) -> int:

        query = self._build_annotation_query(
            session,
            media_id,
            delete_filter,
        )

        return query.count()

    # ------------------------------------------------------------------
    # Game-state query
    # ------------------------------------------------------------------

    def _build_game_state_query(
            self,
            session,
            media_id: int,
            delete_filter: DatabaseDeleteFilter,
    ):
        """
        Build a query for game-state segments that intersect the
        selected frame range.
        """

        query = (
            session.query(SQLAGameStateSegment)
            .filter(
                SQLAGameStateSegment.media_id == media_id
            )
        )

        # --------------------------------------------------------------
        # Source
        # --------------------------------------------------------------

        sources = [
            source
            for source in delete_filter.game_state_sources
            if source in self.GAME_STATE_SOURCES
        ]

        if not sources:
            return query.filter(SQLAGameStateSegment.id == -1)

        query = query.filter(
            SQLAGameStateSegment.source.in_(sources)
        )

        # --------------------------------------------------------------
        # Frame range
        # --------------------------------------------------------------

        if not delete_filter.delete_all_frames:
            start_frame, end_frame = self._normalized_range(
                delete_filter
            )

            # Any segment intersecting the selected range.
            query = query.filter(
                SQLAGameStateSegment.start_frame <= end_frame,
                SQLAGameStateSegment.end_frame >= start_frame,
            )

        return query

    def _count_matching_game_states(
            self,
            session,
            media_id: int,
            delete_filter: DatabaseDeleteFilter,
    ) -> int:

        query = self._build_game_state_query(
            session,
            media_id,
            delete_filter,
        )

        return query.count()

    # ------------------------------------------------------------------
    # Game-state deletion
    # ------------------------------------------------------------------

    def _delete_game_state_segments(
            self,
            session,
            media_id: int,
            delete_filter: DatabaseDeleteFilter,
    ) -> int:
        """
        Delete or trim game-state segments.

        If All Frames is selected:
            delete the entire matching segment.

        If a frame range is selected:
            - fully inside -> delete
            - left overlap  -> trim right side
            - right overlap -> trim left side
            - surrounds entire segment -> delete
            - selected range lies inside segment -> split into two
              remaining segments

        The return value is the number of original segment records
        affected/deleted.
        """

        query = self._build_game_state_query(
            session,
            media_id,
            delete_filter,
        )

        segments = query.all()

        if not segments:
            return 0

        # --------------------------------------------------------------
        # Entire media
        # --------------------------------------------------------------

        if delete_filter.delete_all_frames:
            count = len(segments)

            for segment in segments:
                session.delete(segment)

            session.flush()
            return count

        # --------------------------------------------------------------
        # Selected range
        # --------------------------------------------------------------

        start_frame, end_frame = self._normalized_range(
            delete_filter
        )

        affected_count = 0

        for segment in segments:
            affected_count += 1

            segment_start = segment.start_frame
            segment_end = segment.end_frame

            starts_before = segment_start < start_frame
            ends_after = segment_end > end_frame

            # ----------------------------------------------------------
            # Segment completely surrounds selected range.
            #
            # Example:
            # segment = 100 -------- 500
            # delete =       200 -- 300
            #
            # Keep:
            # 100 -------- 199
            # 301 -------- 500
            # ----------------------------------------------------------

            if starts_before and ends_after:
                right_segment = SQLAGameStateSegment(
                    media_id=media_id,
                    start_frame=end_frame + 1,
                    end_frame=segment_end,
                    state=segment.state,
                    confidence=segment.confidence,
                    source=segment.source,
                )

                segment.end_frame = start_frame - 1

                session.add(right_segment)

            # ----------------------------------------------------------
            # Segment starts before deletion but ends inside it.
            # ----------------------------------------------------------

            elif starts_before:
                segment.end_frame = start_frame - 1

            # ----------------------------------------------------------
            # Segment starts inside deletion but continues afterwards.
            # ----------------------------------------------------------

            elif ends_after:
                segment.start_frame = end_frame + 1

            # ----------------------------------------------------------
            # Segment is completely covered by deletion.
            # ----------------------------------------------------------

            else:
                session.delete(segment)

        session.flush()

        return affected_count

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalized_range(
            delete_filter: DatabaseDeleteFilter,
    ):
        if (
                delete_filter.start_frame is None
                or delete_filter.end_frame is None
        ):
            raise ValueError(
                "A start and end frame are required when "
                "delete_all_frames=False."
            )

        start_frame = min(
            delete_filter.start_frame,
            delete_filter.end_frame,
        )

        end_frame = max(
            delete_filter.start_frame,
            delete_filter.end_frame,
        )

        return start_frame, end_frame

    def _validate_filter(self, delete_filter: DatabaseDeleteFilter):
        if not delete_filter.media_path:
            raise ValueError("No video was selected.")

        invalid_layers = set(delete_filter.layers) - set(
            self.ALL_CONTENT_TYPES
        )

        if invalid_layers:
            raise ValueError(
                f"Unknown content types: {sorted(invalid_layers)}"
            )
