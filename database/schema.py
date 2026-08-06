from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)

    labels = relationship(
        "Label",
        back_populates="job",
        cascade="all, delete-orphan",
    )

    annotations = relationship(
        "Annotation",
        back_populates="job",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Job(name={self.name})>"


class Label(Base):
    __tablename__ = "labels"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)

    name = Column(String(100), nullable=False)
    color = Column(String(7), nullable=False, default="#00FF00")

    job = relationship("Job", back_populates="labels")

    __table_args__ = (
        UniqueConstraint("job_id", "name", name="uq_job_label"),
    )

    def __repr__(self):
        return f"<Label(name={self.name}, color={self.color})>"


class Media(Base):
    __tablename__ = "media"

    id = Column(Integer, primary_key=True)

    path = Column(Text, unique=True, nullable=False)
    media_type = Column(String(10), nullable=False)  # image or video

    width = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    annotations = relationship(
        "Annotation",
        back_populates="media",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Media(path={self.path}, type={self.media_type})>"


class Annotation(Base):
    __tablename__ = "annotations"

    id = Column(Integer, primary_key=True)

    media_id = Column(Integer, ForeignKey("media.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)

    frame_number = Column(Integer, nullable=True)

    label_name = Column(String(100), nullable=False)

    shape_type = Column(String(20), nullable=False)  # rectangle or polygon

    geometry = Column(Text, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    media = relationship("Media", back_populates="annotations")
    job = relationship("Job", back_populates="annotations")

    __table_args__ = (
        UniqueConstraint(
            "media_id",
            "job_id",
            "frame_number",
            "label_name",
            "shape_type",
            "geometry",
            name="uq_annotation",
        ),
    )

    def __repr__(self):
        return (
            f"<Annotation(frame={self.frame_number}, "
            f"label={self.label_name})>"
        )


class ModelConfig(Base):
    __tablename__ = "model_configs"

    key = Column(String(50), primary_key=True)
    path = Column(Text, nullable=True)
