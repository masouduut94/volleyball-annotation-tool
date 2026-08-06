from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

Point = Tuple[float, float]


@dataclass
class AnnotationBase:
    label: str
    color: str

    def to_dict(self) -> dict:
        raise NotImplementedError


@dataclass
class RectangleAnnotation(AnnotationBase):
    x: float
    y: float
    width: float
    height: float

    @property
    def left(self):
        return self.x

    @property
    def top(self):
        return self.y

    @property
    def right(self):
        return self.x + self.width

    @property
    def bottom(self):
        return self.y + self.height

    def to_dict(self) -> dict:
        return {
            "type": "rectangle",
            "label": self.label,
            "geometry": {
                "x": self.x,
                "y": self.y,
                "width": self.width,
                "height": self.height,
            },
        }


@dataclass
class PolygonAnnotation(AnnotationBase):
    points: List[Point]

    def to_dict(self) -> dict:
        return {
            "type": "polygon",
            "label": self.label,
            "geometry": [
                [float(x), float(y)] for x, y in self.points
            ],
        }

    def add_point(self, point: Point):
        self.points.append(point)

    def move_point(self, index: int, point: Point):
        self.points[index] = point
