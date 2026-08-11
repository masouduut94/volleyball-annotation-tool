from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QPen, QPolygonF


def rectangle_icon(size=28):
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)

    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(Qt.GlobalColor.white, 2)
    p.setPen(pen)

    p.drawRect(6, 7, size - 12, size - 14)

    p.end()
    return QIcon(pix)


def polygon_icon(size=28):
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)

    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(Qt.GlobalColor.white, 2)
    p.setPen(pen)

    # Pentagon points (centered around 14,14 with radius ~11)
    points = [
        QPointF(14, 3),    # top
        QPointF(24, 9),    # top-right
        QPointF(21, 22),   # bottom-right
        QPointF(7, 22),    # bottom-left
        QPointF(4, 9),     # top-left
    ]

    poly = QPolygonF(points)
    p.drawPolygon(poly)

    # vertex dots
    p.setBrush(Qt.GlobalColor.black)

    for pt in points:
        p.drawEllipse(pt, 2, 2)

    p.end()
    return QIcon(pix)
