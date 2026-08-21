# -*- coding: utf-8 -*-
"""
ComboWithQuickAdd - Venus Coffee
QComboBox مصحوف بزر إضافة سريع "➕".
يتيح تمرير دالتي تحميل (load_func) وفتح حوار إضافة (add_dialog_func).
بعد الإضافة الناجحة يُعيد تحميل القائمة ويحدد العنصر الجديد.
"""

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QComboBox, QPushButton
from PyQt5.QtCore import Qt, pyqtSignal
from venus.ui.styles import ICON_SIZE


class ComboWithQuickAdd(QWidget):
    """مربع اختيار مع زر إضافة سريع جانبي."""

    # يُطلق عندما يتغير العنصر المختار (أو يُضاف عنصر جديد)
    value_changed = pyqtSignal(object)

    def __init__(self, load_func, add_dialog_func, parent=None,
                 button_text="➕", combo_style=None, button_style=None):
        """
        :param load_func: استدعاء بلا arguments؛ تُرجع قائمة الخيارات (قيمة أو (عرض، قيمة)).
                          إذا عادت قوائم من زوجات (label, value) فإن القيمة تُخزّن كـ userData.
        :param add_dialog_func: فتح حوار الإضافة؛ يُرجع المعرف/القيمة الجديدة أو None عند الإلغاء.
        """
        super().__init__(parent)
        self._load_func = load_func
        self._add_dialog_func = add_dialog_func
        self.setLayoutDirection(Qt.RightToLeft)
        self._init_ui(combo_style, button_style, button_text)
        self.refresh()

    def _init_ui(self, combo_style, button_style, button_text):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.combo = QComboBox()
        self.combo.currentIndexChanged.connect(self._on_index_changed)
        if combo_style:
            self.combo.setStyleSheet(combo_style)

        self.add_button = QPushButton(button_text)
        self.add_button.setText(button_text)
        self.add_button.setFixedSize(32, 28)
        self.add_button.setIconSize(ICON_SIZE)
        self.add_button.setStyleSheet(button_style or """
            QPushButton {
                border: none;
                background-color: #27ae60;
                color: white;
                font-size: 16px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #229954; }
        """)
        self.add_button.clicked.connect(self._on_add_clicked)

        layout.addWidget(self.combo)
        layout.addWidget(self.add_button)

    # ─────────────────────── العمليات ───────────────────────

    def refresh(self, select_value=None):
        self.combo.blockSignals(True)
        try:
            self.combo.clear()
            if self._load_func is None:
                return
            try:
                items = self._load_func()
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"refresh: فشل تحميل القائمة: {e}", exc_info=True)
                items = []
            select_usr = None
            if items is None:
                items = []

            for item in items:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    label, value = item[0], item[1]
                    self.combo.addItem(str(label), value)
                else:
                    self.combo.addItem(str(item), item)

            if select_value is not None:
                self._select_value(select_value)
            elif self.combo.count() > 0 and self.combo.currentIndex() < 0:
                # اختيار أول عنصر افتراضي لضمان وجود قيمة محددة
                self.combo.setCurrentIndex(0)
        finally:
            self.combo.blockSignals(False)

    def _select_value(self, value):
        for i in range(self.combo.count()):
            if self.combo.itemData(i) == value:
                self.combo.setCurrentIndex(i)
                return
        # اختيار أول عنصر كاحتياطي
        if self.combo.count() > 0:
            self.combo.setCurrentIndex(0)

    def _on_index_changed(self, index):
        if index >= 0:
            self.value_changed.emit(self.combo.itemData(index))

    def _on_add_clicked(self):
        if self._add_dialog_func is None:
            return
        new_value = self._add_dialog_func()
        if new_value is None:
            return
        self.refresh(select_value=new_value)

    # ─────────────────────── واجهة برمجة ───────────────────────

    @property
    def button_text(self):
        return self.add_button.text()

    @button_text.setter
    def button_text(self, text):
        self.add_button.setText(text)

    @property
    def current_value(self):
        idx = self.combo.currentIndex()
        if idx >= 0:
            return self.combo.itemData(idx)
        return None

    @property
    def current_index(self):
        return self.combo.currentIndex()

    @property
    def combo_widget(self):
        return self.combo

    def current_text(self):
        return self.combo.currentText()

    def setCurrentValue(self, value):
        self.refresh(select_value=value)
