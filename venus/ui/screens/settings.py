# -*- coding: utf-8 -*-
"""
شاشة الإعدادات - Venus Coffee
تحتوي على: الأرصدة الافتتاحية، إدارة المجموعات والمواد، سعر الصرف
"""

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from datetime import datetime
import sqlite3
import shutil
import os

from venus.core.database import get_conn, patch_db_path, DATABASE_PATH
from venus.utils.logger import setup_logger
from venus.ui.widgets.delegates import NumericDelegate
from venus.ui.widgets.entity_detail_dialog import EntityDetailDialog
from venus.ui.styles import (
    Colors, FontSizes, Spacing, BorderRadius,
    title_label_style, tab_style, group_box_style, table_style, table_style_compact,
    primary_button_style, success_button_style, danger_button_style,
    warning_button_style, teal_button_style, purple_button_style,
    input_style, combo_style
)

logger = setup_logger()

class SettingsScreen(QWidget):
    """شاشة الإعدادات الرئيسية"""

    def __init__(self):
        super().__init__()
        self.setLayoutDirection(Qt.RightToLeft)
        self.creditor_ids = []
        self.inventory_data = []
        self.groups_data = []
        self.materials_data = []
        self.creditors_data = []
        self.init_ui()
        self.load_data()

    def init_ui(self):
        """إنشاء واجهة المستخدم"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        title = QLabel("⚙️ الإعدادات")
        title.setStyleSheet(title_label_style(font_size=FontSizes.XL3, color=Colors.DARK))
        title.setAlignment(Qt.AlignRight)
        main_layout.addWidget(title)

        self.tabs = QTabWidget()
        self.tabs.setLayoutDirection(Qt.RightToLeft)
        self.tabs.setStyleSheet(tab_style())

        self.tab_opening = self.create_opening_balances_tab()
        self.tab_groups = self.create_groups_materials_tab()
        self.tab_exchange = self.create_exchange_rate_tab()
        self.tab_backup = self.create_backup_tab()

        self.tabs.addTab(self.tab_opening, "الأرصدة الافتتاحية")
        self.tabs.addTab(self.tab_groups, "إدارة المجموعات والمواد")
        self.tabs.addTab(self.tab_exchange, "سعر الصرف")
        self.tabs.addTab(self.tab_backup, "النسخ الاحتياطي")

        main_layout.addWidget(self.tabs)

        reset_btn = QPushButton("تصفير قاعدة البيانات")
        reset_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_TrashIcon))
        reset_btn.setFixedHeight(40)
        reset_btn.setCursor(Qt.PointingHandCursor)
        reset_btn.setStyleSheet(danger_button_style(padding="8px"))
        reset_btn.clicked.connect(self.reset_database)
        main_layout.addWidget(reset_btn)

    def create_opening_balances_tab(self):
        widget = QWidget()
        widget.setLayoutDirection(Qt.RightToLeft)
        main_layout = QVBoxLayout(widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        opening_layout = QGridLayout()
        opening_layout.setSpacing(10)
        opening_layout.setContentsMargins(0, 0, 0, 0)
        opening_layout.setColumnStretch(0, 1)
        opening_layout.setColumnStretch(1, 1)
        opening_layout.setRowStretch(0, 1)
        opening_layout.setRowStretch(1, 1)

        cash_group = QGroupBox("💰 رصيد النقدية الافتتاحي")
        cash_group.setStyleSheet(group_box_style("#3498db"))
        cash_layout = QHBoxLayout()
        cash_layout.setContentsMargins(10, 10, 10, 10)

        cash_label = QLabel("رصيد النقدية الحالي (ليرة سورية):")
        cash_label.setStyleSheet(f"font-size: {FontSizes.SM}; color: {Colors.DARK};")
        self.cash_input = QLineEdit()
        self.cash_input.setPlaceholderText("أدخل المبلغ...")
        self.cash_input.setStyleSheet(input_style(focus_color=Colors.FOCUS_BLUE, min_width="150px"))

        cash_layout.addWidget(cash_label)
        cash_layout.addWidget(self.cash_input)
        cash_layout.addStretch()
        cash_group.setLayout(cash_layout)
        opening_layout.addWidget(cash_group, 0, 0)

        vault_group = QGroupBox("🏦 رصيد الخزنة الافتتاحي")
        vault_group.setStyleSheet(group_box_style("#16a085"))
        vault_layout = QHBoxLayout()
        vault_layout.setContentsMargins(10, 10, 10, 10)

        vault_label = QLabel("رصيد الخزنة الحالي (ليرة سورية):")
        vault_label.setStyleSheet(f"font-size: {FontSizes.SM}; color: {Colors.DARK};")
        self.vault_input = QLineEdit()
        self.vault_input.setPlaceholderText("أدخل المبلغ...")
        self.vault_input.setStyleSheet(input_style(focus_color=Colors.FOCUS_TEAL, min_width="150px"))

        vault_layout.addWidget(vault_label)
        vault_layout.addWidget(self.vault_input)
        vault_layout.addStretch()
        vault_group.setLayout(vault_layout)
        opening_layout.addWidget(vault_group, 0, 1)

        inventory_group = QGroupBox("📦 الجرد الافتتاحي للمواد الفرعية")
        inventory_group.setStyleSheet(group_box_style("#27ae60"))
        inventory_layout = QVBoxLayout()
        inventory_layout.setContentsMargins(10, 10, 10, 10)

        self.inventory_table = QTableWidget()
        self.inventory_table.setColumnCount(6)
        self.inventory_table.setHorizontalHeaderLabels([
            "المادة", "الوحدة", "المجموعة",
            "الكمية الفعلية", "سعر الشراء", "القيمة الإجمالية"
        ])
        self.inventory_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.inventory_table.horizontalHeader().setLayoutDirection(Qt.RightToLeft)
        self.inventory_table.setStyleSheet(table_style_compact(Colors.SUCCESS))
        self.inventory_table.setAlternatingRowColors(True)
        self.inventory_table.setItemDelegateForColumn(3, NumericDelegate())
        self.inventory_table.setItemDelegateForColumn(4, NumericDelegate())
        self.inventory_table.setMinimumHeight(120)
        self.inventory_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.inventory_total_label = QLabel("📊 إجمالي قيمة المخزون الافتتاحي: 0 ل.س")
        self.inventory_total_label.setStyleSheet("""
            font-size: 15px;
            font-weight: bold;
            color: #27ae60;
            background-color: #eafaf1;
            border: 2px solid #27ae60;
            border-radius: 8px;
            padding: 10px 15px;
        """)
        self.inventory_total_label.setAlignment(Qt.AlignRight)
        inventory_layout.addWidget(self.inventory_total_label)
        inventory_group.setLayout(inventory_layout)
        opening_layout.addWidget(inventory_group, 1, 0)

        creditors_group = QGroupBox("👥 الأرصدة الافتتاحية للدائنون")
        creditors_group.setStyleSheet(group_box_style("#e74c3c"))
        creditors_layout = QVBoxLayout()
        creditors_layout.setContentsMargins(10, 10, 10, 10)

        self.creditors_table = QTableWidget()
        self.creditors_table.setColumnCount(4)
        self.creditors_table.setHorizontalHeaderLabels(["الاسم", "النوع", "العملة", "الرصيد الافتتاحي"])
        self.creditors_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.creditors_table.horizontalHeader().setLayoutDirection(Qt.RightToLeft)
        self.creditors_table.setStyleSheet(table_style_compact(Colors.DANGER))
        self.creditors_table.setAlternatingRowColors(True)
        self.creditors_table.setItemDelegateForColumn(3, NumericDelegate())
        self.creditors_table.setMinimumHeight(120)
        self.creditors_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        creditors_layout.addWidget(self.creditors_table)
        creditors_group.setLayout(creditors_layout)
        opening_layout.addWidget(creditors_group, 1, 1)

        main_layout.addLayout(opening_layout)

        save_btn = QPushButton("حفظ الأرصدة الافتتاحية")
        save_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_DialogSaveButton))
        save_btn.setFixedHeight(40)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet(primary_button_style(
            bg=Colors.PRIMARY, hover=Colors.PRIMARY_HOVER,
            font_size=FontSizes.XL2, padding="8px", border_radius=BorderRadius.LG
        ))
        save_btn.clicked.connect(self.save_opening_balances)
        main_layout.addWidget(save_btn)

        main_layout.addStretch()
        return widget

    def create_groups_materials_tab(self):
        widget = QWidget()
        widget.setLayoutDirection(Qt.RightToLeft)
        layout = QHBoxLayout(widget)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        groups_group = QGroupBox("📁 مجموعات المبيعات")
        groups_group.setStyleSheet(group_box_style("#9b59b6"))
        groups_layout = QVBoxLayout()
        groups_layout.setContentsMargins(10, 10, 10, 10)

        add_group_layout = QHBoxLayout()
        add_group_layout.setContentsMargins(0, 0, 0, 0)

        group_name_label = QLabel("اسم المجموعة:")
        group_name_label.setStyleSheet(f"font-size: {FontSizes.SM}; color: {Colors.DARK};")
        self.group_name_input = QLineEdit()
        self.group_name_input.setPlaceholderText("مثال: موالح، بن مطحون...")
        self.group_name_input.setStyleSheet(input_style(focus_color=Colors.FOCUS_PURPLE, min_width="250px"))

        add_group_btn = QPushButton("إضافة مجموعة")
        add_group_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_FileIcon))
        add_group_btn.setFixedHeight(34)
        add_group_btn.setCursor(Qt.PointingHandCursor)
        add_group_btn.setStyleSheet(purple_button_style())
        add_group_btn.clicked.connect(self.add_group)

        delete_group_btn = QPushButton("حذف المجموعة المحددة")
        delete_group_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_TrashIcon))
        delete_group_btn.setFixedHeight(34)
        delete_group_btn.setCursor(Qt.PointingHandCursor)
        delete_group_btn.setStyleSheet(danger_button_style())
        delete_group_btn.clicked.connect(self.delete_group)

        add_group_layout.addWidget(group_name_label)
        add_group_layout.addWidget(self.group_name_input)
        add_group_layout.addWidget(add_group_btn)
        add_group_layout.addWidget(delete_group_btn)
        add_group_layout.addStretch()
        groups_layout.addLayout(add_group_layout)

        self.groups_table = QTableWidget()
        self.groups_table.setColumnCount(3)
        self.groups_table.setHorizontalHeaderLabels(["المعرف", "الاسم", "الوصف"])
        self.groups_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.groups_table.horizontalHeader().setLayoutDirection(Qt.RightToLeft)
        self.groups_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.groups_table.setSelectionMode(QTableWidget.SingleSelection)
        self.groups_table.setStyleSheet(table_style_compact(Colors.PURPLE))
        self.groups_table.setAlternatingRowColors(True)
        self.groups_table.cellDoubleClicked.connect(self._on_group_double_clicked)
        self.groups_table.setMinimumHeight(120)
        self.groups_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        groups_layout.addWidget(self.groups_table)
        groups_group.setLayout(groups_layout)
        layout.addWidget(groups_group)

        materials_group = QGroupBox("📦 المواد الفرعية")
        materials_group.setStyleSheet(group_box_style("#f39c12"))
        materials_layout = QVBoxLayout()
        materials_layout.setContentsMargins(10, 10, 10, 10)

        add_mat_layout = QHBoxLayout()
        add_mat_layout.setContentsMargins(0, 0, 0, 0)

        add_mat_layout2 = QHBoxLayout()
        add_mat_layout2.setContentsMargins(0, 0, 0, 0)

        self.material_group_combo = QComboBox()
        self.material_group_combo.setStyleSheet(combo_style(focus_color=Colors.FOCUS_ORANGE, min_width="180px"))

        mat_name_label = QLabel("اسم المادة:")
        mat_name_label.setStyleSheet("font-size: 13px; color: #2c3e50;")
        self.material_name_input = QLineEdit()
        self.material_name_input.setPlaceholderText("اسم المادة...")
        self.material_name_input.setStyleSheet(input_style(focus_color=Colors.FOCUS_ORANGE, min_width="180px"))

        unit_label = QLabel("الوحدة:")
        unit_label.setStyleSheet("font-size: 13px; color: #2c3e50;")
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["كيلوغرام", "قطعة", "لتر"])
        self.unit_combo.setStyleSheet(combo_style(focus_color=Colors.FOCUS_ORANGE, min_width="120px"))

        min_label = QLabel("الحد الأدنى:")
        min_label.setStyleSheet("font-size: 13px; color: #2c3e50;")
        self.min_stock_input = QLineEdit()
        self.min_stock_input.setPlaceholderText("0 = بلا تنبيه")
        self.min_stock_input.setValidator(QDoubleValidator(0, 10000000, 2))
        self.min_stock_input.setStyleSheet(input_style(focus_color=Colors.FOCUS_ORANGE, min_width="120px"))

        add_mat_btn = QPushButton("إضافة مادة")
        add_mat_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_FileIcon))
        add_mat_btn.setFixedHeight(34)
        add_mat_btn.setCursor(Qt.PointingHandCursor)
        add_mat_btn.setStyleSheet(warning_button_style())
        add_mat_btn.clicked.connect(self.add_material)

        add_mat_layout.addWidget(self.material_group_combo)
        add_mat_layout.addWidget(mat_name_label)
        add_mat_layout.addWidget(self.material_name_input)
        add_mat_layout.addStretch()

        add_mat_layout2.addWidget(unit_label)
        add_mat_layout2.addWidget(self.unit_combo)
        add_mat_layout2.addWidget(min_label)
        add_mat_layout2.addWidget(self.min_stock_input)
        add_mat_layout2.addWidget(add_mat_btn)
        add_mat_layout2.addStretch()

        materials_layout.addLayout(add_mat_layout)
        materials_layout.addLayout(add_mat_layout2)

        self.materials_table = QTableWidget()
        self.materials_table.setColumnCount(5)
        self.materials_table.setHorizontalHeaderLabels(["المعرف", "الاسم", "الوحدة", "المجموعة", "آخر سعر شراء"])
        self.materials_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.materials_table.horizontalHeader().setLayoutDirection(Qt.RightToLeft)
        self.materials_table.setStyleSheet(table_style_compact(Colors.ORANGE))
        self.materials_table.setAlternatingRowColors(True)
        self.materials_table.setItemDelegateForColumn(4, NumericDelegate())
        self.materials_table.setMinimumHeight(120)
        self.materials_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.materials_table.cellChanged.connect(self.on_material_price_changed)
        materials_layout.addWidget(self.materials_table)
        materials_group.setLayout(materials_layout)
        layout.addWidget(materials_group)

        return widget

    def create_exchange_rate_tab(self):
        widget = QWidget()
        widget.setLayoutDirection(Qt.RightToLeft)
        layout = QHBoxLayout(widget)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        current_group = QGroupBox("💱 سعر الصرف الحالي")
        current_group.setStyleSheet(group_box_style("#1abc9c"))
        current_layout = QHBoxLayout()
        current_layout.setContentsMargins(10, 10, 10, 10)

        self.current_rate_label = QLabel("السعر الحالي: جاري التحميل...")
        self.current_rate_label.setStyleSheet(f"""
            font-size: {FontSizes.XL};
            font-weight: bold;
            color: {Colors.TEAL};
            padding: 6px;
            background-color: #e8f8f5;
            border-radius: {BorderRadius.MD};
        """)

        new_rate_label = QLabel("سعر صرف جديد (ليرة سورية / دولار):")
        new_rate_label.setStyleSheet(f"font-size: {FontSizes.SM}; color: {Colors.DARK};")
        self.new_rate_input = QLineEdit()
        self.new_rate_input.setPlaceholderText("أدخل السعر الجديد...")
        self.new_rate_input.setStyleSheet(input_style(focus_color=Colors.FOCUS_TEAL, min_width="150px"))

        update_rate_btn = QPushButton("تحديث سعر الصرف")
        update_rate_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_BrowserReload))
        update_rate_btn.setFixedHeight(34)
        update_rate_btn.setCursor(Qt.PointingHandCursor)
        update_rate_btn.setStyleSheet(teal_button_style())
        update_rate_btn.clicked.connect(self.update_exchange_rate)

        current_layout.addWidget(self.current_rate_label)
        current_layout.addWidget(new_rate_label)
        current_layout.addWidget(self.new_rate_input)
        current_layout.addWidget(update_rate_btn)
        current_layout.addStretch()
        current_group.setLayout(current_layout)
        layout.addWidget(current_group)

        history_group = QGroupBox("📜 آخر 10 تغييرات لسعر الصرف")
        history_group.setStyleSheet(group_box_style("#95a5a6"))
        history_layout = QVBoxLayout()
        history_layout.setContentsMargins(10, 10, 10, 10)

        self.rate_history_table = QTableWidget()
        self.rate_history_table.setColumnCount(3)
        self.rate_history_table.setHorizontalHeaderLabels(["التاريخ", "السعر (ليرة/دولار)", "ملاحظات"])
        self.rate_history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.rate_history_table.horizontalHeader().setLayoutDirection(Qt.RightToLeft)
        self.rate_history_table.setStyleSheet(table_style_compact(Colors.GRAY))
        self.rate_history_table.setAlternatingRowColors(True)
        self.rate_history_table.setMinimumHeight(120)
        self.rate_history_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        history_layout.addWidget(self.rate_history_table)
        history_group.setLayout(history_layout)
        layout.addWidget(history_group)

        return widget

    def create_backup_tab(self):
        widget = QWidget()
        widget.setLayoutDirection(Qt.RightToLeft)
        layout = QVBoxLayout(widget)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        info_label = QLabel(
            "يمكنك إنشاء نسخة احتياطية يدوية من قاعدة البيانات في أي وقت.\n"
            "سيتم حفظ الملف في المجلد الذي تختاره باسم يحتوي على الطابع الزمني."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet(f"font-size: {FontSizes.MD}; color: {Colors.DARK};")
        layout.addWidget(info_label)

        backup_btn = QPushButton("📦 نسخ احتياطي الآن")
        backup_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_DialogSaveButton))
        backup_btn.setFixedHeight(48)
        backup_btn.setCursor(Qt.PointingHandCursor)
        backup_btn.setStyleSheet(primary_button_style(
            bg=Colors.PRIMARY, hover=Colors.PRIMARY_HOVER,
            font_size=FontSizes.XL2, padding="10px", border_radius=BorderRadius.LG
        ))
        backup_btn.clicked.connect(self.manual_backup)
        layout.addWidget(backup_btn)

        layout.addStretch()
        return widget

    def load_data(self):
        self.load_cash_data()
        self.load_inventory_data()
        self.load_creditors_data()
        self.load_groups_data()
        self.load_materials_data()
        self.load_exchange_rate_data()

    def load_cash_data(self):
        conn = None
        try:
            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT القيمة FROM الإعدادات WHERE المفتاح = 'رصيد_النقدية_الافتتاحي'
            """)
            result = cursor.fetchone()
            if result and result[0]:
                self.cash_input.setText(str(result[0]))
            else:
                self.cash_input.setText("0")

            cursor.execute("""
                SELECT القيمة FROM الإعدادات WHERE المفتاح = 'رصيد_الخزنة_الافتتاحي'
            """)
            result = cursor.fetchone()
            if result and result[0]:
                self.vault_input.setText(str(result[0]))
            else:
                self.vault_input.setText("0")
        except Exception as e:
            logger.error(str(e))
        finally:
            if conn:
                conn.close()

    def load_inventory_data(self):
        conn = None
        try:
            try:
                self.inventory_table.itemChanged.disconnect(self._recalculate_inventory_totals)
            except Exception:
                pass

            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT م.معرف, م.الاسم, م.الوحدة, ج.الاسم,
                       COALESCE(خ.الكمية_المتوفرة, 0),
                       COALESCE(م.سعر_الشراء_الأخير, 0)
                FROM المواد_الفرعية م
                JOIN المجموعات ج ON م.معرف_المجموعة = ج.معرف
                LEFT JOIN المخزون خ ON م.معرف = خ.معرف_المادة_الفرعية
                ORDER BY ج.الاسم, م.الاسم
            """)
            data = cursor.fetchall()

            self.inventory_table.setRowCount(len(data))
            self.inventory_data = data
            total_value = 0.0

            for row, (mid, name, unit, group, qty, price) in enumerate(data):
                item_name = QTableWidgetItem(name)
                item_name.setFlags(item_name.flags() & ~Qt.ItemIsEditable)
                self.inventory_table.setItem(row, 0, item_name)

                item_unit = QTableWidgetItem(unit)
                item_unit.setFlags(item_unit.flags() & ~Qt.ItemIsEditable)
                self.inventory_table.setItem(row, 1, item_unit)

                item_group = QTableWidgetItem(group)
                item_group.setFlags(item_group.flags() & ~Qt.ItemIsEditable)
                self.inventory_table.setItem(row, 2, item_group)

                item_qty = QTableWidgetItem(str(qty))
                self.inventory_table.setItem(row, 3, item_qty)

                item_price = QTableWidgetItem(str(price))
                self.inventory_table.setItem(row, 4, item_price)

                line_value = qty * price
                total_value += line_value
                item_value = QTableWidgetItem(f"{line_value:,.0f}")
                item_value.setFlags(item_value.flags() & ~Qt.ItemIsEditable)
                item_value.setForeground(QColor("#27ae60"))
                self.inventory_table.setItem(row, 5, item_value)

            self.inventory_total_label.setText(
                f"📊 إجمالي قيمة المخزون الافتتاحي: {total_value:,.0f} ل.س"
            )

            self.inventory_table.itemChanged.connect(self._recalculate_inventory_totals)

        except Exception as e:
            logger.error(str(e))
            QMessageBox.critical(self, "خطأ", f"فشل تحميل بيانات المواد:\n{str(e)}")
        finally:
            if conn:
                conn.close()

    def _recalculate_inventory_totals(self, item):
        row = item.row()
        col = item.column()
        if col not in (3, 4):
            return

        try:
            qty_item = self.inventory_table.item(row, 3)
            price_item = self.inventory_table.item(row, 4)
            qty = float(qty_item.text()) if qty_item and qty_item.text() else 0
            price = float(price_item.text()) if price_item and price_item.text() else 0
            line_value = qty * price

            self.inventory_table.blockSignals(True)
            value_item = QTableWidgetItem(f"{line_value:,.0f}")
            value_item.setFlags(value_item.flags() & ~Qt.ItemIsEditable)
            value_item.setForeground(QColor("#27ae60"))
            self.inventory_table.setItem(row, 5, value_item)
            self.inventory_table.blockSignals(False)

            total = 0.0
            for r in range(self.inventory_table.rowCount()):
                q = float(self.inventory_table.item(r, 3).text() or 0) if self.inventory_table.item(r, 3) else 0
                p = float(self.inventory_table.item(r, 4).text() or 0) if self.inventory_table.item(r, 4) else 0
                total += q * p

            self.inventory_total_label.setText(
                f"📊 إجمالي قيمة المخزون الافتتاحي: {total:,.0f} ل.س"
            )
        except (ValueError, AttributeError):
            pass

    def load_creditors_data(self):
        conn = None
        try:
            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT معرف, اسم_الطرف, نوع_الطرف, العملة, الرصيد
                FROM الديون
                ORDER BY اسم_الطرف
            """)
            data = cursor.fetchall()

            self.creditors_table.setRowCount(len(data))
            for row, (cid, name, ctype, currency, balance) in enumerate(data):
                self.creditor_ids.append(cid)

                item_name = QTableWidgetItem(name)
                item_name.setFlags(item_name.flags() & ~Qt.ItemIsEditable)
                self.creditors_table.setItem(row, 0, item_name)

                item_type = QTableWidgetItem(ctype)
                item_type.setFlags(item_type.flags() & ~Qt.ItemIsEditable)
                self.creditors_table.setItem(row, 1, item_type)

                item_currency = QTableWidgetItem(currency)
                item_currency.setFlags(item_currency.flags() & ~Qt.ItemIsEditable)
                self.creditors_table.setItem(row, 2, item_currency)

                item_balance = QTableWidgetItem(str(balance))
                self.creditors_table.setItem(row, 3, item_balance)

            self.creditors_data = data
        except Exception as e:
            logger.error(str(e))
            QMessageBox.critical(self, "خطأ", f"فشل تحميل بيانات الدائنون:\n{str(e)}")
        finally:
            if conn:
                conn.close()

    def load_groups_data(self):
        conn = None
        try:
            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT معرف, الاسم, الوصف FROM المجموعات ORDER BY الترتيب, الاسم")
            data = cursor.fetchall()

            self.groups_table.setRowCount(len(data))
            for row, (gid, name, desc) in enumerate(data):
                item_id = QTableWidgetItem(str(gid))
                item_id.setFlags(item_id.flags() & ~Qt.ItemIsEditable)
                self.groups_table.setItem(row, 0, item_id)

                item_name = QTableWidgetItem(name)
                item_name.setFlags(item_name.flags() & ~Qt.ItemIsEditable)
                self.groups_table.setItem(row, 1, item_name)

                item_desc = QTableWidgetItem(desc or "")
                item_desc.setFlags(item_desc.flags() & ~Qt.ItemIsEditable)
                self.groups_table.setItem(row, 2, item_desc)

            self.groups_data = data
        except Exception as e:
            logger.error(str(e))
            QMessageBox.critical(self, "خطأ", f"فشل تحميل بيانات المجموعات:\n{str(e)}")
        finally:
            if conn:
                conn.close()

    def load_materials_data(self):
        conn = None
        try:
            try:
                self.materials_table.cellChanged.disconnect(self.on_material_price_changed)
            except Exception:
                pass

            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT م.معرف, م.الاسم, م.الوحدة, ج.الاسم, م.سعر_الشراء_الأخير
                FROM المواد_الفرعية م
                JOIN المجموعات ج ON م.معرف_المجموعة = ج.معرف
                ORDER BY م.معرف
            """)
            data = cursor.fetchall()

            self.materials_table.setRowCount(len(data))
            for row, (mid, name, unit, group, price) in enumerate(data):
                item_id = QTableWidgetItem(str(mid))
                item_id.setFlags(item_id.flags() & ~Qt.ItemIsEditable)
                self.materials_table.setItem(row, 0, item_id)

                item_name = QTableWidgetItem(name)
                item_name.setFlags(item_name.flags() & ~Qt.ItemIsEditable)
                self.materials_table.setItem(row, 1, item_name)

                item_unit = QTableWidgetItem(unit)
                item_unit.setFlags(item_unit.flags() & ~Qt.ItemIsEditable)
                self.materials_table.setItem(row, 2, item_unit)

                item_group = QTableWidgetItem(group)
                item_group.setFlags(item_group.flags() & ~Qt.ItemIsEditable)
                self.materials_table.setItem(row, 3, item_group)

                item_price = QTableWidgetItem(str(price))
                self.materials_table.setItem(row, 4, item_price)

            self.materials_data = data

            self.material_group_combo.clear()
            for gid, name, desc in self.groups_data:
                self.material_group_combo.addItem(name, gid)

            # إعادة توصيل الإشارة بعد انتهاء تعبئة الجدول
            try:
                self.materials_table.cellChanged.connect(self.on_material_price_changed)
            except Exception:
                pass

        except Exception as e:
            logger.error(str(e))
            QMessageBox.critical(self, "خطأ", f"فشل تحميل بيانات المواد:\n{str(e)}")
        finally:
            if conn:
                conn.close()

    def load_exchange_rate_data(self):
        conn = get_conn()
        try:
            cursor = conn.cursor()

            cursor.execute("SELECT القيمة FROM الإعدادات WHERE المفتاح = 'سعر_صرف_الدولار'")
            result = cursor.fetchone()
            current_rate = result[0] if result else "غير محدد"
            self.current_rate_label.setText(f"السعر الحالي: {current_rate} ليرة سورية / دولار")

            cursor.execute("""
                SELECT التاريخ, سعر_الدولار, ملاحظات
                FROM أسعار_الصرف
                ORDER BY معرف DESC
                LIMIT 10
            """)
            data = cursor.fetchall()

            self.rate_history_table.setRowCount(len(data))
            for row, (date, rate, notes) in enumerate(data):
                item_date = QTableWidgetItem(date)
                item_date.setFlags(item_date.flags() & ~Qt.ItemIsEditable)
                self.rate_history_table.setItem(row, 0, item_date)

                item_rate = QTableWidgetItem(str(rate))
                item_rate.setFlags(item_rate.flags() & ~Qt.ItemIsEditable)
                self.rate_history_table.setItem(row, 1, item_rate)

                item_notes = QTableWidgetItem(notes or "")
                item_notes.setFlags(item_notes.flags() & ~Qt.ItemIsEditable)
                self.rate_history_table.setItem(row, 2, item_notes)
        except Exception as e:
            logger.error(str(e))
            QMessageBox.critical(self, "خطأ", f"فشل تحميل بيانات سعر الصرف:\n{str(e)}")
        finally:
            conn.close()

    def save_opening_balances(self):
        try:
            cash_value = self.cash_input.text().strip()
            if not cash_value:
                QMessageBox.warning(self, "تنبيه", "الرجاء إدخال رصيد النقدية")
                return

            cash_amount = float(cash_value)
            if cash_amount < 0:
                QMessageBox.warning(self, "تنبيه", "لا يمكن أن يكون الرصيد سالباً")
                return

            vault_value = self.vault_input.text().strip()
            if not vault_value:
                QMessageBox.warning(self, "تنبيه", "الرجاء إدخال رصيد الخزنة")
                return

            vault_amount = float(vault_value)
            if vault_amount < 0:
                QMessageBox.warning(self, "تنبيه", "لا يمكن أن يكون رصيد الخزنة سالباً")
                return

            inventory_quantities = {}
            inventory_prices = {}
            for row in range(self.inventory_table.rowCount()):
                material_id = self.inventory_data[row][0]
                qty_item = self.inventory_table.item(row, 3)
                qty_text = qty_item.text().strip() if qty_item else "0"
                try:
                    qty = float(qty_text) if qty_text else 0.0
                except ValueError:
                    QMessageBox.warning(self, "تنبيه", f"كمية غير صالحة للمادة في الصف {row + 1}")
                    return
                inventory_quantities[material_id] = qty

                price_item = self.inventory_table.item(row, 4)
                price_text = price_item.text().strip() if price_item else "0"
                try:
                    price = float(price_text) if price_text else 0.0
                except ValueError:
                    QMessageBox.warning(self, "تنبيه", f"سعر شراء غير صالح للمادة في الصف {row + 1}")
                    return
                inventory_prices[material_id] = price

            creditor_balances = {}
            for row in range(self.creditors_table.rowCount()):
                creditor_id = self.creditor_ids[row]
                balance_item = self.creditors_table.item(row, 3)
                balance_text = balance_item.text().strip() if balance_item else "0"
                try:
                    balance = float(balance_text) if balance_text else 0.0
                except ValueError:
                    QMessageBox.warning(self, "تنبيه", f"رصيد غير صالح للدائن في الصف {row + 1}")
                    return
                creditor_balances[creditor_id] = balance

            conn = None
            try:
                conn = get_conn()
                cursor = conn.cursor()
                cursor.execute("BEGIN TRANSACTION")

                cursor.execute("""
                    UPDATE الإعدادات
                    SET القيمة = ?, تاريخ_التحديث = CURRENT_TIMESTAMP
                    WHERE المفتاح = 'رصيد_النقدية_الافتتاحي'
                """, (cash_amount,))

                if cursor.rowcount == 0:
                    cursor.execute("""
                        INSERT INTO الإعدادات (المفتاح, القيمة, الوصف)
                        VALUES ('رصيد_النقدية_الافتتاحي', ?, 'رصيد النقدية الافتتاحي')
                    """, (cash_amount,))

                cursor.execute("""
                    UPDATE الإعدادات
                    SET القيمة = ?, تاريخ_التحديث = CURRENT_TIMESTAMP
                    WHERE المفتاح = 'رصيد_الخزنة_الافتتاحي'
                """, (vault_amount,))

                if cursor.rowcount == 0:
                    cursor.execute("""
                        INSERT INTO الإعدادات (المفتاح, القيمة, الوصف)
                        VALUES ('رصيد_الخزنة_الافتتاحي', ?, 'رصيد الخزنة الافتتاحي')
                    """, (vault_amount,))

                cursor.execute("""
                    SELECT معرف, الرصيد_بعد_الحركة FROM الخزنة
                    WHERE البيان = 'رصيد افتتاحي'
                    ORDER BY معرف ASC LIMIT 1
                """)
                opening_row = cursor.fetchone()

                if opening_row is None:
                    cursor.execute("""
                        INSERT INTO الخزنة (التاريخ, البيان, إيداع, الرصيد_بعد_الحركة, ملاحظات)
                        VALUES (?, ?, ?, ?, ?)
                    """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "رصيد افتتاحي",
                          vault_amount, vault_amount, "رصيد افتتاحي للخزنة"))
                else:
                    opening_id, old_balance = opening_row
                    delta = vault_amount - (old_balance or 0)

                    cursor.execute("""
                        UPDATE الخزنة SET إيداع = ?, الرصيد_بعد_الحركة = ?
                        WHERE معرف = ?
                    """, (vault_amount, vault_amount, opening_id))

                    if delta != 0:
                        cursor.execute("""
                            UPDATE الخزنة SET الرصيد_بعد_الحركة = الرصيد_بعد_الحركة + ?
                            WHERE معرف > ?
                        """, (delta, opening_id))

                for material_id, qty in inventory_quantities.items():
                    cursor.execute("""
                        INSERT OR REPLACE INTO المخزون (معرف_المادة_الفرعية, الكمية_المتوفرة, آخر_تحديث)
                        VALUES (?, ?, CURRENT_TIMESTAMP)
                    """, (material_id, qty))

                    price = inventory_prices.get(material_id, 0.0)
                    cursor.execute("""
                        UPDATE المواد_الفرعية
                        SET سعر_الشراء_الأخير = ?
                        WHERE معرف = ?
                    """, (price, material_id))

                    cursor.execute("""
                        INSERT INTO تحركات_المخزون
                        (معرف_المادة_الفرعية, نوع_الحركة, الكمية, الرصيد_بعد, ملاحظات)
                        VALUES (?, 'تعديل_يدوي', ?, ?, 'رصيد افتتاحي')
                    """, (material_id, qty, qty))

                for creditor_id, balance in creditor_balances.items():
                    cursor.execute("""
                        UPDATE الديون
                        SET الرصيد = ?, المبلغ_الإجمالي = ?, تاريخ_التحديث = CURRENT_TIMESTAMP
                        WHERE معرف = ?
                    """, (balance, balance, creditor_id))

                    cursor.execute("""
                        DELETE FROM تحركات_الديون
                        WHERE معرف_الدين = ? AND نوع_الحركة = 'إضافة' AND ملاحظات = 'رصيد افتتاحي'
                    """, (creditor_id,))

                    cursor.execute("""
                        INSERT INTO تحركات_الديون (معرف_الدين, المبلغ, نوع_الحركة, ملاحظات)
                        VALUES (?, ?, 'إضافة', 'رصيد افتتاحي')
                    """, (creditor_id, balance))

                conn.commit()
                QMessageBox.information(self, "نجاح", "تم حفظ الأرصدة الافتتاحية بنجاح!")

            except Exception as e:
                logger.error(str(e))
                if conn:
                    conn.rollback()
                QMessageBox.critical(self, "خطأ", f"فشل حفظ الأرصدة:\n{str(e)}")
            finally:
                if conn:
                    conn.close()
        except Exception as e:
            logger.error(str(e))
            QMessageBox.critical(self, "خطأ", str(e))

    def add_group(self):
        name = self.group_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "تنبيه", "الرجاء إدخال اسم المجموعة")
            return

        conn = None
        try:
            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT COALESCE(MAX(الترتيب), 0) FROM المجموعات")
            next_order = cursor.fetchone()[0] + 1
            cursor.execute(
                "INSERT INTO المجموعات (الاسم, الترتيب) VALUES (?, ?)",
                (name, next_order)
            )
            conn.commit()

            self.group_name_input.clear()
            self.load_groups_data()
            self.load_materials_data()
            QMessageBox.information(self, "نجاح", "تمت إضافة المجموعة بنجاح!")

        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "تنبيه", "اسم المجموعة موجود مسبقاً")
        except Exception as e:
            logger.error(str(e))
            QMessageBox.critical(self, "خطأ", f"فشل إضافة المجموعة:\n{str(e)}")
        finally:
            if conn:
                conn.close()

    def delete_group(self):
        current_row = self.groups_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "تنبيه", "الرجاء تحديد مجموعة للحذف")
            return

        group_id = self.groups_data[current_row][0]
        group_name = self.groups_data[current_row][1]

        confirm = QMessageBox.question(
            self,
            "تأكيد الحذف",
            f"هل أنت متأكد من حذف المجموعة '{group_name}' وجميع المواد الفرعية التابعة لها؟",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            conn = get_conn()
            try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM المجموعات WHERE معرف = ?", (group_id,))
                conn.commit()

                self.load_groups_data()
                self.load_materials_data()
                self.load_inventory_data()
                QMessageBox.information(self, "نجاح", "تم حذف المجموعة بنجاح!")

            except Exception as e:
                logger.error(str(e))
                QMessageBox.critical(self, "خطأ", f"فشل حذف المجموعة:\n{str(e)}")
            finally:
                conn.close()

    def _on_group_double_clicked(self, row, column):
        if row < 0 or row >= len(self.groups_data):
            return

        group_id = self.groups_data[row][0]
        group_name = self.groups_data[row][1]

        conn = None
        try:
            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT م.الاسم, م.الوحدة, COALESCE(خ.الكمية_المتوفرة, 0)
                FROM المواد_الفرعية م
                LEFT JOIN المخزون خ ON م.معرف = خ.معرف_المادة_الفرعية
                WHERE م.معرف_المجموعة = ?
                ORDER BY م.الاسم
            """, (group_id,))
            materials = cursor.fetchall()

            detail_data = {
                "اسم_المجموعة": group_name,
                "عدد_المواد": len(materials),
            }

            related_rows = [(m[0], m[1], m[2]) for m in materials]
            related_headers = ["اسم المادة", "الوحدة", "الكمية المتوفرة"]

            dialog = EntityDetailDialog(
                title=f"تفاصيل المجموعة: {group_name}",
                detail_data=detail_data,
                related_rows=related_rows,
                related_headers=related_headers,
                parent=self,
            )
            dialog.exec_()

        except Exception as e:
            logger.error(str(e))
            QMessageBox.critical(self, "خطأ", f"فشل تحميل تفاصيل المجموعة:\n{str(e)}")
        finally:
            if conn:
                conn.close()

    def add_material(self):
        group_id = self.material_group_combo.currentData()
        name = self.material_name_input.text().strip()
        unit = self.unit_combo.currentText()

        if not name or group_id is None:
            QMessageBox.warning(self, "تنبيه", "الرجاء إدخال اسم المادة واختيار المجموعة")
            return

        min_text = self.min_stock_input.text().strip() if self.min_stock_input.text() else "0"
        try:
            min_qty = float(min_text) if min_text else 0.0
        except ValueError:
            min_qty = 0.0

        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO المواد_الفرعية (الاسم, الوحدة, معرف_المجموعة, الحد_الأدنى)
                VALUES (?, ?, ?, ?)
            """, (name, unit, group_id, min_qty))
            conn.commit()

            self.material_name_input.clear()
            self.min_stock_input.clear()
            self.load_materials_data()
            self.load_inventory_data()
            QMessageBox.information(self, "نجاح", "تمت إضافة المادة بنجاح!")

        except Exception as e:
            logger.error(str(e))
            QMessageBox.critical(self, "خطأ", f"فشل إضافة المادة:\n{str(e)}")
        finally:
            conn.close()

    def on_material_price_changed(self, row, column):
        if column != 4:
            return

        # تحقق إضافي: تجاهل الحدث إذا كان الصف خارج نطاق البيانات أو لا يوجد عمود سعر
        if not hasattr(self, 'materials_data') or row < 0 or row >= len(self.materials_data):
            return

        conn = None
        try:
            material_id = self.materials_data[row][0]
            new_price_text = self.materials_table.item(row, column).text().strip()
            new_price = float(new_price_text) if new_price_text else 0.0

            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE المواد_الفرعية
                SET سعر_الشراء_الأخير = ?
                WHERE معرف = ?
            """, (new_price, material_id))
            conn.commit()
        except ValueError:
            QMessageBox.warning(self, "تنبيه", "يرجى إدخال رقم صحيح لسعر الشراء")
        except Exception as e:
            logger.error(str(e))
            QMessageBox.critical(self, "خطأ", f"فشل تحديث السعر:\n{str(e)}")
        finally:
            if conn:
                conn.close()

    def update_exchange_rate(self):
        new_rate_text = self.new_rate_input.text().strip()
        if not new_rate_text:
            QMessageBox.warning(self, "تنبيه", "الرجاء إدخال سعر الصرف الجديد")
            return

        try:
            new_rate = float(new_rate_text)
            if new_rate <= 0:
                QMessageBox.warning(self, "تنبيه", "سعر الصرف يجب أن يكون أكبر من صفر")
                return

            conn = None
            try:
                conn = get_conn()
                cursor = conn.cursor()
                cursor.execute("BEGIN TRANSACTION")

                cursor.execute("""
                    UPDATE الإعدادات
                    SET القيمة = ?, تاريخ_التحديث = CURRENT_TIMESTAMP
                    WHERE المفتاح = 'سعر_صرف_الدولار'
                """, (new_rate,))

                if cursor.rowcount == 0:
                    cursor.execute("""
                        INSERT INTO الإعدادات (المفتاح, القيمة, الوصف)
                        VALUES ('سعر_صرف_الدولار', ?, 'سعر صرف الدولار الأمريكي')
                    """, (new_rate,))

                cursor.execute("""
                    INSERT INTO أسعار_الصرف (سعر_الدولار, ملاحظات)
                    VALUES (?, ?)
                """, (new_rate, "تحديث يدوي من الإعدادات"))

                conn.commit()
                self.new_rate_input.clear()
                self.load_exchange_rate_data()
                QMessageBox.information(self, "نجاح", "تم تحديث سعر الصرف بنجاح!")

            except Exception as e:
                logger.error(str(e))
                if conn:
                    conn.rollback()
                QMessageBox.critical(self, "خطأ", f"فشل تحديث سعر الصرف:\n{str(e)}")
            finally:
                if conn:
                    conn.close()

        except ValueError:
            QMessageBox.warning(self, "تنبيه", "يرجى إدخال رقم صحيح لسعر الصرف")

    def manual_backup(self):
        dest_dir = QFileDialog.getExistingDirectory(self, "اختر مجلد الوجهة للنسخ الاحتياطي")
        if not dest_dir:
            return

        try:
            if not os.path.exists(DATABASE_PATH):
                QMessageBox.warning(self, "خطأ", f"قاعدة البيانات غير موجودة في المسار:\n{DATABASE_PATH}")
                return

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"venus_backup_{timestamp}.db"
            dest_path = os.path.join(dest_dir, backup_name)

            shutil.copy2(DATABASE_PATH, dest_path)

            QMessageBox.information(
                self, "تم",
                f"تم إنشاء النسخ الاحتياطية بنجاح:\n{dest_path}"
            )
        except PermissionError:
            QMessageBox.critical(self, "خطأ", "لا يمكن الوصول إلى الملف أو المجلد. تحقق من الصلاحيات.")
        except OSError as e:
            QMessageBox.critical(self, "خطأ", f"فشل النسخ الاحتياطي:\n{str(e)}")
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"حدث خطأ غير متوقع:\n{str(e)}")

    def reset_database(self):
        reply = QMessageBox.question(
            self,
            "تأكيد التصفير",
            "هل أنت متأكد من تصفير قاعدة البيانات؟\nسيتم حذف جميع البيانات (المبيعات، المشتريات، المواد، الديون، المصروفات) ولا يمكن استرجاعها.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.No:
            return

        text, ok = QInputDialog.getText(
            self,
            "تأكيد التصفير",
            "لإتمام العملية، اكتب كلمة \"تصفير\" ثم اضغط موافق:",
            QLineEdit.Normal,
            ""
        )
        if not ok or text != "تصفير":
            return

        db_path = "venus.db"
        conn = None
        try:
            if os.path.exists(db_path):
                try:
                    os.remove(db_path)
                except PermissionError:
                    QMessageBox.critical(self, "خطأ", "لا يمكن حذف قاعدة البيانات لأنها مفتوحة حالياً\nيرجى إغلاق التطبيق وإعادة المحاولة")
                    return

            from migrations.create_database import create_database
            create_database()
            QMessageBox.information(
                self,
                "نجاح",
                "تم تصفير قاعدة البيانات بنجاح.\nسيتم إغلاق التطبيق الآن ليُعاد فتحه يدويًا."
            )
            QApplication.quit()
        except Exception as e:
            logger.error(str(e))
            QMessageBox.critical(self, "خطأ", f"فشل تصفير قاعدة البيانات:\n{str(e)}")
