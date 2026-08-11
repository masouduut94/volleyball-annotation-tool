from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Text,
    UniqueConstraint,
)

from sqlalchemy.orm import declarative_base, relationship

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

    layer_id = Column(
        Integer,
        ForeignKey("layers.id"),
        nullable=False,
    )

    name = Column(String(100), nullable=False)
    color = Column(String(7), nullable=False)

    layer = relationship(
        "Layer",
        back_populates="labels",
    )

    __table_args__ = (
        UniqueConstraint(
            "layer_id",
            "name",
            name="uq_layer_label",
        ),
    )

    def __repr__(self):
        return (
            f"<LayerLabel(name={self.name}, color={self.color})>"
        )


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

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )

    annotations = relationship(
        "Annotation",
        back_populates="media",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Media(path={self.path})>"


# ------------------------------------------------------------------
# Annotation
# ------------------------------------------------------------------

class Annotation(Base):
    __tablename__ = "annotations"

    id = Column(Integer, primary_key=True)

    media_id = Column(
        Integer,
        ForeignKey("media.id"),
        nullable=False,
    )

    layer_id = Column(
        Integer,
        ForeignKey("layers.id"),
        nullable=False,
    )

    frame_number = Column(Integer)

    label_id = Column(
        Integer,
        ForeignKey("labels.id"),
        nullable=False,
    )

    shape_type = Column(String(20), nullable=False)

    geometry = Column(Text, nullable=False)

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    media = relationship(
        "Media",
        back_populates="annotations",
    )

    layer = relationship(
        "Layer",
        back_populates="annotations",
    )

    label = relationship(
        "LayerLabel",
    )

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
# AI model configuration
# ------------------------------------------------------------------

class ModelConfig(Base):
    __tablename__ = "model_configs"

    key = Column(String(50), primary_key=True)

    path = Column(Text)
