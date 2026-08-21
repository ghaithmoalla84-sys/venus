# -*- coding: utf-8 -*-
"""
شاشة المواد والمخزون - Venus Coffee
تحتوي على: فواتير الشراء، عرض المخزون، الجرد الدوري
"""

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

from venus.core.database import get_conn
from venus.core.repositories import MaterialsRepository, CreditorsRepository
from venus.core.events import app_events
from venus.ui.screens.inventory.delegates import NumericDelegate
from venus.ui.screens.inventory.purchase import PurchaseBillMixin, BillItemsTable
from venus.ui.screens.inventory.stock import StockMixin
from venus.ui.screens.inventory.audit import AuditDialog
from venus.ui.widgets.searchable_table import SearchableTable
from venus.ui.widgets.combo_quick_add import ComboWithQuickAdd
from venus.ui.widgets.loading_overlay import LoadingOverlay
from venus.ui.styles import (
    Colors, FontSizes, Spacing, BorderRadius,
    title_label_style, group_box_style, table_style,
    primary_button_style, success_button_style, warning_button_style,
    input_style, combo_style, date_edit_style, _px
)
from venus.utils.logger import setup_logger
logger = setup_logger()

_SETTINGS_ORG = "VenusCoffee"
_SETTINGS_APP = "InventoryScreen"
_COL_WIDTHS_KEY = "billItemsTable/columnWidths"


class InventoryScreen(QWidget, PurchaseBillMixin, StockMixin):
    """شاشة المواد والمخزون"""

    def __init__(self):
        super().__init__()
        self.setLayoutDirection(Qt.RightToLeft)
        self.init_ui()
        self.load_data()
        app_events.data_changed.connect(self._on_app_data_changed)

    def init_ui(self):
        """إنشاء واجهة المستخدم"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        title = QLabel("📦 المواد والمخزون")
        title.setStyleSheet(title_label_style(font_size=FontSizes.XL3, color=Colors.DARK))
        title.setAlignment(Qt.AlignRight)
        main_layout.addWidget(title)

        # قسم فاتورة الشراء
        purchase_group = QGroupBox("🧾 فاتورة شراء جديدة")
        purchase_group.setStyleSheet(group_box_style(Colors.SUCCESS))
        purchase_layout = QVBoxLayout()
        purchase_layout.setSpacing(Spacing.MD)
        purchase_layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)

        # أدوات الفاتورة العلوية
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        supplier_label = QLabel("المورد:")
        supplier_label.setStyleSheet(f"font-size: {FontSizes.LG}; color: {Colors.DARK};")

        self.supplier_combo = ComboWithQuickAdd(
            load_func=self._load_suppliers_for_combo,
            add_dialog_func=self._add_supplier_dialog,
            button_text="➕"
        )

        date_label = QLabel("التاريخ:")
        date_label.setStyleSheet("font-size: 14px; color: #2c3e50;")
        self.date_input = QDateEdit()
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        self.date_input.setStyleSheet(date_edit_style(focus_color=Colors.FOCUS_GREEN))

        self.payment_combo = QComboBox()
        self.payment_combo.addItems(["نقدي من الخزنة", "نقدي من الدرج", "دين (آجل)", "جزئي (كاش + دين)"])
        self.payment_combo.setStyleSheet(combo_style(focus_color=Colors.FOCUS_GREEN, min_width="140px"))
        self.payment_combo.currentIndexChanged.connect(self.on_payment_changed)

        self.cash_amount_edit = QLineEdit()
        self.cash_amount_edit.setValidator(QDoubleValidator(0, 10000000, 2))
        self.cash_amount_edit.setPlaceholderText("المبلغ النقدي")
        self.cash_amount_edit.setStyleSheet(input_style(focus_color=Colors.FOCUS_GREEN))
        self.cash_amount_edit.setVisible(False)

        self.partial_payment_source_combo = QComboBox()
        self.partial_payment_source_combo.addItems(["من الدرج", "من الخزنة"])
        self.partial_payment_source_combo.setStyleSheet(combo_style(focus_color=Colors.FOCUS_GREEN, min_width="110px"))
        self.partial_payment_source_combo.setVisible(False)

        header_layout.addWidget(supplier_label)
        header_layout.addWidget(self.supplier_combo)
        header_layout.addWidget(date_label)
        header_layout.addWidget(self.date_input)
        header_layout.addWidget(self.payment_combo)
        header_layout.addWidget(self.cash_amount_edit)
        header_layout.addWidget(self.partial_payment_source_combo)
        header_layout.addStretch()
        purchase_layout.addLayout(header_layout)

        # جدول بنود الفاتورة
        self.items_table = BillItemsTable()
        self.items_table.setColumnCount(5)
        self.items_table.setHorizontalHeaderLabels(["المادة", "الكمية", "سعر الوحدة", "المبلغ الإجمالي", "حذف"])
        self.items_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.items_table.horizontalHeader().setMinimumSectionSize(40)
        self.items_table.horizontalHeader().sectionResized.connect(self._save_bill_col_widths)
        self._load_bill_col_widths()
        self.items_table.horizontalHeader().setLayoutDirection(Qt.RightToLeft)
        self.items_table.setStyleSheet(table_style(Colors.SUCCESS))
        self.items_table.setAlternatingRowColors(True)
        self._qty_delegate = NumericDelegate(self.items_table)
        self._price_delegate = NumericDelegate(self.items_table)
        self._total_delegate = NumericDelegate(self.items_table)
        self.items_table.setItemDelegateForColumn(1, self._qty_delegate)
        self.items_table.setItemDelegateForColumn(2, self._price_delegate)
        self.items_table.setItemDelegateForColumn(3, self._total_delegate)
        self.items_table.cellChanged.connect(self.calculate_row_total)
        self.items_table.setMinimumHeight(120)
        self.items_table.verticalHeader().setVisible(False)
        self.items_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.items_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.items_table.verticalHeader().setDefaultSectionSize(
            int(self.items_table.verticalHeader().defaultSectionSize() * 1.5)
        )
        purchase_layout.addWidget(self.items_table)

        # أزرار إدارة بنود الفاتورة
        items_buttons_layout = QHBoxLayout()
        items_buttons_layout.setContentsMargins(0, 0, 0, 0)

        add_row_btn = QPushButton("إضافة بند")
        add_row_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_FileIcon))
        add_row_btn.setFixedHeight(34)
        add_row_btn.setCursor(Qt.PointingHandCursor)
        add_row_btn.setStyleSheet(success_button_style())
        add_row_btn.clicked.connect(self.add_bill_row)

        items_buttons_layout.addWidget(add_row_btn)
        items_buttons_layout.addStretch()
        purchase_layout.addLayout(items_buttons_layout)

        # المبلغ الإجمالي وزر الحفظ
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 0, 0, 0)

        total_label = QLabel("المبلغ الإجمالي للفاتورة:")
        total_label.setStyleSheet(f"font-size: {FontSizes.XL2}; font-weight: bold; color: {Colors.DARK};")
        self.total_amount_label = QLabel("0")
        self.total_amount_label.setStyleSheet(f"""
            font-size: {FontSizes.XL2};
            font-weight: bold;
            color: {Colors.DANGER};
            padding: {_px(Spacing.MD)};
            background-color: #fadbd8;
            border-radius: {BorderRadius.MD};
            min-width: 120px;
        """)

        save_bill_btn = QPushButton("حفظ الفاتورة")
        save_bill_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_DialogSaveButton))
        save_bill_btn.setFixedHeight(40)
        save_bill_btn.setCursor(Qt.PointingHandCursor)
        save_bill_btn.setStyleSheet(success_button_style(pressed=Colors.SUCCESS_PRESSED))
        save_bill_btn.clicked.connect(self.save_purchase_bill)

        footer_layout.addWidget(total_label)
        footer_layout.addWidget(self.total_amount_label)
        footer_layout.addStretch()
        footer_layout.addWidget(save_bill_btn)
        purchase_layout.addLayout(footer_layout)

        purchase_group.setLayout(purchase_layout)
        purchase_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # قسم عرض المخزون
        inventory_group = QGroupBox("📋 المخزون الحالي")
        inventory_group.setStyleSheet(group_box_style(Colors.PRIMARY))
        inventory_layout = QVBoxLayout()
        inventory_layout.setSpacing(Spacing.MD)
        inventory_layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)

        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(0, 0, 0, 0)

        filter_label = QLabel("تصفية حسب المجموعة:")
        filter_label.setStyleSheet(f"font-size: {FontSizes.LG}; color: {Colors.DARK};")
        self.group_filter_combo = QComboBox()
        self.group_filter_combo.addItem("الكل", None)
        self.group_filter_combo.setStyleSheet(combo_style(focus_color=Colors.FOCUS_BLUE, min_width="150px"))

        refresh_inventory_btn = QPushButton("تحديث")
        refresh_inventory_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_BrowserReload))
        refresh_inventory_btn.setFixedHeight(34)
        refresh_inventory_btn.setCursor(Qt.PointingHandCursor)
        refresh_inventory_btn.setStyleSheet(primary_button_style(
            bg=Colors.PRIMARY, hover=Colors.PRIMARY_HOVER,
            font_size=FontSizes.MD, padding="6px 12px"
        ))
        refresh_inventory_btn.clicked.connect(self.load_inventory_display)

        self.group_filter_combo.currentIndexChanged.connect(self.load_inventory_display)

        filter_layout.addWidget(filter_label)
        filter_layout.addWidget(self.group_filter_combo)
        filter_layout.addWidget(refresh_inventory_btn)

        audit_btn = QPushButton("الجرد الدوري")
        audit_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        audit_btn.setFixedHeight(34)
        audit_btn.setCursor(Qt.PointingHandCursor)
        audit_btn.setStyleSheet(warning_button_style())
        audit_btn.clicked.connect(self.open_audit_dialog)
        filter_layout.addWidget(audit_btn)

        filter_layout.addStretch()
        inventory_layout.addLayout(filter_layout)

        self.inventory_table = SearchableTable()
        self.inventory_table.edit_requested.connect(self._on_inventory_edit)
        self.inventory_table.delete_requested.connect(self._on_inventory_delete)
        self.inventory_table.row_double_clicked.connect(self._on_inventory_double_click)
        self.inventory_table.setMinimumHeight(150)
        self.inventory_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.inventory_table.table.verticalHeader().setDefaultSectionSize(
            int(self.inventory_table.table.verticalHeader().defaultSectionSize() * 1.5)
        )
        inventory_layout.addWidget(self.inventory_table)

        inventory_group.setLayout(inventory_layout)
        inventory_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # قسم فواتير الشراء السابقة
        history_group = QGroupBox("📜 فواتير الشراء السابقة")
        history_group.setStyleSheet(group_box_style(Colors.WARNING))
        history_layout = QVBoxLayout()
        history_layout.setSpacing(Spacing.MD)
        history_layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)

        history_header = QHBoxLayout()
        history_header.setContentsMargins(0, 0, 0, 0)

        refresh_history_btn = QPushButton("تحديث")
        refresh_history_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_BrowserReload))
        refresh_history_btn.setFixedHeight(34)
        refresh_history_btn.setCursor(Qt.PointingHandCursor)
        refresh_history_btn.setStyleSheet(warning_button_style())
        refresh_history_btn.clicked.connect(self._load_purchase_history)

        history_header.addWidget(refresh_history_btn)
        history_header.addStretch()
        history_layout.addLayout(history_header)

        self.purchase_history_table = SearchableTable()
        self.purchase_history_table.edit_requested.connect(self._on_purchase_history_edit)
        self.purchase_history_table.delete_requested.connect(self._on_purchase_history_delete)
        self.purchase_history_table.row_double_clicked.connect(self._on_purchase_history_double_click)
        self.purchase_history_table.setMinimumHeight(150)
        self.purchase_history_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.purchase_history_table.table.verticalHeader().setDefaultSectionSize(
            int(self.purchase_history_table.table.verticalHeader().defaultSectionSize() * 1.5)
        )
        history_layout.addWidget(self.purchase_history_table)

        history_group.setLayout(history_layout)
        history_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        main_hbox = QHBoxLayout()
        main_hbox.setSpacing(10)

        right_column = QVBoxLayout()
        right_column.setSpacing(0)
        right_column.addWidget(purchase_group)

        left_column = QVBoxLayout()
        left_column.setSpacing(10)
        left_column.addWidget(inventory_group)
        left_column.addWidget(history_group)

        main_hbox.addLayout(right_column, 2)
        main_hbox.addLayout(left_column, 2)

        main_layout.addLayout(main_hbox, stretch=1)

        self.loading_overlay = LoadingOverlay(self)

    def _save_bill_col_widths(self):
        settings = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        widths = [self.items_table.columnWidth(i) for i in range(self.items_table.columnCount())]
        settings.setValue(_COL_WIDTHS_KEY, widths)

    def _load_bill_col_widths(self):
        settings = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        widths = settings.value(_COL_WIDTHS_KEY)
        if widths and isinstance(widths, list) and len(widths) == self.items_table.columnCount():
            for i, w in enumerate(widths):
                self.items_table.setColumnWidth(i, int(w))

    def on_payment_changed(self, index):
        text = self.payment_combo.currentText()
        self.cash_amount_edit.setVisible(text == "جزئي (كاش + دين)")
        self.partial_payment_source_combo.setVisible(text == "جزئي (كاش + دين)")
        if text == "جزئي (كاش + دين)":
            self.cash_amount_edit.setFocus()

    def load_data(self):
        """تحميل البيانات الأولية"""
        self.loading_overlay.start()
        QApplication.processEvents()
        self.supplier_combo.refresh()
        self.load_materials_combo()
        self.load_inventory_display()
        self._load_purchase_history()
        self.loading_overlay.stop()

    def _on_app_data_changed(self, entity_name):
        if entity_name in {"materials", "purchases", "creditors"}:
            self.load_data()

    def load_suppliers(self):
        """تحميل قائمة الموردين من جدول الديون"""
        self.supplier_combo.refresh()

    def open_audit_dialog(self):
        """فتح نافذة الجرد"""
        dialog = AuditDialog(self)
        dialog.audit_saved.connect(self.load_inventory_display)
        dialog.exec_()

    def _test_add_row(self):
        logger.debug("_test_add_row: بدأت")
        try:
            row = self.items_table.rowCount()
            self.items_table.insertRow(row)
            logger.debug(f"_test_add_row: أضيف صف رقم {row}")

            item0 = QTableWidgetItem("اختبار")
            self.items_table.setItem(row, 0, item0)
            logger.debug("_test_add_row: وضع item0 نجح")

            item1 = QTableWidgetItem("0")
            self.items_table.setItem(row, 1, item1)

            item2 = QTableWidgetItem("0")
            self.items_table.setItem(row, 2, item2)

            item3 = QTableWidgetItem("0")
            self.items_table.setItem(row, 3, item3)
            logger.debug("_test_add_row: items 1-3 نجحت")

            delete_btn = QPushButton("X")
            delete_btn.setFixedWidth(40)
            logger.debug("_test_add_row: تم إنشاء delete_btn")
            
            self.items_table.setCellWidget(row, 4, delete_btn)
            logger.debug("_test_add_row: وضع delete_btn نجح")

            logger.debug("_test_add_row: انتهت بنجاح")
        except Exception as e:
            logger.error(f"_test_add_row خطأ: {e}", exc_info=True)

