# -*- coding: utf-8 -*-
"""
SearchableMaterialCombo - Venus Coffee
مكوّن اختيار مادة مع بحث حي وتصنيف حسب المجموعة.
يظهر نافذة منبثقة تحتوي على حقل بحث وقائمة مصنّفة بالمواد.
"""

from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QPushButton, QFrame, QVBoxLayout,
    QListWidget, QListWidgetItem, QApplication
)
from PyQt5.QtCore import Qt, QPoint, pyqtSignal
from PyQt5.QtGui import QColor, QBrush
from venus.ui.styles import input_style
from venus.utils.currency import fmt
from venus.utils.logger import setup_logger

logger = setup_logger()


class SearchableMaterialCombo(QWidget):
    """مربع اختيار مادة مع بحث وتصنيف."""

    value_changed = pyqtSignal(object)

    def __init__(self, load_func, add_dialog_func, parent=None,
                 button_text="➕", table_widget=None, current_row=None,
                 on_duplicate_check=None):
        super().__init__(parent)
        self._load_func = load_func
        self._add_dialog_func = add_dialog_func
        self._table_widget = table_widget
        self._current_row = current_row
        self._on_duplicate_check = on_duplicate_check
        self._button_text = button_text
        self._all_items = []
        self._selected_value = None
        self._popup = None
        self._popup_list = None
        self._popup_search = None
        self._init_ui()
        self.refresh()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._display_edit = QLineEdit()
        self._display_edit.setReadOnly(True)
        self._display_edit.setPlaceholderText("-- اختر المادة --")
        self._display_edit.setStyleSheet(input_style())
        self._display_edit.setMinimumWidth(190)
        self._display_edit.setCursor(Qt.PointingHandCursor)
        self._display_edit.mousePressEvent = self._on_display_clicked

        self._add_btn = QPushButton(self._button_text)
        self._add_btn.setFixedSize(28, 28)
        self._add_btn.setCursor(Qt.PointingHandCursor)
        self._add_btn.clicked.connect(self._on_add_clicked)

        layout.addWidget(self._display_edit)
        layout.addWidget(self._add_btn)

    def refresh(self, select_value=None):
        try:
            items = self._load_func()
        except Exception as e:
            logger.error(f"SearchableMaterialCombo.refresh خطأ: {e}")
            items = []
        self._all_items = items if items else []
        if select_value is not None:
            self._select_value(select_value)

    def _select_value(self, value):
        for item in self._all_items:
            if item['id'] == value:
                self._selected_value = value
                self._display_edit.setText(item['name'])
                self._display_edit.setToolTip(item['name'])
                return
        self._selected_value = None
        self._display_edit.clear()
        self._display_edit.setPlaceholderText("-- اختر المادة --")
        self._display_edit.setToolTip('')

    def _toggle_popup(self):
        if self._popup is not None and self._popup.isVisible():
            self._close_popup()
            return
        self._show_popup()

    def _on_display_clicked(self, event):
        self._toggle_popup()
        event.accept()

    def _show_popup(self):
        self._close_popup()

        popup = QFrame(self, Qt.Popup | Qt.FramelessWindowHint)
        popup.setFrameShape(QFrame.StyledPanel)
        popup_layout = QVBoxLayout(popup)
        popup_layout.setContentsMargins(8, 8, 8, 8)
        popup_layout.setSpacing(4)

        search_edit = QLineEdit()
        search_edit.setPlaceholderText("بحث عن مادة...")
        search_edit.setStyleSheet(input_style())
        search_edit.textChanged.connect(self._filter_list)

        list_widget = QListWidget()
        list_widget.setStyleSheet("QListWidget { border: 1px solid #ddd; }")
        list_widget.itemClicked.connect(self._on_item_activated)
        list_widget.itemActivated.connect(self._on_item_activated)

        popup_layout.addWidget(search_edit)
        popup_layout.addWidget(list_widget)

        popup_width = max(480, int(self.width() * 3.5))
        popup.setFixedWidth(popup_width)
        popup.setFixedHeight(320)

        self_pos = self.mapToGlobal(QPoint(0, 0))
        screen_geo = QApplication.primaryScreen().availableGeometry()
        popup_x = self_pos.x()
        popup_y = self_pos.y() + self.height()
        if popup_x + popup_width > screen_geo.right():
            popup_x = screen_geo.right() - popup_width
        if popup_y + 320 > screen_geo.bottom():
            popup_y = self_pos.y() - 320
        popup.move(popup_x, popup_y)

        self._popup = popup
        self._popup_list = list_widget
        self._popup_search = search_edit
        self._populate_list(list_widget, self._all_items)
        popup.show()
        search_edit.setFocus()

    def _close_popup(self):
        if self._popup is not None:
            self._popup.close()
            self._popup.deleteLater()
            self._popup = None
            self._popup_list = None
            self._popup_search = None

    def _populate_list(self, list_widget, items):
        list_widget.clear()
        list_widget.setSpacing(4)
        if not items:
            empty_item = QListWidgetItem("لا توجد نتائج")
            empty_item.setFlags(Qt.NoItemFlags)
            empty_item.setForeground(QBrush(QColor('#9CA3AF')))
            list_widget.addItem(empty_item)
            return

        groups = {}
        for item in items:
            group = item.get('group', '') or 'بدون مجموعة'
            groups.setdefault(group, []).append(item)

        for group_name in sorted(groups.keys()):
            header = QListWidgetItem(f"  {group_name}  ")
            header.setFlags(Qt.NoItemFlags)
            font = header.font()
            font.setBold(True)
            header.setFont(font)
            header.setBackground(QBrush(QColor('#F3F4F6')))
            header.setForeground(QBrush(QColor('#374151')))
            list_widget.addItem(header)

            for mat in groups[group_name]:
                price = mat.get('last_price') or 0
                text = (f"{mat['name']}  —  آخر سعر: {fmt(price)}  "
                        f"—  المتوفر: {mat.get('qty', 0)} {mat.get('unit', '')}")
                list_item = QListWidgetItem(text)
                list_item.setData(Qt.UserRole, mat['id'])
                list_item.setData(Qt.UserRole + 1, mat)
                list_widget.addItem(list_item)

    def _filter_list(self, text):
        if self._popup_list is None:
            return
        if not text:
            filtered = self._all_items
        else:
            lower = text.lower()
            filtered = [item for item in self._all_items if lower in item['name'].lower()]
        self._populate_list(self._popup_list, filtered)

    def _on_item_activated(self, item):
        if self._popup_list is None:
            return
        data = item.data(Qt.UserRole + 1)
        if data is None:
            return
        value = item.data(Qt.UserRole)

        if self._on_duplicate_check is not None:
            allowed = self._on_duplicate_check(value, self)
            if not allowed:
                self._display_edit.setPlaceholderText("-- اختر المادة --")
                self._display_edit.clear()
                self._selected_value = None
                self._close_popup()
                return

        self._selected_value = value
        self._display_edit.setText(data['name'])
        self.value_changed.emit(value)
        self._close_popup()

    def _on_add_clicked(self):
        if self._add_dialog_func is None:
            return
        new_value = self._add_dialog_func()
        if new_value is None:
            return
        self.refresh(select_value=new_value)

    @property
    def selected_item_data(self):
        if self._selected_value is None:
            return None
        for item in self._all_items:
            if item['id'] == self._selected_value:
                return item
        return None

    @property
    def current_value(self):
        return self._selected_value

    def currentData(self):
        return self._selected_value

    def currentText(self):
        return self._display_edit.text()

    def setCurrentValue(self, value):
        self._select_value(value)

    def findData(self, value):
        for i, item in enumerate(self._all_items):
            if item['id'] == value:
                return i
        return -1

    def setCurrentIndex(self, index):
        if 0 <= index < len(self._all_items):
            self._select_value(self._all_items[index]['id'])
        else:
            self._selected_value = None
            self._display_edit.clear()
            self._display_edit.setPlaceholderText("-- اختر المادة --")
