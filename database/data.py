from dataclasses import dataclass, field
from typing import List, Optional
from dataclasses_json import dataclass_json


@dataclass_json
@dataclass
class Label:
    name: str
    color: str
    layer: str
    label_id: Optional[int] = None


@dataclass_json
@dataclass
class Layer:
    name: str
    labels: List[Label] = field(default_factory=list)
    layer_id: Optional[int] = None


@dataclass_json
@dataclass
class Annotation:
    media_name: str
    layer: Layer
    label: Label
    frame_number: Optional[int]
    shape_type: str
    geometry: dict | list
    annotation_id: Optional[int] = None  # Optional ID for reference
    is_ai_generated: bool = False  # NEW
    confirmed: bool = True  # NEW — human-drawn defaults to confirmed


@dataclass_json
@dataclass
class GameStateSegment:
    media_name: str
    start_frame: int
    end_frame: int
    state: str
    confidence: float = 0.0
    source: str = "model"          # NEW
    segment_id: Optional[int] = None
