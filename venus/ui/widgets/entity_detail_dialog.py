# -*- coding: utf-8 -*-
"""
EntityDetailDialog - Venus Coffee
QDialog عام إعادة الاستخدام لعرض تفاصيل أي كيان (مادة، دائن، مجموعة...).
يعرض أزواجاً مفتاح/قيمة في أعلى، وجدولاً للسجلات المرتبطة (اختياري) في الأسفل.
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLabel, QDialogButtonBox,
    QTableWidget, QTableWidgetItem, QGroupBox, QHeaderView,
    QTabWidget, QWidget,
)
from PyQt5.QtCore import Qt
from venus.ui.styles import Colors, FontSizes, Spacing, BorderRadius, group_box_style, table_style


class EntityDetailDialog(QDialog):
    """نافذة تفاصيل كيان عامة وقابلة لإعادة الاستخدام."""

    def __init__(self, title, detail_data=None, related_rows=None,
                 related_headers=None, related_rows_2=None,
                 related_headers_2=None, parent=None):
        """
        :param title: عنوان النافذة.
        :param detail_data: قاموس (key -> value) لعرض البيانات الأساسية.
        :param related_rows: قائمة صفوف (قوائم/كوادين) للجدول السفلي (اختياري).
        :param related_headers: عناوين أعمدة الجدول المرتبط (اختياري).
        :param related_rows_2: قائمة صفوف للجدول الثاني (اختياري).
        :param related_headers_2: عناوين أعمدة الجدول الثاني (اختياري).
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setLayoutDirection(Qt.RightToLeft)
        self.setMinimumWidth(500)
        self._detail_data = detail_data or {}
        self._related_rows = related_rows
        self._related_headers = related_headers
        self._related_rows_2 = related_rows_2
        self._related_headers_2 = related_headers_2
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # ── قسم البيانات الأساسية ──
        form_group = QGroupBox("📋 البيانات الأساسية")
        form_group.setStyleSheet(group_box_style(Colors.PRIMARY))
        form = QFormLayout(form_group)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        for key, value in self._detail_data.items():
            row_label = QLabel(self._safe_text(value))
            row_label.setTextFormat(Qt.RichText)
            row_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            form.addRow(QLabel(self._safe_text(key) + ":"), row_label)

        layout.addWidget(form_group)

        # ── جداول السجلات المرتبطة (اختياري) ──
        if self._related_rows or self._related_rows_2:
            if self._related_rows and self._related_rows_2:
                tab_widget = QTabWidget()
                tab_widget.setLayoutDirection(Qt.RightToLeft)

                tab1 = QWidget()
                tab1_layout = QVBoxLayout(tab1)
                tab1_layout.setContentsMargins(0, 0, 0, 0)
                self._build_related_table(tab1_layout, self._related_rows, self._related_headers)
                tab_widget.addTab(tab1, "📎 السجلات المرتبطة")

                tab2 = QWidget()
                tab2_layout = QVBoxLayout(tab2)
                tab2_layout.setContentsMargins(0, 0, 0, 0)
                self._build_related_table(tab2_layout, self._related_rows_2, self._related_headers_2)
                tab_widget.addTab(tab2, "📊 مقارنة الأسعار")

                layout.addWidget(tab_widget)
            elif self._related_rows:
                self._build_related_table(layout, self._related_rows, self._related_headers)
            elif self._related_rows_2:
                self._build_related_table(layout, self._related_rows_2, self._related_headers_2)

        # ── الأزرار ──
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.setLayoutDirection(Qt.RightToLeft)
        btn_ok = buttons.button(QDialogButtonBox.Ok)
        btn_ok.setText("إغلاق")
        btn_cancel = buttons.button(QDialogButtonBox.Cancel)
        btn_cancel.setText("إلغاء")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_related_table(self, parent_layout, related_rows, related_headers):
        related_group = QGroupBox("📎 سجلات مرتبطة")
        related_group.setStyleSheet(group_box_style(Colors.SECONDARY_TEXT))
        table_layout = QVBoxLayout(related_group)

        self.related_table = QTableWidget()
        if related_headers:
            self.related_table.setColumnCount(len(related_headers))
            self.related_table.setHorizontalHeaderLabels(list(related_headers))
            self.related_table.horizontalHeader().setStretchLastSection(True)
            self.related_table.horizontalHeader().setSectionResizeMode(
                QHeaderView.Interactive)
        else:
            self.related_table.setColumnCount(1)
            self.related_table.setHorizontalHeaderLabels(["البيانات"])

        self.related_table.setRowCount(len(related_rows))
        self.related_table.verticalHeader().setVisible(False)
        self.related_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.related_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.related_table.setStyleSheet(table_style(Colors.PURPLE))

        for row_idx, row in enumerate(related_rows):
            values = list(row) if row else []
            for col_idx in range(self.related_table.columnCount()):
                text = self._safe_text(values[col_idx]) if col_idx < len(values) else ""
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.related_table.setItem(row_idx, col_idx, item)

        self.related_table.resizeColumnsToContents()
        table_layout.addWidget(self.related_table)
        parent_layout.addWidget(related_group)

    @staticmethod
    def _safe_text(value):
        if value is None:
            return ""
        if isinstance(value, bool):
            return "نعم" if value else "لا"
        return str(value)
