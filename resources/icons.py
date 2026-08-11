import math
from PyQt6.QtGui import QPixmap, QPainter, QPen, QPolygonF, QIcon
from PyQt6.QtCore import Qt, QPointF, QRectF


def rectangle_icon(size=28):
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)

    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(Qt.GlobalColor.white, max(2, size // 12))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)

    # centered rectangle
    margin = size * 0.18
    rect = QRectF(margin, size * 0.22,
                  size - 2 * margin,
                  size * 0.56)
    p.drawRoundedRect(rect, size * 0.08, size * 0.08)

    p.end()
    return QIcon(pix)


def polygon_icon(size=28, sides=6):
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)

    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    margin = size * 0.18
    radius = (size / 2) - margin
    center = QPointF(size / 2, size / 2)

    pen = QPen(Qt.GlobalColor.white, max(2, size // 12))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)

    points = []
    start_angle = -math.pi / 2  # start from top

    for i in range(sides):
        angle = start_angle + (2 * math.pi * i / sides)
        x = center.x() + radius * math.cos(angle)
        y = center.y() + radius * math.sin(angle)
        points.append(QPointF(x, y))

    poly = QPolygonF(points)
    p.drawPolygon(poly)

    # vertex dots
    dot_radius = max(1.5, size * 0.06)
    p.setBrush(Qt.GlobalColor.white)
    p.setPen(Qt.PenStyle.NoPen)

    for pt in points:
        p.drawEllipse(pt, dot_radius, dot_radius)

    p.end()
    return QIcon(pix)
