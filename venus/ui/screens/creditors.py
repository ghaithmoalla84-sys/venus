# Path: D:\acc\venus\ui\screens\creditors.py
# -*- coding: utf-8 -*-
"""
شاشة الدائنون - Venus Coffee
إدارة الديون مع الموردين والأصدقاء
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QComboBox, QTabWidget,
    QMessageBox, QDateEdit, QHeaderView, QDialog, QDialogButtonBox, QGroupBox,
    QTextEdit, QStyledItemDelegate, QMenu, QAction, QStyle, QApplication,
    QSizePolicy, QMainWindow
)
from PyQt5.QtCore import Qt, QTimer, QDate
from PyQt5.QtGui import QDoubleValidator, QColor
import sqlite3
from datetime import datetime

from venus.core.database import get_conn, now_str
from venus.core.repositories import CreditorsRepository
from venus.core.events import app_events
from venus.ui.widgets.searchable_table import SearchableTable
from venus.ui.widgets.entity_detail_dialog import EntityDetailDialog
from venus.ui.widgets.combo_quick_add import ComboWithQuickAdd
from venus.ui.widgets.loading_overlay import LoadingOverlay
from venus.ui.styles import (
    Colors, FontSizes, Spacing, BorderRadius,
    title_label_style, group_box_style, table_style,
    primary_button_style, success_button_style, danger_button_style,
    purple_button_style, gray_button_style,
    input_style, combo_style, date_edit_style, summary_label_style, info_label_style, _px
)
from venus.utils.currency import fmt, fmt_syp, fmt_usd
from venus.utils.logger import setup_logger
from venus.utils.overdue import get_overdue_debts
logger = setup_logger()

class NumericDelegate(QStyledItemDelegate):
    """ديلجيت لتقييد الإدخال بالأرقام فقط في الجداول"""
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setValidator(QDoubleValidator())
        return editor

class AddCreditorDialog(QDialog):
    """حوار إضافة دائن جديد"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("إضافة دائن جديد")
        self.setLayoutDirection(Qt.RightToLeft)
        self.setFixedWidth(400)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)

        form = QGridLayout()
        form.setVerticalSpacing(12)
        form.setHorizontalSpacing(10)

        form.addWidget(QLabel("👤 الاسم:"), 0, 0)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("اسم الدائن")
        self.name_input.setStyleSheet(input_style(focus_color=Colors.FOCUS_GREEN))
        form.addWidget(self.name_input, 0, 1)

        form.addWidget(QLabel("🏷️ النوع:"), 1, 0)
        self.type_combo = QComboBox()
        self.type_combo.addItems(["مورد", "صديق"])
        self.type_combo.setStyleSheet(combo_style(focus_color=Colors.FOCUS_GREEN))
        form.addWidget(self.type_combo, 1, 1)

        form.addWidget(QLabel("💱 العملة:"), 2, 0)
        self.currency_combo = QComboBox()
        self.currency_combo.addItems(["ليرة_سورية", "دولار"])
        self.currency_combo.setStyleSheet(combo_style(focus_color=Colors.FOCUS_GREEN))
        form.addWidget(self.currency_combo, 2, 1)

        form.addWidget(QLabel("💰 المبلغ الأولي:"), 3, 0)
        self.amount_input = QLineEdit()
        self.amount_input.setValidator(QDoubleValidator(0, 100000000, 2))
        self.amount_input.setPlaceholderText("0.00")
        self.amount_input.setStyleSheet(input_style(focus_color=Colors.FOCUS_GREEN))
        form.addWidget(self.amount_input, 3, 1)

        form.addWidget(QLabel("📅 تاريخ الاستحقاق:"), 4, 0)
        self.due_date_checkbox = QComboBox()
        self.due_date_checkbox.addItems(["بدون تحديد", "تحديد موعد استحقاق"])
        self.due_date_checkbox.setStyleSheet(combo_style(focus_color=Colors.FOCUS_GREEN))
        self.due_date_checkbox.currentIndexChanged.connect(self._on_due_date_checkbox_changed)
        form.addWidget(self.due_date_checkbox, 4, 1)

        self.due_date_edit = QDateEdit()
        self.due_date_edit.setDate(QDate.currentDate())
        self.due_date_edit.setCalendarPopup(True)
        self.due_date_edit.setStyleSheet(date_edit_style(min_width="150px"))
        self.due_date_edit.setEnabled(False)
        form.addWidget(self.due_date_edit, 5, 1)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.setLayoutDirection(Qt.RightToLeft)
        btn_ok = buttons.button(QDialogButtonBox.Ok)
        btn_ok.setText("إضافة")
        btn_ok.setStyleSheet(success_button_style(padding="10px 24px"))
        btn_ok.setAutoDefault(False)
        btn_ok.setDefault(False)
        btn_cancel = buttons.button(QDialogButtonBox.Cancel)
        btn_cancel.setText("إلغاء")
        btn_cancel.setStyleSheet(gray_button_style(padding="10px 24px"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.amount_input.returnPressed.connect(btn_ok.click)
        layout.addWidget(buttons)

        self.name_input.setFocus()

    def _on_due_date_checkbox_changed(self, index):
        self.due_date_edit.setEnabled(index == 1)

    def get_data(self):
        name = self.name_input.text().strip()
        ctype = self.type_combo.currentText()
        currency = self.currency_combo.currentText()
        amount_txt = self.amount_input.text().strip()
        if not name:
            return None
        try:
            amount = float(amount_txt) if amount_txt else 0.0
        except ValueError:
            amount = 0.0
        due_date = None
        if self.due_date_checkbox.currentIndex() == 1:
            due_date = self.due_date_edit.date().toString("yyyy-MM-dd")
        return {
            "name": name,
            "type": ctype,
            "currency": currency,
            "amount": amount,
            "due_date": due_date
        }

class PaymentDialog(QDialog):
    """حوار تسجيل دفعة"""
    def __init__(self, creditor_name, balance, currency, exchange_rate, parent=None):
        super().__init__(parent)
        self.creditor_name = creditor_name
        self.balance = balance
        self.currency = currency
        self.exchange_rate = exchange_rate
        self.setWindowTitle(f"تسديد دفعة - {creditor_name}")
        self.setLayoutDirection(Qt.RightToLeft)
        self.setFixedWidth(420)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)

        info_group = QGroupBox("📋 معلومات الدائن")
        info_group.setStyleSheet("""
            QGroupBox {
                font-size: 15px;
                font-weight: bold;
                color: #2c3e50;
                border: 2px solid #3498db;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                right: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(15, 15, 15, 15)

        lbl_name = QLabel(f"الاسم: {self.creditor_name}")
        lbl_name.setStyleSheet("font-size: 14px; color: #2c3e50;")
        info_layout.addWidget(lbl_name)

        if self.currency == "دولار":
            lbl_balance = QLabel(f"الرصيد الحالي: {fmt_usd(self.balance)}")
        else:
            lbl_balance = QLabel(f"الرصيد الحالي: {fmt_syp(self.balance)}")
        lbl_balance.setStyleSheet("font-size: 14px; color: #e74c3c; font-weight: bold;")
        info_layout.addWidget(lbl_balance)

        if self.currency == "دولار" and self.exchange_rate:
            equivalent = self.balance * self.exchange_rate
            lbl_eq = QLabel(f"ما يعادل: {fmt_syp(equivalent)}")
            lbl_eq.setStyleSheet("font-size: 13px; color: #7f8c8d;")
            info_layout.addWidget(lbl_eq)

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        form = QGridLayout()
        form.setVerticalSpacing(12)
        form.setHorizontalSpacing(10)

        form.addWidget(QLabel("📅 التاريخ:"), 0, 0)
        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setStyleSheet(date_edit_style(min_width="150px"))
        form.addWidget(self.date_edit, 0, 1)

        form.addWidget(QLabel("💵 المبلغ:"), 1, 0)
        self.amount_input = QLineEdit()
        self.amount_input.setValidator(QDoubleValidator(0, 100000000, 2))
        self.amount_input.setPlaceholderText("0.00")
        self.amount_input.setStyleSheet(input_style(focus_color=Colors.FOCUS_GREEN))
        form.addWidget(self.amount_input, 1, 1)

        form.addWidget(QLabel("📝 ملاحظات:"), 2, 0)
        self.notes_input = QLineEdit()
        self.notes_input.setPlaceholderText("ملاحظات اختيارية...")
        self.notes_input.setStyleSheet(input_style(focus_color=Colors.FOCUS_GREEN))
        form.addWidget(self.notes_input, 2, 1)

        form.addWidget(QLabel("🏦 المصدر:"), 3, 0)
        self.source_combo = QComboBox()
        self.source_combo.addItems(["من درج المحل", "خارجي"])
        self.source_combo.setStyleSheet("""
            QComboBox {
                padding: 10px;
                font-size: 14px;
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                background-color: white;
                min-width: 150px;
            }
            QComboBox:focus { border-color: #27ae60; }
            QComboBox::drop-down { border: none; width: 30px; }
        """)
        form.addWidget(self.source_combo, 3, 1)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.setLayoutDirection(Qt.RightToLeft)
        btn_ok = buttons.button(QDialogButtonBox.Ok)
        btn_ok.setText("تسجيل الدفعة")
        btn_ok.setStyleSheet(success_button_style(padding="10px 24px"))
        btn_ok.setAutoDefault(False)
        btn_ok.setDefault(False)
        btn_cancel = buttons.button(QDialogButtonBox.Cancel)
        btn_cancel.setText("إلغاء")
        btn_cancel.setStyleSheet(gray_button_style(padding="10px 24px"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.notes_input.returnPressed.connect(btn_ok.click)
        layout.addWidget(buttons)

        self.amount_input.setFocus()

    def get_data(self):
        date_str = self.date_edit.date().toString("yyyy-MM-dd")
        date_str = date_str.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
        amount_txt = self.amount_input.text().strip()
        notes = self.notes_input.text().strip()
        source = self.source_combo.currentText()

        if not amount_txt:
            return None
        try:
            amount = float(amount_txt)
        except ValueError:
            return None

        if amount <= 0:
            return None

        if amount > self.balance + 0.01:
            return "exceeded"

        dt = f"{date_str} {datetime.now().strftime('%H:%M:%S')}"
        return {
            "date": dt,
            "amount": amount,
            "notes": notes,
            "source": source
        }

class MovementsDialog(QDialog):
    """حوار عرض سجل الحركات"""
    def __init__(self, creditor_id, creditor_name, parent=None):
        super().__init__(parent)
        self.creditor_id = creditor_id
        self.creditor_name = creditor_name
        self.setWindowTitle(f"📜 سجل الحركات - {creditor_name}")
        self.setLayoutDirection(Qt.RightToLeft)
        self.setMinimumSize(700, 500)
        self.init_ui()
        self.load_movements()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)

        header = QLabel(f"📜 سجل حركات: {self.creditor_name}")
        header.setStyleSheet(f"""
            font-size: {FontSizes.XL3};
            font-weight: bold;
            color: {Colors.DARK};
            padding: 10px;
        """)
        header.setAlignment(Qt.AlignRight)
        layout.addWidget(header)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["📅 التاريخ", "🔔 النوع", "💰 المبلغ", "📝 ملاحظات"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setLayoutDirection(Qt.RightToLeft)
        self.table.setStyleSheet(table_style("#9b59b6"))
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        close_btn = QPushButton("إغلاق")
        close_btn.setFixedHeight(40)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(gray_button_style(padding="8px 24px"))
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def load_movements(self):
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT التاريخ, نوع_الحركة, المبلغ, ملاحظات
                FROM تحركات_الديون
                WHERE معرف_الدين = ?
                ORDER BY معرف DESC
            """, (self.creditor_id,))
            rows = cur.fetchall()

            self.table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                date_item = QTableWidgetItem(str(row["التاريخ"] or ""))
                date_item.setFlags(date_item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(r, 0, date_item)

                type_text = str(row["نوع_الحركة"] or "")
                type_item = QTableWidgetItem(type_text)
                type_item.setFlags(type_item.flags() & ~Qt.ItemIsEditable)
                if type_text == "إضافة":
                    type_item.setForeground(QColor("#e74c3c"))
                elif type_text == "دفعة":
                    type_item.setForeground(QColor("#27ae60"))
                self.table.setItem(r, 1, type_item)

                amount_item = QTableWidgetItem(fmt(row['المبلغ'] or 0))
                amount_item.setFlags(amount_item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(r, 2, amount_item)

                notes_item = QTableWidgetItem(str(row["ملاحظات"] or ""))
                notes_item.setFlags(notes_item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(r, 3, notes_item)

        except Exception as e:
            logger.error(str(e))
            QMessageBox.critical(self, "خطأ", f"فشل تحميل الحركات:\n{str(e)}")
        finally:
            conn.close()



class EditCreditorDialog(QDialog):
    """حوار تعديل بيانات دائن (الاسم/النوع/العملة فقط)"""
    def __init__(self, creditor_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("تعديل بيانات الدائن")
        self.setLayoutDirection(Qt.RightToLeft)
        self.setFixedWidth(400)
        self._creditor_data = creditor_data
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)

        form = QGridLayout()
        form.setVerticalSpacing(12)
        form.setHorizontalSpacing(10)

        form.addWidget(QLabel("👤 الاسم:"), 0, 0)
        self.name_input = QLineEdit(self._creditor_data.get("اسم_الطرف", ""))
        self.name_input.setPlaceholderText("اسم الدائن")
        self.name_input.setStyleSheet(input_style(focus_color=Colors.FOCUS_GREEN))
        form.addWidget(self.name_input, 0, 1)

        form.addWidget(QLabel("🏷️ النوع:"), 1, 0)
        self.type_combo = QComboBox()
        self.type_combo.addItems(["مورد", "صديق"])
        current_type = self._creditor_data.get("نوع_الطرف", "مورد")
        idx = self.type_combo.findText(current_type)
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)
        self.type_combo.setStyleSheet(combo_style(focus_color=Colors.FOCUS_GREEN))
        form.addWidget(self.type_combo, 1, 1)

        form.addWidget(QLabel("💱 العملة:"), 2, 0)
        self.currency_combo = QComboBox()
        self.currency_combo.addItems(["ليرة_سورية", "دولار"])
        current_currency = self._creditor_data.get("العملة", "ليرة_سورية")
        idx = self.currency_combo.findText(current_currency)
        if idx >= 0:
            self.currency_combo.setCurrentIndex(idx)
        self.currency_combo.setStyleSheet(combo_style(focus_color=Colors.FOCUS_GREEN))
        form.addWidget(self.currency_combo, 2, 1)

        form.addWidget(QLabel("📅 تاريخ الاستحقاق:"), 3, 0)
        self.due_date_checkbox = QComboBox()
        self.due_date_checkbox.addItems(["بدون تحديد", "تحديد موعد استحقاق"])
        self.due_date_checkbox.setStyleSheet(combo_style(focus_color=Colors.FOCUS_GREEN))
        self.due_date_checkbox.currentIndexChanged.connect(self._on_due_date_checkbox_changed)
        form.addWidget(self.due_date_checkbox, 3, 1)

        self.due_date_edit = QDateEdit()
        self.due_date_edit.setCalendarPopup(True)
        self.due_date_edit.setStyleSheet(date_edit_style(min_width="150px"))
        self.due_date_edit.setEnabled(False)
        form.addWidget(self.due_date_edit, 4, 1)

        existing_due_date = self._creditor_data.get("تاريخ_استحقاق")
        if existing_due_date:
            self.due_date_checkbox.setCurrentIndex(1)
            self.due_date_edit.setEnabled(True)
            qdate = QDate.fromString(str(existing_due_date), "yyyy-MM-dd")
            if qdate.isValid():
                self.due_date_edit.setDate(qdate)

        layout.addLayout(form)

        info_label = QLabel("⚠️ لا يمكن تعديل الرصيد مباشرة.\nالرصيد يُعدَّل فقط عبر حركات موثقة (إضافة/دفعة).")
        info_label.setStyleSheet(info_label_style())
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.setLayoutDirection(Qt.RightToLeft)
        btn_ok = buttons.button(QDialogButtonBox.Ok)
        btn_ok.setText("حفظ")
        btn_ok.setStyleSheet(success_button_style(padding="10px 24px"))
        btn_ok.setAutoDefault(False)
        btn_ok.setDefault(False)
        btn_cancel = buttons.button(QDialogButtonBox.Cancel)
        btn_cancel.setText("إلغاء")
        btn_cancel.setStyleSheet(gray_button_style(padding="10px 24px"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.name_input.setFocus()

    def _on_due_date_checkbox_changed(self, index):
        self.due_date_edit.setEnabled(index == 1)

    def get_data(self):
        name = self.name_input.text().strip()
        ctype = self.type_combo.currentText()
        currency = self.currency_combo.currentText()
        if not name:
            return None
        due_date = None
        if self.due_date_checkbox.currentIndex() == 1:
            due_date = self.due_date_edit.date().toString("yyyy-MM-dd")
        return {
            "name": name,
            "type": ctype,
            "currency": currency,
            "due_date": due_date
        }

class CreditorsScreen(QWidget):
    """شاشة إدارة الدائنون"""

    def __init__(self):
        super().__init__()
        self.setLayoutDirection(Qt.RightToLeft)
        self.creditor_ids = []
        self.creditors_data = []
        self.exchange_rate = None
        self.init_ui()
        self.load_data()

        timer = QTimer(self)
        timer.timeout.connect(self.load_data)
        timer.start(30000)

        app_events.data_changed.connect(self._on_app_data_changed)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(30, 30, 30, 30)

        title = QLabel("👥 الدائنون")
        title.setStyleSheet(title_label_style(font_size=FontSizes.XL6, color=Colors.DARK))
        title.setAlignment(Qt.AlignRight)
        main_layout.addWidget(title)

        info_group = QGroupBox("📊 معلومات عامة")
        info_group.setStyleSheet(group_box_style(Colors.PRIMARY))
        info_layout = QHBoxLayout()
        info_layout.setContentsMargins(20, 15, 20, 15)

        self.rate_label = QLabel("💱 سعر الصرف: جاري التحميل...")
        self.rate_label.setStyleSheet(f"""
            font-size: {FontSizes.XL};
            font-weight: bold;
            color: {Colors.WARNING};
            background-color: #fef9e7;
            border: 1px solid #f9e79f;
            border-radius: {BorderRadius.MD};
            padding: {_px(Spacing.XL)} {_px(Spacing.LG)};
        """)
        self.rate_label.setMinimumWidth(300)
        info_layout.addWidget(self.rate_label)

        self.total_label = QLabel("")
        self.total_label.setStyleSheet(summary_label_style(bg="#f8f9fa", border_color="#dee2e6"))
        self.total_label.setMinimumWidth(300)
        info_layout.addWidget(self.total_label)

        info_layout.addStretch()
        info_group.setLayout(info_layout)
        info_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        main_layout.addWidget(info_group)

        self.overdue_group = QGroupBox("⚠️ الديون المتأخرة")
        self.overdue_group.setStyleSheet(group_box_style(Colors.DANGER))
        overdue_layout = QVBoxLayout()
        overdue_layout.setContentsMargins(20, 15, 20, 15)
        self.overdue_label = QLabel("جاري التحقق من الديون المتأخرة...")
        self.overdue_label.setStyleSheet(f"""
            font-size: {FontSizes.LG};
            font-weight: bold;
            color: {Colors.DANGER};
            padding: {_px(Spacing.SM)} {_px(Spacing.MD)};
        """)
        self.overdue_label.setAlignment(Qt.AlignRight)
        overdue_layout.addWidget(self.overdue_label)
        self.overdue_group.setLayout(overdue_layout)
        self.overdue_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        main_layout.addWidget(self.overdue_group)

        btn_group = QGroupBox("⚡ الإجراءات")
        btn_group.setStyleSheet(group_box_style(Colors.SUCCESS))
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(20, 15, 20, 15)
        btn_layout.setSpacing(15)

        self.add_btn = QPushButton("إضافة دائن")
        self.add_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_FileIcon))
        self.add_btn.setFixedHeight(45)
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.setStyleSheet(success_button_style())
        self.add_btn.clicked.connect(self.add_creditor)
        btn_layout.addWidget(self.add_btn)

        self.payment_btn = QPushButton("تسديد دفعة")
        self.payment_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.payment_btn.setFixedHeight(45)
        self.payment_btn.setCursor(Qt.PointingHandCursor)
        self.payment_btn.setStyleSheet(primary_button_style(
            bg=Colors.PRIMARY, hover=Colors.PRIMARY_HOVER,
            font_size=FontSizes.LG, padding="8px 16px"
        ))
        self.payment_btn.clicked.connect(self.record_payment)
        btn_layout.addWidget(self.payment_btn)

        self.history_btn = QPushButton("سجل الحركات")
        self.history_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        self.history_btn.setFixedHeight(45)
        self.history_btn.setCursor(Qt.PointingHandCursor)
        self.history_btn.setStyleSheet(purple_button_style())
        self.history_btn.clicked.connect(self.view_history)
        btn_layout.addWidget(self.history_btn)

        btn_layout.addStretch()
        btn_group.setLayout(btn_layout)
        btn_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        main_layout.addWidget(btn_group)

        table_group = QGroupBox("📋 قائمة الدائنون")
        table_group.setStyleSheet(group_box_style(Colors.BORDER))
        table_layout = QVBoxLayout()
        table_layout.setContentsMargins(15, 15, 15, 15)

        self.searchable_table = SearchableTable()
        self.searchable_table.edit_requested.connect(self._on_edit_creditor)
        self.searchable_table.delete_requested.connect(self._on_delete_creditor)
        self.searchable_table.row_double_clicked.connect(self._on_row_double_clicked)
        self.searchable_table.setMinimumHeight(300)
        table_layout.addWidget(self.searchable_table)

        table_group.setLayout(table_layout)
        table_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_layout.addWidget(table_group, stretch=1)

        self.loading_overlay = LoadingOverlay(self)
        main_layout.addWidget(self.loading_overlay)

    def load_exchange_rate(self):
        from venus.utils.currency import get_exchange_rate
        try:
            rate = get_exchange_rate()
            if rate is not None:
                self.exchange_rate = rate
                self.rate_label.setText(
                    f"💱 سعر الصرف: {rate:,.2f} ليرة سورية / دولار"
                )
            else:
                self.exchange_rate = None
                self.rate_label.setText("💱 سعر الصرف: غير محدد")
        except Exception as e:
            logger.error(f"فشل تحميل سعر الصرف: {type(e).__name__}")
            self.exchange_rate = None
            self.rate_label.setText("💱 سعر الصرف: غير محدد")

    def load_data(self):
        self.loading_overlay.start()
        QApplication.processEvents()
        self.load_exchange_rate()

        conn = None
        try:
            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT معرف, اسم_الطرف, نوع_الطرف, العملة, الرصيد, حالة_الدين, تاريخ_استحقاق
                FROM الديون
                ORDER BY اسم_الطرف
                LIMIT 500
            """)  # TODO: add pagination if shop scales
            rows = cursor.fetchall()

            self.creditor_ids = []
            self.creditors_data = []

            headers = ["معرف", "👤 الاسم", "🏷️ النوع", "💱 العملة", "💰 الرصيد",
                       "💵 ما يعادل بالليرة", "📌 الحالة", "📅 تاريخ الاستحقاق"]
            display_rows = []
            for row in rows:
                cid, name, ctype, currency, balance, status, due_date = row
                self.creditor_ids.append(cid)
                self.creditors_data.append(row)

                equivalent = 0.0
                if currency == "دولار" and self.exchange_rate:
                    equivalent = (balance or 0) * self.exchange_rate
                else:
                    equivalent = balance or 0

                display_rows.append([
                    cid,
                    name or "",
                    ctype or "",
                    currency or "",
                    balance or 0,
                    equivalent,
                    status or "نشط",
                    due_date or "—"
                ])

            self.searchable_table.set_data(headers, display_rows, id_column_index=0)
            self.searchable_table.table.setColumnHidden(0, True)

            total_syp = 0.0
            total_usd = 0.0
            for row in rows:
                _, _, _, currency, balance, _, _ = row
                b = balance or 0
                if currency == "دولار":
                    total_usd += b
                else:
                    total_syp += b

            parts = []
            if total_syp > 0:
                parts.append(f"ليرة: {fmt_syp(total_syp)}")
            if total_usd > 0:
                parts.append(f"دولار: {fmt_usd(total_usd)}")
            if self.exchange_rate and total_usd > 0:
                total_eq = total_syp + (total_usd * self.exchange_rate)
                parts.append(f"الإجمالي بالليرة: {fmt_syp(total_eq)}")

            self.total_label.setText(" | ".join(parts) if parts else "لا توجد ديون")

            self.load_overdue_alert()

        except Exception as e:
            logger.error(str(e))
            QMessageBox.critical(self, "خطأ", f"فشل تحميل البيانات:\n{str(e)}")
        finally:
            if conn:
                conn.close()
            self.loading_overlay.stop()

    def _on_app_data_changed(self, entity_name):
        if entity_name in {"creditors", "purchases"}:
            self.load_data()

    def load_overdue_alert(self):
        conn = None
        try:
            conn = get_conn()
            overdue_rows = get_overdue_debts(conn)

            if not overdue_rows:
                self.overdue_group.hide()
                return

            self.overdue_group.show()
            lines = []
            for row in overdue_rows:
                name = row["اسم_الطرف"]
                ctype = row["نوع_الطرف"]
                currency = row["العملة"]
                balance = row["الرصيد"]
                due_date = row["تاريخ_استحقاق"]
                b = fmt_syp(balance) if currency == 'ليرة_سورية' else fmt_usd(balance)
                due_str = due_date or "—"
                lines.append(f"• {name} ({ctype}) — {b} — استحقاق: {due_str}")

            self.overdue_label.setText(
                f"⚠️ يوجد {len(overdue_rows)} دين/ديون متأخرة:\n" + "\n".join(lines)
            )
        except Exception as e:
            logger.error(f"فشل تحميل تنبيه الديون المتأخرة: {e}")
            self.overdue_group.hide()
        finally:
            if conn:
                conn.close()


    def _get_creditor_by_id(self, creditor_id):
        for idx, cid in enumerate(self.creditor_ids):
            if cid == creditor_id:
                return self.creditors_data[idx]
        return None

    def _on_edit_creditor(self, creditor_id):
        row_data = self._get_creditor_by_id(creditor_id)
        if not row_data:
            return
        cid, name, ctype, currency, balance, status, due_date = row_data
        creditor_data = {
            "اسم_الطرف": name,
            "نوع_الطرف": ctype,
            "العملة": currency,
            "الرصيد": balance,
            "حالة_الدين": status,
            "تاريخ_استحقاق": due_date
        }
        dialog = EditCreditorDialog(creditor_data, self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if not data:
                QMessageBox.warning(self, "تنبيه", "الرجاء إدخال اسم الدائن")
                return
            try:
                repo = CreditorsRepository()
                repo.update(cid, اسم_الطرف=data["name"], نوع_الطرف=data["type"],
                            العملة=data["currency"], تاريخ_استحقاق=data["due_date"])
                self.load_data()
                app_events.emit_data_changed("creditors")
                QMessageBox.information(self, "نجاح", "تم تعديل بيانات الدائن بنجاح!")
            except Exception as e:
                logger.error(str(e))
                QMessageBox.critical(self, "خطأ", f"فشل تعديل الدائن:\n{str(e)}")

    def _on_delete_creditor(self, creditor_id):
        row_data = self._get_creditor_by_id(creditor_id)
        if not row_data:
            return
        cid, name, ctype, currency, balance, status, due_date = row_data

        conn = None
        try:
            conn = get_conn()
            cursor = conn.cursor()

            cursor.execute("PRAGMA foreign_keys = ON")

            cursor.execute("SELECT COUNT(*) FROM فواتير_الشراء WHERE معرف_المورد = ?", (cid,))
            invoice_count = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM تحركات_الديون WHERE معرف_الدين = ? AND نوع_الحركة = 'دفعة'",
                (cid,)
            )
            payment_count = cursor.fetchone()[0]

            if invoice_count > 0 or payment_count > 0:
                parts = []
                if invoice_count > 0:
                    parts.append(f"{invoice_count} فاتورة شراء")
                if payment_count > 0:
                    parts.append(f"{payment_count} حركة دين")
                detail = " و/أو ".join(parts)
                QMessageBox.warning(
                    self,
                    "لا يمكن الحذف",
                    f"لا يمكن حذف '{name}' لوجود {detail} مرتبطة به. "
                    "لا يمكن حذف دائن له سجل تعاملات."
                )
                return

            reply = QMessageBox.question(
                self, "تأكيد الحذف",
                f"سيتم حذف هذا الدائن وجميع الحركات المرتبطة به (إن وجدت) بشكل نهائي. "
                f"هذا الإجراء لا يمكن التراجع عنه.\n\n"
                f"هل أنت متأكد من حذف الدائن '{name}'؟",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

            cursor.execute("BEGIN TRANSACTION")
            cursor.execute("DELETE FROM تحركات_الديون WHERE معرف_الدين = ?", (cid,))
            cursor.execute("DELETE FROM الديون WHERE معرف = ?", (cid,))
            conn.commit()
            self.load_data()
            app_events.emit_data_changed("creditors")
            QMessageBox.information(self, "نجاح", "تم حذف الدائن بنجاح!")

            try:
                main_window = self.window()
                if isinstance(main_window, QMainWindow):
                    main_window.show_status("تم حذف الدائن بنجاح", "success")
            except Exception:
                pass
        except Exception as e:
            error_msg = str(e)
            if "FOREIGN KEY" in error_msg:
                QMessageBox.warning(
                    self,
                    "لا يمكن الحذف",
                    f"لا يمكن حذف '{name}' لوجود سجلات مرتبطة به. "
                    "لا يمكن حذف دائن له سجل تعاملات."
                )
            else:
                logger.error(str(e))
                QMessageBox.critical(self, "خطأ", f"فشل حذف الدائن:\n{str(e)}")
        finally:
            if conn:
                conn.close()

    def _on_row_double_clicked(self, creditor_id):
        row_data = self._get_creditor_by_id(creditor_id)
        if not row_data:
            return
        cid, name, ctype, currency, balance, status, due_date = row_data

        conn = None
        try:
            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT التاريخ, نوع_الحركة, المبلغ, ملاحظات
                FROM تحركات_الديون
                WHERE معرف_الدين = ?
                ORDER BY معرف DESC
                LIMIT 500
            """, (cid,))
            movements = cursor.fetchall()

            cursor.execute("""
                SELECT d.معرف_المادة_الفرعية, m.الاسم, d.سعر_الوحدة
                FROM تفاصيل_الشراء d
                JOIN فواتير_الشراء f ON d.معرف_الفاتورة = f.معرف
                JOIN المواد_الفرعية m ON d.معرف_المادة_الفرعية = m.معرف
                WHERE f.معرف_المورد = ?
                ORDER BY d.معرف DESC
            """, (cid,))
            price_rows = cursor.fetchall()

            equivalent = 0.0
            if currency == "دولار" and self.exchange_rate:
                equivalent = (balance or 0) * self.exchange_rate
            else:
                equivalent = balance or 0

            if currency == "دولار":
                balance_str = fmt_usd(balance or 0)
            else:
                balance_str = fmt_syp(balance or 0)
            detail_data = {
                "الاسم": name,
                "النوع": ctype,
                "العملة": currency,
                "الرصيد الحالي": balance_str,
                "ما يعادل بالليرة": fmt_syp(equivalent) if currency == "دولار" else fmt_syp(balance or 0),
                "الحالة": status or "نشط",
                "تاريخ الاستحقاق": due_date or "—"
            }

            related_headers = ["📅 التاريخ", "🔔 النوع", "💰 المبلغ", "📝 ملاحظات"]
            related_rows = []
            for m in movements:
                related_rows.append([m["التاريخ"], m["نوع_الحركة"], m["المبلغ"], m["ملاحظات"]])

            price_headers = ["المادة", "آخر سعر", "السعر السابق", "نسبة التغيّر"]
            price_table_rows = []
            material_prices = {}
            for row in price_rows:
                mid, mname, price = row
                if mid not in material_prices:
                    material_prices[mid] = []
                material_prices[mid].append((mname, float(price or 0)))

            for mid, prices in material_prices.items():
                unique_prices = []
                seen = set()
                for mname, price in prices:
                    if price not in seen:
                        seen.add(price)
                        unique_prices.append((mname, price))
                    if len(unique_prices) >= 2:
                        break
                if len(unique_prices) >= 2:
                    mname, last_price = unique_prices[0]
                    _, prev_price = unique_prices[1]
                    if prev_price != 0:
                        change_pct = ((last_price - prev_price) / prev_price) * 100
                        change_str = f"{change_pct:+.1f}%"
                    else:
                        change_str = "—"
                    price_table_rows.append([mname, f"{last_price:,.2f}", f"{prev_price:,.2f}", change_str])
                elif len(unique_prices) == 1:
                    mname, price = unique_prices[0]
                    price_table_rows.append([mname, f"{price:,.2f}", "—", "لا تغيير"])

            dialog = EntityDetailDialog(
                f"📜 تفاصيل الدائن - {name}",
                detail_data=detail_data,
                related_rows=related_rows if related_rows else None,
                related_headers=related_headers if related_rows else None,
                related_rows_2=price_table_rows if price_table_rows else None,
                related_headers_2=price_headers if price_table_rows else None,
                parent=self
            )
            dialog.related_table.setSelectionBehavior(QTableWidget.SelectRows)
            dialog.related_table.setSelectionMode(QTableWidget.SingleSelection)
            if related_rows:
                dialog.related_table.setContextMenuPolicy(Qt.CustomContextMenu)
                dialog.related_table.customContextMenuRequested.connect(
                    lambda pos, d=dialog, cid=cid, b=balance, s=status: self._on_movement_context_menu(d, cid, b, s, pos)
                )
            dialog.exec_()
        except Exception as e:
            logger.error(str(e))
            QMessageBox.critical(self, "خطأ", f"فشل تحميل التفاصيل:\n{str(e)}")
        finally:
            if conn:
                conn.close()

    def _on_movement_context_menu(self, detail_dialog, creditor_id, current_balance, current_status, pos):
        table = detail_dialog.related_table
        item = table.itemAt(pos)
        if not item:
            return
        row = item.row()

        movement_type = table.item(row, 1).text()
        amount_text = table.item(row, 2).text()
        try:
            amount = float(amount_text)
        except ValueError:
            return

        menu = QMenu(table)
        menu.setLayoutDirection(Qt.RightToLeft)

        delete_action = menu.addAction(f"🗑️ حذف هذه الحركة ({movement_type} - {fmt(amount)})")

        def do_delete():
            if movement_type == "دفعة":
                self._delete_payment_movement(creditor_id, amount, current_balance, current_status, table, row)
            elif movement_type == "إضافة":
                self._delete_addition_movement(creditor_id, amount, current_balance, table, row)

        delete_action.triggered.connect(do_delete)
        menu.exec_(table.viewport().mapToGlobal(pos))

    def _delete_payment_movement(self, creditor_id, amount, current_balance, current_status, table, row):
        reply = QMessageBox.question(
            self,
            "تأكيد حذف الدفعة",
            f"هل أنت متأكد من حذف دفعة بقيمة {fmt(amount)}؟\n"
            "سيتم زيادة الرصيد وإنقاص المبلغ المدفوع بنفس القيمة.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        conn = None
        try:
            conn = get_conn()
            conn.execute("PRAGMA foreign_keys = ON")
            cursor = conn.cursor()
            cursor.execute("BEGIN TRANSACTION")

            cursor.execute("""
                DELETE FROM تحركات_الديون
                WHERE معرف = (SELECT معرف FROM تحركات_الديون
                              WHERE معرف_الدين = ? AND نوع_الحركة = 'دفعة' AND المبلغ = ?
                              ORDER BY معرف DESC LIMIT 1)
            """, (creditor_id, amount))

            cursor.execute("""
                UPDATE الديون
                SET المبلغ_المدفوع = CASE
                        WHEN المبلغ_المدفوع >= ? THEN المبلغ_المدفوع - ?
                        ELSE 0
                    END,
                    الرصيد = المبلغ_الإجمالي - (CASE
                        WHEN المبلغ_المدفوع >= ? THEN المبلغ_المدفوع - ?
                        ELSE 0
                    END),
                    حالة_الدين = CASE
                        WHEN المبلغ_الإجمالي - (CASE WHEN المبلغ_المدفوع >= ? THEN المبلغ_المدفوع - ? ELSE 0 END) > 0.01 THEN 'نشط'
                        ELSE حالة_الدين
                    END,
                    تاريخ_التحديث = CURRENT_TIMESTAMP
                WHERE معرف = ?
            """, (amount, amount, amount, amount, amount, amount, creditor_id))

            conn.commit()
            table.removeRow(row)
            self.load_data()
            app_events.emit_data_changed("creditors")
            QMessageBox.information(self, "نجاح", "تم حذف الدفعة بنجاح وتحديث الرصيد!")

        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(str(e))
            QMessageBox.critical(self, "خطأ", f"فشل حذف الحركة:\n{str(e)}")
        finally:
            if conn:
                conn.close()

    def _delete_addition_movement(self, creditor_id, amount, current_balance, table, row):
        conn = None
        try:
            conn = get_conn()
            conn.execute("PRAGMA foreign_keys = ON")
            cursor = conn.cursor()
            cursor.execute("BEGIN TRANSACTION")

            cursor.execute("""
                SELECT المبلغ_المدفوع, الرصيد FROM الديون WHERE معرف = ?
            """, (creditor_id,))
            debt_row = cursor.fetchone()
            if not debt_row:
                conn.rollback()
                QMessageBox.warning(self, "خطأ", "لم يتم العثور على الدين المطلوب")
                return

            paid_amount = debt_row[0] or 0
            balance_after = debt_row[1] or 0

            new_paid = paid_amount - amount
            new_balance = balance_after - amount

            if new_paid < -0.01 or new_balance < -0.01:
                conn.rollback()
                QMessageBox.warning(
                    self,
                    "لا يمكن حذف هذه الإضافة",
                    "لا يمكن حذف هذه الحركة لأنها ستسبب رصيد سالب.\n"
                    "توجد دفعات لاحقة تعتمد على هذه الإضافة. "
                    "يرجى حذف الدفعات أولاً ثم حذف الإضافة."
                )
                return

            cursor.execute("""
                DELETE FROM تحركات_الديون
                WHERE معرف = (SELECT معرف FROM تحركات_الديون
                              WHERE معرف_الدين = ? AND نوع_الحركة = 'إضافة' AND المبلغ = ?
                              ORDER BY معرف DESC LIMIT 1)
            """, (creditor_id, amount))

            cursor.execute("""
                UPDATE الديون
                SET المبلغ_الإجمالي = CASE
                        WHEN المبلغ_الإجمالي >= ? THEN المبلغ_الإجمالي - ?
                        ELSE 0
                    END,
                    المبلغ_المدفوع = CASE
                        WHEN المبلغ_المدفوع >= ? THEN المبلغ_المدفوع - ?
                        ELSE 0
                    END,
                    الرصيد = الرصيد - ?,
                    حالة_الدين = CASE
                        WHEN الرصيد - ? <= 0.01 THEN 'مسدد'
                        ELSE حالة_الدين
                    END,
                    تاريخ_التحديث = CURRENT_TIMESTAMP
                WHERE معرف = ?
            """, (amount, amount, amount, amount, amount, amount, creditor_id))

            conn.commit()
            table.removeRow(row)
            self.load_data()
            app_events.emit_data_changed("creditors")
            QMessageBox.information(self, "نجاح", "تم حذف الإضافة بنجاح وتحديث الأرصدة!")

        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(str(e))
            QMessageBox.critical(self, "خطأ", f"فشل حذف الحركة:\n{str(e)}")
        finally:
            if conn:
                conn.close()

    def add_creditor(self):
        dialog = AddCreditorDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if not data:
                QMessageBox.warning(self, "تنبيه", "الرجاء إدخال اسم الدائن")
                return

            conn = None
            try:
                conn = get_conn()
                conn.execute("PRAGMA foreign_keys = ON")
                cursor = conn.cursor()
                cursor.execute("BEGIN TRANSACTION")

                cursor.execute("""
                    INSERT INTO الديون
                    (اسم_الطرف, نوع_الطرف, العملة, المبلغ_الإجمالي, الرصيد, حالة_الدين, ملاحظات, تاريخ_استحقاق, تاريخ_الإنشاء, تاريخ_التحديث)
                    VALUES (?, ?, ?, ?, ?, 'نشط', ?, ?, ?, ?)
                """, (
                    data["name"],
                    data["type"],
                    data["currency"],
                    data["amount"],
                    data["amount"],
                    f"إضافة دائن - {data['type']}",
                    data.get("due_date"),
                    now_str(),
                    now_str()
                ))

                creditor_id = cursor.lastrowid

                if data["amount"] > 0:
                    cursor.execute("""
                        INSERT INTO تحركات_الديون
                        (معرف_الدين, التاريخ, المبلغ, نوع_الحركة, ملاحظات)
                        VALUES (?, ?, ?, 'إضافة', ?)
                    """, (
                    creditor_id,
                    now_str(),
                    data["amount"],
                    "رصيد افتتاحي"
                ))

                conn.commit()
                self.load_data()
                app_events.emit_data_changed("creditors")
                QMessageBox.information(self, "نجاح", "تم إضافة الدائن بنجاح!")

                try:
                    main_window = self.window()
                    if isinstance(main_window, QMainWindow):
                        main_window.show_status(f"تم إضافة الدائن '{data['name']}' بنجاح", "success")
                except Exception:
                    pass

            except sqlite3.IntegrityError:
                if conn:
                    conn.rollback()
                QMessageBox.warning(self, "تنبيه", "اسم الدائن موجود مسبقاً")
            except Exception as e:
                logger.error(str(e))
                if conn:
                    conn.rollback()
                QMessageBox.critical(self, "خطأ", f"فشل إضافة الدائن:\n{str(e)}")
            finally:
                if conn:
                    conn.close()

    def record_payment(self):
        current_row = self.searchable_table.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "تنبيه", "الرجاء تحديد دائن من الجدول")
            return

        creditor_id = self.creditor_ids[current_row]
        row_data = self.creditors_data[current_row]
        _, name, _, currency, balance, status, _ = row_data

        if status == "مسدد":
            QMessageBox.information(self, "معلومة", "هذا الدين مسدد بالكامل")
            return

        dialog = PaymentDialog(
            name,
            balance or 0,
            currency or "ليرة_سورية",
            self.exchange_rate,
            self
        )
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if not data:
                QMessageBox.warning(self, "خطأ", "الرجاء إدخال مبلغ صحيح")
                return
            if data == "exceeded":
                QMessageBox.warning(self, "تنبيه", "المبلغ المدخل يتجاوز الرصيد الحالي")
                return

            conn = None
            try:
                conn = get_conn()
                conn.execute("PRAGMA foreign_keys = ON")
                cursor = conn.cursor()
                cursor.execute("BEGIN TRANSACTION")

                cursor.execute("""
                    UPDATE الديون
                    SET الرصيد = الرصيد - ?, المبلغ_المدفوع = المبلغ_المدفوع + ?,
                        تاريخ_التحديث = CURRENT_TIMESTAMP,
                        حالة_الدين = CASE
                            WHEN (الرصيد - ?) <= 0.01 THEN 'مسدد'
                            ELSE حالة_الدين
                        END
                    WHERE معرف = ?
                """, (data["amount"], data["amount"], data["amount"], creditor_id))

                notes = f"{data['notes']} - {data['source']}" if data["notes"] else data["source"]
                cursor.execute("""
                    INSERT INTO تحركات_الديون
                    (معرف_الدين, التاريخ, المبلغ, نوع_الحركة, ملاحظات)
                    VALUES (?, ?, ?, 'دفعة', ?)
                """, (creditor_id, data["date"], data["amount"], notes))

                conn.commit()
                self.load_data()
                app_events.emit_data_changed("creditors")
                QMessageBox.information(self, "نجاح", "تم تسجيل الدفعة بنجاح!")

                try:
                    main_window = self.window()
                    if isinstance(main_window, QMainWindow):
                        main_window.show_status(f"تم تسجيل دفعة بقيمة {fmt(data['amount'])} من {name}", "success")
                except Exception:
                    pass

            except Exception as e:
                logger.error(str(e))
                if conn:
                    conn.rollback()
                QMessageBox.critical(self, "خطأ", f"فشل تسجيل الدفعة:\n{str(e)}")
            finally:
                if conn:
                    conn.close()

    def view_history(self):
        current_row = self.searchable_table.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "تنبيه", "الرجاء تحديد دائن من الجدول")
            return

        creditor_id = self.creditor_ids[current_row]
        _, name, _, _, _, _, _ = self.creditors_data[current_row]

        conn = None
        try:
            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT التاريخ, نوع_الحركة, المبلغ, ملاحظات
                FROM تحركات_الديون
                WHERE معرف_الدين = ?
                ORDER BY معرف DESC
            """, (creditor_id,))
            movements = cursor.fetchall()

            related_headers = ["📅 التاريخ", "🔔 النوع", "💰 المبلغ", "📝 ملاحظات"]
            related_rows = []
            for m in movements:
                related_rows.append([m["التاريخ"], m["نوع_الحركة"], m["المبلغ"], m["ملاحظات"]])

            dialog = EntityDetailDialog(
                f"📜 سجل الحركات - {name}",
                detail_data={},
                related_rows=related_rows if related_rows else None,
                related_headers=related_headers if related_rows else None,
                parent=self
            )
            dialog.exec_()
        except Exception as e:
            logger.error(str(e))
            QMessageBox.critical(self, "خطأ", f"فشل تحميل الحركات:\n{str(e)}")
        finally:
            if conn:
                conn.close()


