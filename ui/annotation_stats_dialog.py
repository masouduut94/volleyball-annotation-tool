"""
Annotation statistics dialog — opened from the top toolbar / a shortcut.
Shows a grouped bar chart (layer x label counts) or a pie chart (share of
total annotations per layer), plus an exact-numbers table. No external
charting library — both charts are hand-drawn with QPainter to avoid a
new dependency.
"""

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QFont
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
                             QWidget, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton)

PALETTE = ["#F5276C", "#F5B027", "#4927F5", "#3DDC84", "#00C8FF", "#B027F5",
          "#FF7A29", "#6CF527", "#FFD814", "#27D3F5"]


class GroupedBarChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = {}  # {layer: {label: count}}
        self.setMinimumHeight(280)

    def set_data(self, data):
        self.data = data or {}
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#1E1F24"))

        if not self.data:
            painter.setPen(QColor("#8A93A3"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No annotations yet.")
            return

        margin_left, margin_bottom, margin_top, margin_right = 50, 60, 20, 20
        chart_rect = QRectF(
            margin_left, margin_top,
            self.width() - margin_left - margin_right,
            self.height() - margin_top - margin_bottom,
        )

        layers = list(self.data.keys())
        all_labels = []
        for counts in self.data.values():
            for name in counts:
                if name not in all_labels:
                    all_labels.append(name)
        label_colors = {name: PALETTE[i % len(PALETTE)] for i, name in enumerate(all_labels)}

        max_count = max((max(c.values()) if c else 0) for c in self.data.values())
        max_count = max(max_count, 1)

        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)

        steps = 5
        for i in range(steps + 1):
            y = chart_rect.bottom() - (chart_rect.height() * i / steps)
            painter.setPen(QColor("#3A3D46"))
            painter.drawLine(int(chart_rect.left()), int(y), int(chart_rect.right()), int(y))
            painter.setPen(QColor("#8A93A3"))
            painter.drawText(QRectF(0, y - 8, margin_left - 6, 16),
                              Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                              str(round(max_count * i / steps)))

        group_width = chart_rect.width() / max(len(layers), 1)
        for gi, layer_name in enumerate(layers):
            counts = self.data[layer_name]
            labels_here = [l for l in all_labels if l in counts]
            if not labels_here:
                continue
            bar_slot = group_width * 0.8
            bar_width = bar_slot / max(len(labels_here), 1)
            group_left = chart_rect.left() + gi * group_width + group_width * 0.1

            for li, label_name in enumerate(labels_here):
                count = counts[label_name]
                bar_height = (count / max_count) * chart_rect.height()
                x = group_left + li * bar_width
                y = chart_rect.bottom() - bar_height
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(label_colors[label_name]))
                painter.drawRoundedRect(QRectF(x + 1, y, bar_width - 2, bar_height), 3, 3)

            painter.setPen(QColor("#C7CBD4"))
            painter.drawText(
                QRectF(chart_rect.left() + gi * group_width, chart_rect.bottom() + 4,
                       group_width, margin_bottom - 8),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                layer_name.capitalize(),
            )

        legend_y = self.height() - 18
        lx = margin_left
        for label_name in all_labels:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(label_colors[label_name]))
            painter.drawRect(QRectF(lx, legend_y, 10, 10))
            painter.setPen(QColor("#C7CBD4"))
            painter.drawText(QRectF(lx + 14, legend_y - 3, 120, 16),
                              Qt.AlignmentFlag.AlignVCenter, label_name)
            lx += 14 + painter.fontMetrics().horizontalAdvance(label_name) + 24


class PieChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = {}  # {layer: total_count}
        self.setMinimumHeight(280)

    def set_data(self, totals):
        self.data = totals or {}
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#1E1F24"))

        total = sum(self.data.values())
        if total <= 0:
            painter.setPen(QColor("#8A93A3"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No annotations yet.")
            return

        side = min(self.width(), self.height()) - 80
        rect = QRectF((self.width() - side) / 2 - 70, (self.height() - side) / 2, side, side)

        start_angle = 90 * 16
        names = list(self.data.keys())
        for i, name in enumerate(names):
            span = int(-(self.data[name] / total) * 360 * 16)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(PALETTE[i % len(PALETTE)]))
            painter.drawPie(rect, start_angle, span)
            start_angle += span

        legend_x = rect.right() + 30
        legend_y = rect.top()
        for i, name in enumerate(names):
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(PALETTE[i % len(PALETTE)]))
            painter.drawRect(QRectF(legend_x, legend_y + i * 22, 12, 12))
            painter.setPen(QColor("#C7CBD4"))
            pct = self.data[name] / total * 100
            painter.drawText(QRectF(legend_x + 18, legend_y + i * 22 - 4, 180, 20),
                              Qt.AlignmentFlag.AlignVCenter,
                              f"{name.capitalize()}: {self.data[name]} ({pct:.0f}%)")


class AnnotationStatsDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Annotation Statistics")
        self.resize(680, 560)

        layout = QVBoxLayout(self)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Chart:"))
        self.chart_selector = QComboBox()
        self.chart_selector.addItems(["Bar chart (by layer & label)", "Pie chart (by layer)"])
        self.chart_selector.currentIndexChanged.connect(self._on_chart_changed)
        top_row.addWidget(self.chart_selector)
        top_row.addStretch()

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.reload_data)
        top_row.addWidget(self.refresh_button)
        layout.addLayout(top_row)

        self.bar_chart = GroupedBarChart()
        self.pie_chart = PieChart()
        self.pie_chart.setVisible(False)
        layout.addWidget(self.bar_chart)
        layout.addWidget(self.pie_chart)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Layer", "Label", "Count"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        self.reload_data()

    def _on_chart_changed(self, index):
        self.bar_chart.setVisible(index == 0)
        self.pie_chart.setVisible(index == 1)

    def reload_data(self):
        data = self.db.get_annotation_counts()
        self.bar_chart.set_data(data)

        totals = {layer: sum(counts.values()) for layer, counts in data.items()}
        self.pie_chart.set_data(totals)

        rows = [
            (layer_name, label_name, count)
            for layer_name, counts in data.items()
            for label_name, count in counts.items()
        ]
        self.table.setRowCount(len(rows))
        for r, (layer_name, label_name, count) in enumerate(rows):
            self.table.setItem(r, 0, QTableWidgetItem(layer_name.capitalize()))
            self.table.setItem(r, 1, QTableWidgetItem(label_name))
            self.table.setItem(r, 2, QTableWidgetItem(str(count)))