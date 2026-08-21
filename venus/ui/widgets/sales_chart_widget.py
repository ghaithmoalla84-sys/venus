# -*- coding: utf-8 -*-
"""
SalesChartWidget - Venus Coffee
ودجة رسم بياني بسيط لأحدث 7 أيام من المبيعات باستخدام QPainter
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPainter, QColor, QPen, QFont, QBrush

from venus.ui.styles import Colors, FontSizes


class SalesChartWidget(QWidget):
    """رسم بياني عمودي بسيط لمبيعات آخر 7 أيام."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(220)
        self._data = []
        self._hovered_bar = -1

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.empty_label = QLabel("لا توجد بيانات مبيعات كافية لعرض الرسم البياني")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet(f"""
            color: {Colors.SECONDARY_TEXT};
            font-size: {FontSizes.LG};
            padding: 30px;
            font-style: italic;
        """)
        self.empty_label.hide()
        layout.addWidget(self.empty_label)

        self.setMouseTracking(True)

    def set_data(self, data):
        self._data = data if data else []
        self._hovered_bar = -1
        if not self._data or all(v == 0 for _, v in self._data):
            self.empty_label.show()
            self.setToolTip("")
        else:
            self.empty_label.hide()
        self.update()

    def _bar_at(self, pos):
        if not self._data:
            return -1
        margin = 24
        bottom = self.height() - 40
        top = 36
        chart_w = self.width() - margin * 2
        n = len(self._data)
        bar_w = max(20, min(60, chart_w / n * 0.6))
        gap = (chart_w - bar_w * n) / (n + 1)
        for i in range(n):
            x = margin + gap + (bar_w + gap) * i
            if x <= pos.x() <= x + bar_w and top <= pos.y() <= bottom:
                return i
        return -1

    def mouseMoveEvent(self, event):
        idx = self._bar_at(event.pos())
        if idx != self._hovered_bar:
            self._hovered_bar = idx
            if 0 <= idx < len(self._data):
                label, value = self._data[idx]
                self.setToolTip(f"{label}: {value:,.2f}")
            else:
                self.setToolTip("")
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        if self._hovered_bar != -1:
            self._hovered_bar = -1
            self.setToolTip("")
            self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        if not self._data or all(v == 0 for _, v in self._data):
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        margin = 24
        bottom = self.height() - 40
        top = 36
        chart_h = bottom - top
        chart_w = self.width() - margin * 2
        n = len(self._data)
        max_val = max(v for _, v in self._data)
        if max_val == 0:
            max_val = 1

        bar_w = max(20, min(60, chart_w / n * 0.6))
        gap = (chart_w - bar_w * n) / (n + 1)

        base_color = QColor(Colors.PRIMARY)
        hover_color = QColor(Colors.PRIMARY_HOVER)

        for i, (label, value) in enumerate(self._data):
            x = margin + gap + (bar_w + gap) * i
            bar_h = (value / max_val) * chart_h
            y = bottom - bar_h

            color = hover_color if i == self._hovered_bar else base_color
            painter.fillRect(int(x), int(y), int(bar_w), int(bar_h), color)

            if bar_h > 4:
                painter.setPen(QPen(QColor(Colors.WHITE)))
                painter.setFont(QFont("Arial", 9, QFont.Bold))
                val_text = f"{value:,.0f}" if value >= 1000 else f"{value:,.2f}"
                painter.drawText(int(x), int(y) - 6, int(bar_w), 20,
                                 Qt.AlignCenter, val_text)

            painter.setPen(QPen(QColor(Colors.DARK_TEXT)))
            painter.setFont(QFont("Arial", 9))
            painter.drawText(int(x), bottom + 4, int(bar_w), 32,
                             Qt.AlignCenter, label)

        painter.setPen(QPen(QColor(Colors.BORDER)))
        painter.drawLine(margin, bottom, self.width() - margin, bottom)
