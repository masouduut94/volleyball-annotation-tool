import math
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class CalibrationStep:
    key: str
    label: str
    kind: str                 # "polygon" | "line"
    points: Optional[int]     # fixed vertex count, None = open-ended polygon
    color: str
    hint: str


CALIBRATION_STEPS = (
    CalibrationStep("court", "Full Court", "polygon", 4, "#FFD814",
                    "Click the 4 corners of the whole court, in any order."),
    CalibrationStep("attack_line_1", "Far Attack Line", "line", 2, "#128DE5",
                    "Click the left end, then the right end, of the far attack line."),
    CalibrationStep("middle_line", "Middle Line", "line", 2, "#FFFFFF",
                    "Click the left end, then the right end, of the middle line."),
    CalibrationStep("attack_line_2", "Near Attack Line", "line", 2, "#128DE5",
                    "Click the left end, then the right end, of the near attack line."),
    CalibrationStep("net", "Net", "polygon", None, "#4927F5",
                    "Click the net's corners. Double-click or press Enter to finish."),
)
STEP_BY_KEY = {s.key: s for s in CALIBRATION_STEPS}

_LINE_PREFIXES = {
    "attack_line_1": "Far Attack Line",
    "middle_line": "Middle Line",
    "attack_line_2": "Near Attack Line",
}


def order_polygon_clockwise(points):
    """Sort vertices around their centroid so a 4-corner click order
    can never produce a self-intersecting bow-tie."""
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    return [list(p) for p in sorted(points, key=lambda p: math.atan2(p[1] - cy, p[0] - cx))]


def compute_point_labels(key: str, points: List[List[float]]) -> List[Optional[str]]:
    """
    Per-point on-screen labels for the calibration overlay, aligned 1:1
    with `points`. A None entry means that point gets no label.

    - "court": labeled by ACTUAL position relative to the shape's own
      centroid (Top/Down x Left/Right) — not by click order — so dragging
      a corner to a different part of the court re-labels it correctly
      instead of the label staying stuck to whichever order it was clicked.
    - line steps (attack_line_1 / middle_line / attack_line_2): point 0 =
      "<Line Name> Left", point 1 = "<Line Name> Right". This DOES rely on
      click order, matching the on-screen hint ("click left end, then
      right end").
    - "net": only the two topmost points are labeled ("Net Left Top" /
      "Net Right Top"); any additional net vertices are left unlabeled.
    """
    if not points:
        return []

    if key == "court":
        if len(points) != 4:
            return [None] * len(points)
        cx = sum(p[0] for p in points) / len(points)
        cy = sum(p[1] for p in points) / len(points)
        labels = []
        for x, y in points:
            vert = "Top" if y < cy else "Down"
            horiz = "Left" if x < cx else "Right"
            labels.append(f"{vert}-{horiz} Corner")
        return labels

    if key in _LINE_PREFIXES:
        prefix = _LINE_PREFIXES[key]
        labels: List[Optional[str]] = [None] * len(points)
        if len(points) >= 1:
            labels[0] = f"{prefix} Left"
        if len(points) >= 2:
            labels[1] = f"{prefix} Right"
        return labels

    if key == "net":
        labels: List[Optional[str]] = [None] * len(points)
        if len(points) < 2:
            return labels
        min_y = min(p[1] for p in points)
        tolerance = 2.0
        top_idxs = [i for i, p in enumerate(points) if p[1] <= min_y + tolerance]
        if len(top_idxs) < 2:
            top_idxs = sorted(range(len(points)), key=lambda i: points[i][1])[:2]
        top_idxs.sort(key=lambda i: points[i][0])  # left-to-right
        left_i, right_i = top_idxs[0], top_idxs[-1]
        labels[left_i] = "Net Left Top"
        labels[right_i] = "Net Right Top"
        return labels

    return [None] * len(points)


def validate_calibration(calibration: dict) -> dict:
    """Keep only well-formed shapes. Partial calibrations are allowed."""
    cleaned = {}
    for key, pts in (calibration or {}).items():
        step = STEP_BY_KEY.get(key)
        if step is None or not pts:
            continue
        try:
            pts = [[float(x), float(y)] for x, y in pts]
        except (TypeError, ValueError):
            continue
        if step.points is not None and len(pts) != step.points:
            continue
        if step.points is None and len(pts) < 3:
            continue
        cleaned[key] = pts
    return cleaned