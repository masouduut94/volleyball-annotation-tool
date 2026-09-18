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
    is_ai_generated: bool = False
    confirmed: bool = True  # — human-drawn defaults to confirmed
    track_id: Optional[int] = None
    team_id: Optional[int] = None

    def combined_track_id(self) -> Optional[int]:
        """team 1, player 7 -> 107; team 2, player 12 -> 212. Bump the
        multiplier if you ever expect >99 players on one team."""
        if self.team_id is None or self.track_id is None:
            return None
        return self.team_id * 100 + self.track_id


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
