import json
from pathlib import Path
from typing import List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .schema import Base, Job, Label, Media, Annotation, ModelConfig


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
    # Default data
    # ------------------------------------------------------------------

    def _create_default_data(self):
        with self.Session() as session:
            if session.query(Job).count() == 0:
                job = Job(name="Court")

                job.labels = [
                    Label(name="court", color="#00FF00"),
                    Label(name="net", color="#00AAFF"),
                ]

                session.add(job)
                session.commit()

    # ------------------------------------------------------------------
    # Jobs
    # ------------------------------------------------------------------

    def get_jobs(self) -> List[Job]:
        with self.Session() as session:
            return session.query(Job).order_by(Job.name).all()

    def add_job(self, name: str) -> Job:
        with self.Session() as session:
            job = Job(name=name)
            session.add(job)
            session.commit()
            session.refresh(job)
            return job

    def remove_job(self, job_id: int):
        with self.Session() as session:
            job = session.get(Job, job_id)
            if job:
                session.delete(job)
                session.commit()

    # ------------------------------------------------------------------
    # Labels
    # ------------------------------------------------------------------

    def get_labels(self, job_id: int) -> List[Label]:
        with self.Session() as session:
            return (
                session.query(Label)
                .filter(Label.job_id == job_id)
                .order_by(Label.name)
                .all()
            )

    def add_label(self, job_id: int, name: str, color: str) -> Label:
        with self.Session() as session:
            label = Label(
                job_id=job_id,
                name=name,
                color=color,
            )

            session.add(label)
            session.commit()
            session.refresh(label)
            return label

    def update_label_color(self, label_id: int, color: str):
        with self.Session() as session:
            label = session.get(Label, label_id)
            if label:
                label.color = color
                session.commit()

    def remove_label(self, label_id: int):
        with self.Session() as session:
            label = session.get(Label, label_id)
            if label:
                session.delete(label)
                session.commit()

    # ------------------------------------------------------------------
    # Media
    # ------------------------------------------------------------------

    def get_or_create_media(
            self,
            path: str,
            media_type: str,
            width: int,
            height: int,
    ) -> Media:
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

    # ------------------------------------------------------------------
    # Annotations
    # ------------------------------------------------------------------

    def save_annotations(
            self,
            media_path: str,
            media_type: str,
            width: int,
            height: int,
            job_id: int,
            frame_number: Optional[int],
            annotations: List[dict],
    ):
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

            session.query(Annotation).filter(
                Annotation.media_id == media.id,
                Annotation.job_id == job_id,
                Annotation.frame_number == frame_number,
            ).delete()

            for ann in annotations:
                record = Annotation(
                    media_id=media.id,
                    job_id=job_id,
                    frame_number=frame_number,
                    label_name=ann["label"],
                    shape_type=ann["type"],
                    geometry=json.dumps(ann["geometry"]),
                )

                session.add(record)

            session.commit()

    def load_annotations(
            self,
            media_path: str,
            job_id: int,
            frame_number: Optional[int],
    ) -> List[dict]:
        with self.Session() as session:
            media = (
                session.query(Media)
                .filter(Media.path == media_path)
                .first()
            )

            if media is None:
                return []

            records = (
                session.query(Annotation)
                .filter(
                    Annotation.media_id == media.id,
                    Annotation.job_id == job_id,
                    Annotation.frame_number == frame_number,
                )
                .all()
            )

            return [
                {
                    "id": r.id,
                    "label": r.label_name,
                    "type": r.shape_type,
                    "geometry": json.loads(r.geometry),
                }
                for r in records
            ]

    def delete_annotations(
            self,
            media_path: str,
            job_id: int,
            frame_number: Optional[int],
    ):
        with self.Session() as session:
            media = (
                session.query(Media)
                .filter(Media.path == media_path)
                .first()
            )

            if media is None:
                return

            session.query(Annotation).filter(
                Annotation.media_id == media.id,
                Annotation.job_id == job_id,
                Annotation.frame_number == frame_number,
            ).delete()

            session.commit()

    def get_model_path(self, key: str):
        with self.Session() as session:
            config = session.get(ModelConfig, key)
            return config.path if config else None

    def set_model_path(self, key: str, path: str):
        with self.Session() as session:
            config = session.get(ModelConfig, key)

            if config is None:
                config = ModelConfig(key=key, path=path)
                session.add(config)
            else:
                config.path = path

            session.commit()

