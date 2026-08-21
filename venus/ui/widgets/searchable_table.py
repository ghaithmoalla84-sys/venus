# -*- coding: utf-8 -*-
"""
SearchableTable - Venus Coffee
QWidget يحتوي على حقل بحث في الأعلى وجدول QTableWidget أسفله.
يدعم تعبئة البيانات الديناميكية، تصفية فورية (بدون استعلام قاعدة بيانات)،
وإضافة عمود "إجراءات" أخير تلقائياً يحتوي أزرار تعديل وحذف.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QStyle, QApplication,
    QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from venus.ui.styles import Colors, FontSizes, BorderRadius, table_style_compact, ICON_SIZE
from PyQt5.QtGui import QColor, QBrush


class _ActionButton(QPushButton):
    """زر صغير يُستخدم داخل جدول الإجراءات."""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setFixedSize(32, 28)
        self.setStyleSheet("""
            QPushButton {
                border: none;
                background-color: transparent;
                font-size: 15px;
                padding: 2px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #ecf0f1;
            }
        """)


class SearchableTable(QWidget):
    """جدول قابل للبحث مع زرّي تعديل وحذف في كل صف."""

    edit_requested = pyqtSignal(int)
    delete_requested = pyqtSignal(int)
    row_double_clicked = pyqtSignal(int)

    ACTIONS_HEADER = "إجراءات"

    def __init__(self, parent=None, show_actions=True):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._id_column_index = -1
        self._rows_data = []          # البيانات الأصلية (قوائم)
        self._headers = []            # رؤوس الأعمدة الأصلية (بدون عمود الإجراءات)
        self._actions_col_idx = -1    # فهرس عمود الإجراءات
        self._show_actions = show_actions
        self._init_ui()

    # ─────────────────────── البناء الرسومي ───────────────────────

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("بحث في الجدول...")
        self.search_box.textChanged.connect(self._filter_rows)
        layout.addWidget(self.search_box)

        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Interactive)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        # الاتصال مرة واحدة (لا يُعاد ربطه في _render_table لتجنب التكرار)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)

    # ─────────────────────── تعبئة البيانات ───────────────────────

    def set_data(self, headers, rows, id_column_index=-1):
        """
        ملء الجدول بالبيانات.
        :param headers: قائمة بعناوين الأعمدة (بدون عمود الإجراءات).
        :param rows: قائمة بالصفوف؛ كل صف قائمة قيم مطابقة للرؤوس.
        :param id_column_index: فهرس عمود يُستخدم كمعرّف لكل صف.
        """
        self._headers = list(headers)
        self._rows_data = list(rows)
        self._id_column_index = id_column_index

        if self._show_actions:
            display_headers = list(self._headers) + [self.ACTIONS_HEADER]
        else:
            display_headers = list(self._headers)
        self.table.setColumnCount(len(display_headers))
        self.table.setHorizontalHeaderLabels(display_headers)
        self._actions_col_idx = len(self._headers) if self._show_actions else -1

        self._render_table(self._rows_data)

    def _render_table(self, rows):
        self.table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            for col_idx, value in enumerate(row):
                item = QTableWidgetItem(self._to_display(value))
                item.setTextAlignment(self._align_for(col_idx, value))
                if col_idx == self._id_column_index:
                    item.setData(Qt.UserRole, value)
                self.table.setItem(row_idx, col_idx, item)
            if self._show_actions:
                self._insert_action_buttons(row_idx, row)

        self.table.resizeColumnsToContents()
        if self._show_actions and 0 <= self._actions_col_idx < self.table.columnCount():
            self.table.setColumnWidth(self._actions_col_idx, 100)

    def _insert_action_buttons(self, row_idx, row):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)

        edit_btn = _ActionButton()
        edit_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_FileDialogContentsView))
        edit_btn.setToolTip("تعديل")
        edit_btn.setIconSize(ICON_SIZE)
        edit_btn.clicked.connect(lambda _, r=row_idx: self._on_edit(r))
        del_btn = _ActionButton()
        del_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_TrashIcon))
        del_btn.setIconSize(ICON_SIZE)
        del_btn.clicked.connect(lambda _, r=row_idx: self._on_delete(r))
        layout.addWidget(edit_btn)
        layout.addWidget(del_btn)

        self.table.setCellWidget(row_idx, self._actions_col_idx, widget)

    # ─────────────────────── الإشارات والمعالجات ───────────────────────

    def _row_id(self, row_idx):
        if self._id_column_index < 0:
            return row_idx
        item = self.table.item(row_idx, self._id_column_index)
        if item is not None:
            return int(item.text()) if str(item.text()).lstrip("-").isdigit() else row_idx
        # خذ القيمة من البيانات الأصلية إن وجدت
        if 0 <= row_idx < len(self._rows_data):
            value = self._rows_data[row_idx][self._id_column_index]
            try:
                return int(value)
            except (ValueError, TypeError):
                return row_idx
        return row_idx

    def _on_edit(self, row_idx):
        self.edit_requested.emit(self._row_id(row_idx))

    def _on_delete(self, row_idx):
        self.delete_requested.emit(self._row_id(row_idx))

    def _on_cell_double_clicked(self, row, column):
        # تجاهل الضغط على عمود الإجراءات
        if column == self._actions_col_idx:
            return
        self.row_double_clicked.emit(self._row_id(row))

    # ─────────────────────── التصفية ───────────────────────

    def _filter_rows(self, text=None):
        """تصفية الصفوف المعروضة فورياً بناءً على أي عمود نصي
        دون إعادة استعلام قاعدة البيانات."""
        text = text if text is not None else self.search_box.text()
        needle = str(text).strip()
        max_col = self._actions_col_idx if self._show_actions else self.table.columnCount()
        for row_idx in range(self.table.rowCount()):
            hidden = False
            if needle:
                hidden = True
                for col_idx in range(max_col):
                    item = self.table.item(row_idx, col_idx)
                    if item is not None and needle in item.text():
                        hidden = False
                        break
            self.table.setRowHidden(row_idx, hidden)

    def clear_search(self):
        self.search_box.clear()

    def get_visible_row_ids(self):
        """قائمة بمعرّفات الصفوف المرئية بعد التصفية."""
        ids = []
        for row_idx in range(self.table.rowCount()):
            if not self.table.isRowHidden(row_idx):
                ids.append(self._row_id(row_idx))
        return ids

    # ─────────────────────── المساعدات ───────────────────────

    @staticmethod
    def _to_display(value):
        if value is None:
            return ""
        return str(value)

    def _align_for(self, col_idx, value):
        if isinstance(value, (int, float)):
            return Qt.AlignLeft | Qt.AlignVCenter
        return Qt.AlignRight | Qt.AlignVCenter

    def set_id_column_index(self, index):
        self._id_column_index = index

    @property
    def actions_column_index(self):
        return self._actions_col_idx

    def refresh(self):
        """إعادة عرض البيانات الأصلية (بعد مسح التصفية)."""
        self.search_box.clear()
        self._render_table(self._rows_data)
