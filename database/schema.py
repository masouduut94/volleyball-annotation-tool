from datetime import datetime
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import (Column, Integer, String, DateTime, ForeignKey, Text,
                        UniqueConstraint, Boolean, Float)

Base = declarative_base()


# ------------------------------------------------------------------
# Layer
# ------------------------------------------------------------------


class Layer(Base):
    __tablename__ = "layers"  # keep old table name

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)

    labels = relationship(
        "LayerLabel",
        back_populates="layer",
        cascade="all, delete-orphan",
    )

    annotations = relationship(
        "Annotation",
        back_populates="layer",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Layer(name={self.name})>"


# ------------------------------------------------------------------
# Layer labels
# ------------------------------------------------------------------

class LayerLabel(Base):
    __tablename__ = "labels"  # keep old table name

    id = Column(Integer, primary_key=True)
    layer_id = Column(Integer, ForeignKey("layers.id"), nullable=False)
    name = Column(String(100), nullable=False)
    color = Column(String(7), nullable=False)
    layer = relationship("Layer", back_populates="labels")

    __table_args__ = (UniqueConstraint("layer_id", "name", name="uq_layer_label"),)

    def __repr__(self):
        return f"<LayerLabel(name={self.name}, color={self.color})>"


# ------------------------------------------------------------------
# Media
# ------------------------------------------------------------------

class Media(Base):
    __tablename__ = "media"

    id = Column(Integer, primary_key=True)
    path = Column(Text, unique=True, nullable=False)
    media_type = Column(String(10), nullable=False)
    width = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, )

    annotations = relationship(
        "Annotation",
        back_populates="media",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Media(path={self.path})>"


# ------------------------------------------------------------------
# Annotation
# ------------------------------------------------------------------

class Annotation(Base):
    __tablename__ = "annotations"

    id = Column(Integer, primary_key=True)
    is_ai_generated = Column(Boolean, nullable=False, default=False)
    confirmed = Column(Boolean, nullable=False, default=True)
    media_id = Column(Integer, ForeignKey("media.id"), nullable=False, )
    layer_id = Column(Integer, ForeignKey("layers.id"), nullable=False, )
    frame_number = Column(Integer)
    label_id = Column(Integer, ForeignKey("labels.id"), nullable=False, )
    shape_type = Column(String(20), nullable=False)
    geometry = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, )
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, )
    media = relationship("Media", back_populates="annotations", )
    layer = relationship("Layer", back_populates="annotations", )
    label = relationship("LayerLabel", )
    __table_args__ = (
        UniqueConstraint(
            "media_id",
            "layer_id",
            "frame_number",
            "label_id",
            "shape_type",
            "geometry",
            name="uq_annotation",
        ),
    )

    def __repr__(self):
        return (
            f"<Annotation(frame={self.frame_number}, layer={self.layer_id})>"
        )


# ------------------------------------------------------------------
# Frame-Review
# ------------------------------------------------------------------


class FrameReview(Base):
    """
    Human sign-off for a (media, layer, frame) combination. If this row is
    confirmed=True, every annotation in that frame/layer has been reviewed
    by a human. Adding new AI detections to a frame resets this to False.
    """
    __tablename__ = "frame_reviews"

    id = Column(Integer, primary_key=True)
    media_id = Column(Integer, ForeignKey("media.id"), nullable=False)
    layer_id = Column(Integer, ForeignKey("layers.id"), nullable=False)
    frame_number = Column(Integer)

    confirmed = Column(Boolean, nullable=False, default=False)
    confirmed_at = Column(DateTime)

    __table_args__ = (
        UniqueConstraint(
            "media_id",
            "layer_id",
            "frame_number",
            name="uq_frame_review"
        ),
    )

    def __repr__(self):
        return f"<FrameReview(frame={self.frame_number}, confirmed={self.confirmed})>"


# ------------------------------------------------------------------
# AI model configuration
# ------------------------------------------------------------------

class ModelConfig(Base):
    __tablename__ = "model_configs"

    key = Column(String(50), primary_key=True)
    path = Column(Text)


# ------------------------------------------------------------------
# AI Video Game Status Classifier
# ------------------------------------------------------------------


class GameStateSegment(Base):
    __tablename__ = "game_state_segments"

    id = Column(Integer, primary_key=True)
    media_id = Column(Integer, ForeignKey("media.id"), nullable=False)
    start_frame = Column(Integer, nullable=False)
    end_frame = Column(Integer, nullable=False)
    state = Column(String(20), nullable=False)
    confidence = Column(Float, nullable=False, default=0.0)
    source = Column(String(10), nullable=False, default="model")  # NEW: "model" | "manual"
    created_at = Column(DateTime, default=datetime.utcnow)

    media = relationship("Media", backref="game_state_segments")

    __table_args__ = (
        UniqueConstraint("media_id", "start_frame", "end_frame", name="uq_game_state_segment"),
    )
