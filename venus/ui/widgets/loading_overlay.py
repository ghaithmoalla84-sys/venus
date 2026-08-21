# -*- coding: utf-8 -*-
"""
LoadingOverlay - Venus Coffee
ودجة تراكب خفيفة تعرض مؤشر تحميل دوّار أثناء تنفيذ الاستعلامات.
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QMovie, QPixmap
import os


class LoadingOverlay(QWidget):
    """تراكب شبه شفاف يعرض مؤشر تحميل دوّار."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.hide()

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        self.spinner = QLabel()
        self.spinner.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.spinner, alignment=Qt.AlignCenter)

        assets_dir = os.path.join(os.path.dirname(__file__), "..", "assets")
        spinner_path = os.path.join(assets_dir, "loading_spinner.gif")
        if os.path.exists(spinner_path):
            self.movie = QMovie(spinner_path)
            self.spinner.setMovie(self.movie)
        else:
            self.movie = None
            self.spinner.setPixmap(QPixmap())

    def start(self):
        self.show()
        self.raise_()
        self.setGeometry(self.parent().rect())
        if self.movie:
            self.movie.start()
            self.movie.setPaused(False)

    def stop(self):
        if self.movie:
            self.movie.stop()
        self.hide()

    def resizeEvent(self, event):
        if self.parent():
            self.setGeometry(self.parent().rect())
        super().resizeEvent(event)
