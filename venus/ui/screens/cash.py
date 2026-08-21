# Path: D:\acc\venus\ui\screens\cash.py
# -*- coding: utf-8 -*-
"""
شاشة النقدية - Venus Coffee
إدارة النقدية اليومية، المصروفات، والسحوبات
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QComboBox, QTabWidget,
    QMessageBox, QDateEdit, QHeaderView, QSplitter, QStyle, QApplication,
    QSizePolicy, QGroupBox, QMainWindow, QFrame
)
from PyQt5.QtCore import Qt, QTimer, QDate, QSize
from PyQt5.QtGui import QDoubleValidator, QColor
from datetime import datetime, timedelta

from venus.core.database import get_conn, now_str
from venus.core.events import app_events
from venus.ui.widgets.loading_overlay import LoadingOverlay
from venus.ui.styles import (
    Colors, FontSizes, Spacing, BorderRadius,
    title_label_style, tab_style, group_box_style, table_style,
    primary_button_style, success_button_style, warning_button_style, danger_button_style,
    input_style, combo_style, date_edit_style, summary_card_style, cash_panel_style, close_panel_style,
    status_bar_style
)
from venus.utils.logger import setup_logger
from venus.utils.currency import fmt, fmt_syp, round_currency
logger = setup_logger()

class CashScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setLayoutDirection(Qt.RightToLeft)
        self.day_opened = False
        self.today_closed = False
        self.init_ui()
        self.refresh_status()

    def init_ui(self):
        main = QVBoxLayout(self)
        main.setSpacing(20)
        main.setContentsMargins(30, 30, 30, 30)

        title = QLabel("💰 إدارة النقدية - Venus Coffee")
        title.setStyleSheet(title_label_style(font_size=FontSizes.XL5, color=Colors.DARK))
        title.setAlignment(Qt.AlignRight)
        main.addWidget(title)

        tabs = QTabWidget()
        tabs.setLayoutDirection(Qt.RightToLeft)
        tabs.setStyleSheet(tab_style())
        main.addWidget(tabs)

        self.cash_tab = QWidget()
        self.expenses_tab = QWidget()
        tabs.addTab(self.cash_tab, "📋 إدارة النقدية")
        tabs.addTab(self.expenses_tab, "📝 المصروفات والسحوبات")

        self.build_cash_tab()
        self.build_expenses_tab()

        self.open_date.dateChanged.connect(self.refresh_status)

        timer = QTimer(self)
        timer.timeout.connect(self.refresh_status)
        timer.start(5000)
        self.refresh_status()

        app_events.data_changed.connect(self._on_app_data_changed)

        self.loading_overlay = LoadingOverlay(self)
        main.addWidget(self.loading_overlay)

    def build_cash_tab(self):
        layout = QVBoxLayout(self.cash_tab)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        open_group = QGroupBox("🗓️ فتح اليومية")
        open_group.setStyleSheet("""
            QGroupBox {
                font-size: 16px;
                font-weight: bold;
                color: #27ae60;
                border: 2px solid #27ae60;
                border-radius: 10px;
                margin-top: 10px;
                padding-top: 15px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                right: 10px;
                padding: 0 10px 0 10px;
            }
        """)
        open_layout = QGridLayout(open_group)
        open_layout.setContentsMargins(20, 20, 20, 20)
        open_layout.setColumnStretch(1, 1)

        open_layout.addWidget(QLabel("📅 التاريخ:"), 0, 0)
        self.open_date = QDateEdit()
        self.open_date.setDate(QDate.currentDate())
        self.open_date.setCalendarPopup(True)
        self.open_date.setStyleSheet(date_edit_style(focus_color=Colors.FOCUS_BLUE))
        open_layout.addWidget(self.open_date, 0, 1)

        open_layout.addWidget(QLabel("💵 رصيد بداية اليوم:"), 1, 0)
        self.opening_edit = QLineEdit()
        self.opening_edit.setValidator(QDoubleValidator(-1, 10000000, 2))
        self.opening_edit.setPlaceholderText("0.00")
        self.opening_edit.setStyleSheet(input_style(focus_color=Colors.FOCUS_BLUE))
        open_layout.addWidget(self.opening_edit, 1, 1)

        open_layout.addWidget(QLabel("💱 العملة:"), 2, 0)
        self.currency_combo = QComboBox()
        self.currency_combo.addItems(["ليرة_سورية", "دولار"])
        self.currency_combo.setStyleSheet(combo_style(focus_color=Colors.FOCUS_BLUE, min_width="180px"))
        open_layout.addWidget(self.currency_combo, 2, 1)

        self.open_btn = QPushButton("فتح اليومية")
        self.open_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_FileIcon))
        self.open_btn.setStyleSheet(success_button_style(hover="#2ecc71"))
        self.open_btn.clicked.connect(self.open_day)
        open_layout.addWidget(self.open_btn, 2, 2)

        layout.addWidget(open_group)

        summary_group = QWidget()
        sgrid = QGridLayout(summary_group)
        sgrid.setContentsMargins(20, 20, 20, 20)
        sgrid.setVerticalSpacing(15)
        sgrid.setHorizontalSpacing(20)

        def make_colored_card(text, color):
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: {color};
                    border-radius: 12px;
                }}
            """)
            vbox = QVBoxLayout(card)
            vbox.setContentsMargins(20, 20, 20, 20)
            vbox.setSpacing(8)

            lbl = QLabel(text)
            lbl.setWordWrap(True)
            lbl.setStyleSheet(f"""
                font-size: {FontSizes.LG};
                font-weight: bold;
                color: white;
                background-color: transparent;
            """)
            lbl.setAlignment(Qt.AlignRight)

            value_lbl = QLabel("-")
            value_lbl.setStyleSheet(f"""
                font-size: {FontSizes.XL2};
                font-weight: bold;
                color: white;
                background-color: transparent;
            """)
            value_lbl.setAlignment(Qt.AlignRight)

            vbox.addWidget(lbl)
            vbox.addWidget(value_lbl)
            return card, value_lbl

        self.lbl_opening, self.val_opening = make_colored_card("💵 رصيد البداية", "#3498db")
        self.lbl_sales, self.val_sales = make_colored_card("🛒 المبيعات", "#27ae60")
        self.lbl_expenses, self.val_expenses = make_colored_card("💸 المصروفات", "#e74c3c")
        self.lbl_withdrawals, self.val_withdrawals = make_colored_card("🏦 السحوبات", "#e67e22")
        self.lbl_theoretical, self.val_theoretical = make_colored_card("📊 الرصيد النظري", "#8e44ad")
        self.lbl_vault, self.val_vault = make_colored_card("🏦 رصيد الخزنة", "#16a085")

        sgrid.addWidget(self.lbl_opening, 0, 0)
        sgrid.addWidget(self.lbl_sales, 0, 1)
        sgrid.addWidget(self.lbl_expenses, 0, 2)
        sgrid.addWidget(self.lbl_withdrawals, 0, 3)
        sgrid.addWidget(self.lbl_theoretical, 1, 0, 1, 3)
        sgrid.addWidget(self.lbl_vault, 1, 3)

        layout.addWidget(summary_group)
        summary_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        close_group = QWidget()
        close_group.setStyleSheet("""
            background-color: #fff9e6;
            border: 2px solid #f39c12;
            border-radius: 10px;
        """)
        cgrid = QGridLayout(close_group)
        cgrid.setContentsMargins(20, 20, 20, 20)
        cgrid.setVerticalSpacing(15)
        cgrid.setHorizontalSpacing(15)

        cgrid.addWidget(QLabel("🔔 المبلغ الفعلي في الدرج:"), 0, 0)
        self.actual_edit = QLineEdit()
        self.actual_edit.setValidator(QDoubleValidator(0, 10000000, 2))
        self.actual_edit.setPlaceholderText("0.00")
        self.actual_edit.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                font-size: 16px;
                border: 2px solid #f39c12;
                border-radius: 8px;
                background-color: white;
                min-height: 45px;
            }
            QLineEdit:focus { border-color: #ff9800; }
            QLineEdit:disabled { background-color: #ecf0f1; color: #7f8c8d; }
        """)
        cgrid.addWidget(self.actual_edit, 0, 1)

        self.close_btn = QPushButton("تسوية وإغلاق")
        self.close_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_TrashIcon))
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #f39c12;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 8px;
                font-size: 15px;
                font-weight: bold;
                min-height: 48px;
            }
            QPushButton:hover { background-color: #d68910; }
            QPushButton:pressed { background-color: #b9770e; }
            QPushButton:disabled { background-color: #95a5a6; }
        """)
        self.close_btn.clicked.connect(self.close_day)
        cgrid.addWidget(self.close_btn, 0, 2)

        self.reopen_btn = QPushButton("إعادة فتح اليومية")
        self.reopen_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_FileIcon))
        self.reopen_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 8px;
                font-size: 15px;
                font-weight: bold;
                min-height: 48px;
            }
            QPushButton:hover { background-color: #229954; }
            QPushButton:pressed { background-color: #1e8449; }
            QPushButton:disabled { background-color: #95a5a6; }
        """)
        self.reopen_btn.clicked.connect(self.reopen_day)
        cgrid.addWidget(self.reopen_btn, 0, 3)

        layout.addWidget(close_group)
        close_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addStretch(1)

    def build_expenses_tab(self):
        layout = QVBoxLayout(self.expenses_tab)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # شريط التاريخ
        date_bar = QHBoxLayout()
        date_bar.setContentsMargins(0, 0, 0, 0)

        date_bar.addWidget(QLabel("📅 عرض حركات تاريخ:"))

        self.mov_date = QDateEdit()
        self.mov_date.setDate(QDate.currentDate())
        self.mov_date.setCalendarPopup(True)
        self.mov_date.setStyleSheet(date_edit_style(
            focus_color=Colors.FOCUS_BLUE
        ))
        self.mov_date.dateChanged.connect(self.load_movements)
        date_bar.addWidget(self.mov_date)
        date_bar.addStretch()
        layout.addLayout(date_bar)

        forms_layout = QHBoxLayout()
        forms_layout.setSpacing(20)

        exp_group = QGroupBox("📝 تسجيل مصروف")
        exp_group.setStyleSheet("""
            QGroupBox {
                font-size: 16px;
                font-weight: bold;
                color: #e74c3c;
                border: 2px solid #e74c3c;
                border-radius: 10px;
                margin-top: 10px;
                padding-top: 15px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                right: 10px;
                padding: 0 10px 0 10px;
            }
        """)
        exp_form = QGridLayout(exp_group)
        exp_form.setContentsMargins(20, 20, 20, 20)
        exp_form.setVerticalSpacing(12)
        exp_form.setHorizontalSpacing(10)

        exp_form.addWidget(QLabel("📅 التاريخ:"), 0, 0)
        self.exp_date = QDateEdit()
        self.exp_date.setDate(QDate.currentDate())
        self.exp_date.setCalendarPopup(True)
        self.exp_date.setStyleSheet(date_edit_style(min_width="130px"))
        exp_form.addWidget(self.exp_date, 0, 1)

        exp_form.addWidget(QLabel("💵 المبلغ:"), 1, 0)
        self.exp_amount = QLineEdit()
        self.exp_amount.setValidator(QDoubleValidator(0, 10000000, 2))
        self.exp_amount.setPlaceholderText("0.00")
        self.exp_amount.setStyleSheet(input_style(focus_color=Colors.FOCUS_RED))
        exp_form.addWidget(self.exp_amount, 1, 1)

        exp_form.addWidget(QLabel("📝 الوصف:"), 2, 0)
        self.exp_desc = QLineEdit()
        self.exp_desc.setPlaceholderText("وصف المصروف...")
        self.exp_desc.setStyleSheet(input_style(focus_color=Colors.FOCUS_RED))
        exp_form.addWidget(self.exp_desc, 2, 1)

        exp_form.addWidget(QLabel("🏷️ النوع:"), 3, 0)
        self.exp_type = QComboBox()
        self.exp_type.addItems(["إيجار", "رواتب", "كهرباء", "ماء", "نقل", "أخرى"])
        self.exp_type.setStyleSheet(combo_style(focus_color=Colors.FOCUS_RED, min_width="130px"))
        exp_form.addWidget(self.exp_type, 3, 1)

        save_exp = QPushButton("حفظ المصروف")
        save_exp.setIcon(QApplication.style().standardIcon(QStyle.SP_DialogSaveButton))
        save_exp.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
                min-height: 44px;
            }
            QPushButton:hover { background-color: #c0392b; }
            QPushButton:pressed { background-color: #a93226; }
            QPushButton:disabled { background-color: #95a5a6; }
        """)
        save_exp.clicked.connect(self.save_expense)
        exp_form.addWidget(save_exp, 4, 0, 1, 2)

        splitter = QSplitter(Qt.Horizontal)

        w_group = QGroupBox("💸 تسجيل سحب")
        w_group.setStyleSheet("""
            QGroupBox {
                font-size: 16px;
                font-weight: bold;
                color: #e67e22;
                border: 2px solid #e67e22;
                border-radius: 10px;
                margin-top: 10px;
                padding-top: 15px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                right: 10px;
                padding: 0 10px 0 10px;
            }
        """)
        w_form = QGridLayout(w_group)
        w_form.setContentsMargins(20, 20, 20, 20)
        w_form.setVerticalSpacing(12)
        w_form.setHorizontalSpacing(10)

        w_form.addWidget(QLabel("📅 التاريخ:"), 0, 0)
        self.wd_date = QDateEdit()
        self.wd_date.setDate(QDate.currentDate())
        self.wd_date.setCalendarPopup(True)
        self.wd_date.setStyleSheet(date_edit_style(min_width="130px"))
        w_form.addWidget(self.wd_date, 0, 1)

        w_form.addWidget(QLabel("💵 المبلغ:"), 1, 0)
        self.wd_amount = QLineEdit()
        self.wd_amount.setValidator(QDoubleValidator(0, 10000000, 2))
        self.wd_amount.setPlaceholderText("0.00")
        self.wd_amount.setStyleSheet(input_style(focus_color=Colors.FOCUS_ORANGE))
        w_form.addWidget(self.wd_amount, 1, 1)

        w_form.addWidget(QLabel("📝 الوصف:"), 2, 0)
        self.wd_desc = QLineEdit()
        self.wd_desc.setPlaceholderText("وصف السحب...")
        self.wd_desc.setStyleSheet(input_style(focus_color=Colors.FOCUS_ORANGE))
        w_form.addWidget(self.wd_desc, 2, 1)

        save_wd = QPushButton("حفظ السحب")
        save_wd.setIcon(QApplication.style().standardIcon(QStyle.SP_DialogSaveButton))
        save_wd.setStyleSheet("""
            QPushButton {
                background-color: #e67e22;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
                min-height: 44px;
            }
            QPushButton:hover { background-color: #d35400; }
            QPushButton:pressed { background-color: #a04000; }
            QPushButton:disabled { background-color: #95a5a6; }
        """)
        save_wd.clicked.connect(self.save_withdrawal)
        w_form.addWidget(save_wd, 3, 0, 1, 2)

        splitter.addWidget(exp_group)
        splitter.addWidget(w_group)
        splitter.setSizes([400, 400])
        layout.addWidget(splitter)

        undo_layout = QHBoxLayout()
        undo_layout.setContentsMargins(0, 0, 0, 0)

        undo_exp_btn = QPushButton("↩️ تراجع عن آخر مصروف")
        undo_exp_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_ArrowBack))
        undo_exp_btn.setIconSize(QSize(16, 16))
        undo_exp_btn.setMaximumHeight(32)
        undo_exp_btn.setCursor(Qt.PointingHandCursor)
        undo_exp_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 13px;
                font-weight: bold;
                padding: 6px 12px;
            }
            QPushButton:hover { background-color: #c0392b; }
        """)
        undo_exp_btn.clicked.connect(self.undo_last_expense)

        undo_wd_btn = QPushButton("↩️ تراجع عن آخر سحب")
        undo_wd_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_ArrowBack))
        undo_wd_btn.setIconSize(QSize(16, 16))
        undo_wd_btn.setMaximumHeight(32)
        undo_wd_btn.setCursor(Qt.PointingHandCursor)
        undo_wd_btn.setStyleSheet("""
            QPushButton {
                background-color: #e67e22;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 13px;
                font-weight: bold;
                padding: 6px 12px;
            }
            QPushButton:hover { background-color: #d35400; }
        """)
        undo_wd_btn.clicked.connect(self.undo_last_withdrawal)

        undo_layout.addWidget(undo_exp_btn)
        undo_layout.addWidget(undo_wd_btn)
        undo_layout.addStretch()
        layout.addLayout(undo_layout)

        layout.addWidget(QLabel("📜 آخر 20 حركة (مصروفات وسحوبات):"))
        self.mov_table = QTableWidget(0, 5)
        self.mov_table.setHorizontalHeaderLabels(["التاريخ", "النوع", "المبلغ", "الوصف", "تفاصيل"])
        self.mov_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.mov_table.horizontalHeader().setLayoutDirection(Qt.RightToLeft)
        self.mov_table.setMinimumHeight(220)
        self.mov_table.verticalHeader().setVisible(False)
        self.mov_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.mov_table.setStyleSheet(table_style(Colors.PRIMARY))
        self.mov_table.setAlternatingRowColors(True)
        layout.addWidget(self.mov_table, stretch=1)

    def refresh_status(self):
        conn = get_conn()
        cur = conn.cursor()
        try:
            selected_date = self.open_date.date().toString("yyyy-MM-dd")
            selected_date = selected_date.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
            next_date = (datetime.strptime(selected_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
            cur.execute("SELECT * FROM أرصدة_الصندوق WHERE التاريخ >= ? AND التاريخ < ?", (selected_date, next_date))
            row = cur.fetchone()
            if row:
                self.day_opened = True
                self.today_closed = bool(row["مغلقة"])
            else:
                self.day_opened = False
                self.today_closed = False
        except Exception:
            self.day_opened = False
            self.today_closed = False
        finally:
            conn.close()

        if self.day_opened and not self.today_closed:
            self.open_btn.setEnabled(False)
            self.opening_edit.setEnabled(False)
            self.currency_combo.setEnabled(False)
            self.close_btn.setEnabled(True)
            self.reopen_btn.setEnabled(False)
            self.actual_edit.setEnabled(True)
        elif self.today_closed:
            self.open_btn.setEnabled(False)
            self.opening_edit.setEnabled(False)
            self.currency_combo.setEnabled(False)
            self.close_btn.setEnabled(False)
            self.reopen_btn.setEnabled(True)
            self.actual_edit.setEnabled(False)
        else:
            self.open_btn.setEnabled(True)
            self.opening_edit.setEnabled(True)
            self.currency_combo.setEnabled(True)
            self.close_btn.setEnabled(False)
            self.reopen_btn.setEnabled(False)
            self.actual_edit.setEnabled(False)
            if not self.opening_edit.text().strip():
                conn2 = None
                try:
                    conn2 = get_conn()
                    cur2 = conn2.cursor()
                    cur2.execute("SELECT رصيد_نهاية_فعلي, العملة FROM أرصدة_الصندوق WHERE التاريخ < ? ORDER BY التاريخ DESC LIMIT 1",
                                (selected_date,))
                    prev = cur2.fetchone()
                    if prev and prev["رصيد_نهاية_فعلي"]:
                        self.opening_edit.setText(f"{fmt(prev['رصيد_نهاية_فعلي'])}")
                        if prev["العملة"]:
                            idx = self.currency_combo.findText(prev["العملة"])
                            if idx >= 0:
                                self.currency_combo.setCurrentIndex(idx)
                    else:
                        conn3 = None
                        try:
                            conn3 = get_conn()
                            cur3 = conn3.cursor()
                            cur3.execute("SELECT القيمة FROM الإعدادات WHERE المفتاح = 'رصيد_النقدية_الافتتاحي'")
                            setting_row = cur3.fetchone()
                            opening_balance = float(setting_row[0]) if setting_row and setting_row[0] else 0.0
                        except Exception:
                            opening_balance = 0.0
                        finally:
                            if conn3:
                                conn3.close()
                        self.opening_edit.setText(f"{fmt(opening_balance)}")
                except Exception:
                    pass
                finally:
                    if conn2:
                        conn2.close()

        self.update_summary()
        self.load_movements()

    def _on_app_data_changed(self, entity_name):
        if entity_name in {"sales", "expenses", "withdrawals", "cash"}:
            self.refresh_status()

    def get_unregistered_group_id(self, cursor=None):
        if cursor is not None:
            cur = cursor
            conn = cursor.connection
            owns_conn = False
        else:
            conn = get_conn()
            cur = conn.cursor()
            owns_conn = True
        try:
            cur.execute("SELECT معرف FROM المجموعات WHERE الاسم = ?", ("مبيعات غير مسجلة",))
            row = cur.fetchone()
            if row:
                return row["معرف"]
            cur.execute("SELECT COALESCE(MAX(الترتيب), 0) FROM المجموعات")
            next_order = cur.fetchone()[0] + 1
            cur.execute("INSERT INTO المجموعات (الاسم, الوصف, تاريخ_الإنشاء, الترتيب) VALUES (?, ?, ?, ?)",
                        ("مبيعات غير مسجلة", "مجموعة خاصة للمبيعات غير المسجلة في التسوية", now_str(), next_order))
            if owns_conn:
                conn.commit()
            return cur.lastrowid
        except Exception as e:
            logger.error(str(e))
            if owns_conn:
                conn.rollback()
            QMessageBox.critical(self, "خطأ", str(e))
        finally:
            if owns_conn:
                conn.close()
            self.loading_overlay.stop()

    def get_vault_opening_balance(self):
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute("SELECT القيمة FROM الإعدادات WHERE المفتاح = 'رصيد_الخزنة_الافتتاحي'")
            row = cur.fetchone()
            if row and row["القيمة"]:
                return float(row["القيمة"])
            cur.execute("""
                INSERT INTO الإعدادات (المفتاح, القيمة, الوصف)
                VALUES ('رصيد_الخزنة_الافتتاحي', '0', 'رصيد الخزنة الافتتاحي')
            """)
            conn.commit()
            return 0.0
        except Exception as e:
            logger.error(f"Failed to get vault opening balance: {e}")
            return 0.0
        finally:
            conn.close()

    def get_float_amount(self):
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute("SELECT القيمة FROM الإعدادات WHERE المفتاح = 'مبلغ_الفكة'")
            row = cur.fetchone()
            return float(row["القيمة"]) if row else 65000.0
        except Exception:
            return 65000.0
        finally:
            conn.close()

    def get_vault_balance(self):
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute("SELECT الرصيد_بعد_الحركة FROM الخزنة ORDER BY معرف DESC LIMIT 1")
            row = cur.fetchone()
            return float(row["الرصيد_بعد_الحركة"]) if row else 0.0
        except Exception:
            return 0.0
        finally:
            conn.close()

    def record_vault_deposit(self, amount, description, notes=""):
        conn = get_conn()
        cur = conn.cursor()
        try:
            vault_balance = self.get_vault_balance()
            new_balance = vault_balance + amount
            cur.execute("""
                INSERT INTO الخزنة (التاريخ, البيان, إيداع, الرصيد_بعد_الحركة, ملاحظات)
                VALUES (?, ?, ?, ?, ?)
            """, (now_str(), description, amount, new_balance, notes))
            conn.commit()
            return new_balance
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to record vault deposit: {e}")
            return None
        finally:
            conn.close()

    def record_vault_withdrawal(self, amount, description, notes=""):
        conn = get_conn()
        cur = conn.cursor()
        try:
            vault_balance = self.get_vault_balance()
            if vault_balance < amount:
                return None
            new_balance = vault_balance - amount
            cur.execute("""
                INSERT INTO الخزنة (التاريخ, البيان, سحب, الرصيد_بعد_الحركة, ملاحظات)
                VALUES (?, ?, ?, ?, ?)
            """, (now_str(), description, amount, new_balance, notes))
            conn.commit()
            return new_balance
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to record vault withdrawal: {e}")
            return None
        finally:
            conn.close()

    def open_day(self):
        txt = self.opening_edit.text().strip()
        if not txt:
            QMessageBox.warning(self, "خطأ", "الرجاء إدخال رصيد بداية اليوم")
            return
        try:
            amt = round(float(txt))
        except ValueError:
            QMessageBox.warning(self, "خطأ", "قيمة غير صالحة")
            return
        if amt < 0:
            QMessageBox.warning(self, "خطأ", "القيمة غير صالحة")
            return

        self.loading_overlay.start()
        QApplication.processEvents()
        currency = self.currency_combo.currentText()
        date_str = self.open_date.date().toString("yyyy-MM-dd")
        date_str = date_str.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))

        conn = None
        try:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("SELECT * FROM أرصدة_الصندوق WHERE التاريخ = ?", (date_str,))
            if cur.fetchone():
                QMessageBox.information(self, "معلومة", "اليومية مفتوحة بالفعل لهذا التاريخ")
                conn.rollback()
                self.loading_overlay.stop()
                return

            float_amount = self.get_float_amount()
            vault_balance = self.get_vault_balance()
            if vault_balance < float_amount:
                reply = QMessageBox.question(
                    self, "تنبيه - رصيد الخزنة",
                    f"رصيد الخزنة ({fmt(vault_balance)}) أقل من مبلغ الفكة ({fmt(float_amount)}).\n"
                    f"سيصبح رصيد الخزنة سالباً.\n\n"
                    "هل تريد المتابعة؟",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    conn.rollback()
                    self.loading_overlay.stop()
                    return

            now = date_str + ' ' + datetime.now().strftime('%H:%M:%S')
            if float_amount > 0:
                cur.execute("""
                    INSERT INTO تحويلات_الصندوق (التاريخ, من_حساب, إلى_حساب, المبلغ, ملاحظات)
                        VALUES (?, 'الخزنة', 'الدرج', ?, ?)
                    """, (now, float_amount, f"فتح يومية - سحب فكة ({fmt(float_amount)} ليرة)"))

                cur.execute("""
                        INSERT INTO الخزنة (التاريخ, البيان, سحب, الرصيد_بعد_الحركة, ملاحظات)
                        VALUES (?, ?, ?, ?, ?)
                    """, (now, "سحب فكة - فتح يومية", float_amount, vault_balance - float_amount, "تحويل للدرج"))
    
            cur.execute("""
                INSERT INTO أرصدة_الصندوق (التاريخ, رصيد_بداية_اليوم, العملة, رصيد_الخزنة)
                VALUES (?, ?, ?, ?)
            """, (date_str, amt, currency, vault_balance - float_amount))

            conn.commit()
            self.opening_edit.clear()
            self.refresh_status()
            app_events.emit_data_changed("cash")
            QMessageBox.information(self, "تم", "تم فتح اليومية بنجاح")
        except Exception as e:
            logger.error(str(e))
            conn.rollback()
            QMessageBox.critical(self, "خطأ", str(e))
        finally:
            if conn:
                conn.close()

    def close_day(self):
        txt = self.actual_edit.text().strip()
        if not txt:
            QMessageBox.warning(self, "خطأ", "الرجاء إدخال المبلغ الفعلي في الدرج")
            return
        try:
            actual = round(float(txt))
        except ValueError:
            QMessageBox.warning(self, "خطأ", "قيمة غير صالحة")
            return
        if actual < 0:
            QMessageBox.warning(self, "خطأ", "القيمة غير صالحة")
            return

        self.loading_overlay.start()
        QApplication.processEvents()
        selected_date = self.open_date.date().toString("yyyy-MM-dd")
        selected_date = selected_date.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))

        conn = None
        try:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("BEGIN TRANSACTION")
            next_date = (datetime.strptime(selected_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
            cur.execute("SELECT * FROM أرصدة_الصندوق WHERE التاريخ >= ? AND التاريخ < ?", (selected_date, next_date))
            row = cur.fetchone()
            if not row:
                QMessageBox.warning(self, "خطأ", "لا توجد يومية مفتوحة لهذا التاريخ")
                conn.rollback()
                return

            opening = row["رصيد_بداية_اليوم"] or 0
            cash_currency = row["العملة"] or "ليرة_سورية"
            vault_balance = self.get_vault_balance()

            cur.execute("""
                SELECT SUM(المبلغ_الإجمالي) FROM المبيعات_اليومية WHERE التاريخ >= ? AND التاريخ < ?
            """, (selected_date, next_date))
            sales = cur.fetchone()[0] or 0

            cur.execute("""
                SELECT 0
            """)
            expenses = cur.fetchone()[0] or 0

            cur.execute("""
                SELECT 0
            """)
            withdrawals = cur.fetchone()[0] or 0

            theoretical = opening + sales - expenses - withdrawals
            base_theoretical = theoretical
            diff = actual - base_theoretical

            now = selected_date + ' ' + datetime.now().strftime('%H:%M:%S')

            if actual > 0:
                cur.execute("""
                    INSERT INTO تحويلات_الصندوق (التاريخ, من_حساب, إلى_حساب, المبلغ, ملاحظات)
                    VALUES (?, 'الدرج', 'الخزنة', ?, ?)
                """, (now, actual, "إغلاق يومية - تحويل كامل الدرج للخزنة"))

            cur.execute("""
                INSERT INTO الخزنة (التاريخ, البيان, إيداع, الرصيد_بعد_الحركة, ملاحظات)
                VALUES (?, ?, ?, ?, ?)
            """, (now, "إيداع إغلاق يومية", actual, vault_balance + actual, "تحويل من الدرج"))

            final_vault_balance = vault_balance + actual

            cur.execute("""
                UPDATE أرصدة_الصندوق
                SET رصيد_نهاية_نظري = ?,
                    رصيد_نهاية_فعلي = ?,
                    فرق_التسوية = ?,
                    رصيد_الخزنة = ?,
                    مبيعات_اليوم = ?,
                    مصروفات_اليوم = ?,
                    سحوبات_اليوم = ?,
                    مغلقة = 1
                WHERE التاريخ = ?
            """, (base_theoretical, actual, diff, final_vault_balance, sales, expenses, withdrawals, selected_date))

            if diff > 0.01:
                group_id = self.get_unregistered_group_id(cur)
                if group_id:
                    cur.execute("""
                        INSERT INTO المبيعات_اليومية (التاريخ, معرف_المجموعة, المبلغ_الإجمالي, العملة, ملاحظات)
                        VALUES (?, ?, ?, ?, 'مبيعات غير مسجلة - تسوية')
                    """, (selected_date, group_id, diff, cash_currency))
                    cur.execute("""
                        UPDATE أرصدة_الصندوق SET مبيعات_غير_مسجلة = ? WHERE التاريخ = ?
                    """, (diff, selected_date))
                    conn.commit()
                    QMessageBox.information(self, "فرق إيجابي",
                        f"يوجد فائض بقيمة {fmt(diff)} {cash_currency}\nتم تسجيله كـ 'مبيعات غير مسجلة'")

                    try:
                        main_window = self.window()
                        if isinstance(main_window, QMainWindow):
                            main_window.show_status(f"تم الإغلاق بفائض قدره {fmt(diff)}", "success")
                    except Exception:
                        pass
                else:
                    conn.rollback()
                    QMessageBox.critical(self, "خطأ", "فشل في إنشاء مجموعة المبيعات غير المسجلة")
                    return
            elif diff < -0.01:
                conn.commit()
                QMessageBox.warning(self, "عجز",
                    f"يوجد عجز بقيمة {fmt(abs(diff))} {cash_currency}\nيفضل تسجيل مصروف إضافي")

                try:
                    main_window = self.window()
                    if isinstance(main_window, QMainWindow):
                        main_window.show_status(f"تم الإغلاق بعجز قدره {fmt(abs(diff))}", "warning")
                except Exception:
                    pass
            else:
                conn.commit()
                QMessageBox.information(self, "تم", "تمت التسوية بنجاح بدون فرق")

            self.actual_edit.clear()
            self.refresh_status()
            app_events.emit_data_changed("cash")
        except Exception as e:
            logger.error(str(e))
            conn.rollback()
            QMessageBox.critical(self, "خطأ", str(e))
        finally:
            if conn:
                conn.close()
            self.loading_overlay.stop()

    def reopen_day(self):
        selected_date = self.open_date.date().toString("yyyy-MM-dd")
        selected_date = selected_date.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))

        reply = QMessageBox.question(
            self,
            "تأكيد إعادة الفتح",
            f"هل أنت متأكد من إعادة فتح اليومية لتاريخ {selected_date}؟\nسيتم مسح بيانات التسوية القديمة.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.No:
            return

        self.loading_overlay.start()
        QApplication.processEvents()
        conn = None
        try:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("BEGIN TRANSACTION")
            
            cur.execute("SELECT * FROM أرصدة_الصندوق WHERE التاريخ = ?", (selected_date,))
            row = cur.fetchone()
            if not row:
                QMessageBox.warning(self, "خطأ", "لا توجد يومية مفتوحة لهذا التاريخ")
                conn.rollback()
                return
            
            cur.execute("""
                DELETE FROM تحويلات_الصندوق
                WHERE معرف = (
                    SELECT معرف FROM تحويلات_الصندوق
                    WHERE date(التاريخ) = ? AND من_حساب = 'الدرج' AND إلى_حساب = 'الخزنة'
                    AND ملاحظات = 'إغلاق يومية - تحويل كامل الدرج للخزنة'
                    ORDER BY معرف DESC LIMIT 1
                )
            """, (selected_date,))
            
            cur.execute("""
                SELECT معرف, إيداع, سحب FROM الخزنة
                WHERE date(التاريخ) = ? AND البيان = 'إيداع إغلاق يومية'
                ORDER BY معرف DESC LIMIT 1
            """, (selected_date,))
            deposit_row = cur.fetchone()
            if deposit_row:
                v_id, v_deposit, v_withdraw = deposit_row
                v_delta = (v_deposit or 0) - (v_withdraw or 0)
                cur.execute("DELETE FROM الخزنة WHERE معرف = ?", (v_id,))
                if v_delta != 0:
                    cur.execute("""
                        UPDATE الخزنة SET الرصيد_بعد_الحركة = الرصيد_بعد_الحركة - ?
                        WHERE معرف > ?
                    """, (v_delta, v_id))
            
            cur.execute("""
                DELETE FROM المبيعات_اليومية
                WHERE معرف = (
                    SELECT معرف FROM المبيعات_اليومية
                    WHERE التاريخ = ? AND ملاحظات LIKE 'مبيعات غير مسجلة%'
                    ORDER BY معرف DESC LIMIT 1
                )
            """, (selected_date,))
            
            cur.execute("SELECT الرصيد_بعد_الحركة FROM الخزنة ORDER BY معرف DESC LIMIT 1")
            new_vault_balance = cur.fetchone()[0] or 0
            
            cur.execute("""
                UPDATE أرصدة_الصندوق
                SET رصيد_نهاية_نظري = 0, رصيد_نهاية_فعلي = 0, فرق_التسوية = 0, مبيعات_غير_مسجلة = 0, رصيد_الخزنة = ?, مغلقة = 0
                WHERE التاريخ = ?
            """, (new_vault_balance, selected_date))
            
            conn.commit()
            self.refresh_status()
            app_events.emit_data_changed("cash")
            QMessageBox.information(self, "تم", "تم إعادة فتح اليومية بنجاح\nيمكنك الآن تعديل البيانات")
        except Exception as e:
            logger.error(str(e))
            conn.rollback()
            QMessageBox.critical(self, "خطأ", str(e))
        finally:
            if conn:
                conn.close()
            self.loading_overlay.stop()

    def update_summary(self):
        conn = get_conn()
        cur = conn.cursor()
        try:
            selected_date = self.open_date.date().toString("yyyy-MM-dd")
            selected_date = selected_date.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
            next_date = (datetime.strptime(selected_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
            cur.execute("SELECT * FROM أرصدة_الصندوق WHERE التاريخ >= ? AND التاريخ < ?", (selected_date, next_date))
            row = cur.fetchone()
            if row:
                opening = row["رصيد_بداية_اليوم"] or 0
                cash_currency = row["العملة"] or "ليرة_سورية"
                vault_balance = self.get_vault_balance()
            else:
                cur.execute("SELECT رصيد_نهاية_فعلي, العملة FROM أرصدة_الصندوق WHERE التاريخ < ? ORDER BY التاريخ DESC LIMIT 1",
                            (selected_date,))
                prev = cur.fetchone()
                opening = prev["رصيد_نهاية_فعلي"] if prev and prev["رصيد_نهاية_فعلي"] else 0
                cash_currency = prev["العملة"] if prev and prev["العملة"] else "ليرة_سورية"
                vault_balance = self.get_vault_balance()

            cur.execute("""
                SELECT SUM(المبلغ_الإجمالي) FROM المبيعات_اليومية WHERE التاريخ >= ? AND التاريخ < ?
            """, (selected_date, next_date))
            sales = cur.fetchone()[0] or 0

            cur.execute("""
                SELECT COALESCE(SUM(المبلغ), 0)
                FROM المصروفات
                WHERE التاريخ >= ? AND التاريخ < ?
            """, (selected_date, next_date))
            expenses = cur.fetchone()[0] or 0

            cur.execute("""
                SELECT COALESCE(SUM(المبلغ), 0)
                FROM السحوبات
                WHERE التاريخ >= ? AND التاريخ < ?
            """, (selected_date, next_date))
            withdrawals = cur.fetchone()[0] or 0

            if row:
                theoretical = opening + sales
            else:
                theoretical = opening + sales

            self.val_opening.setText(f"{fmt(opening)} {cash_currency}")
            self.val_sales.setText(f"{fmt(sales)}")
            self.val_expenses.setText(f"{fmt(expenses)} {cash_currency}")
            self.val_withdrawals.setText(f"{fmt(withdrawals)} {cash_currency}")
            self.val_theoretical.setText(f"{fmt(theoretical)} {cash_currency}")
            self.val_vault.setText(f"{fmt(vault_balance)} {cash_currency}")
        except Exception as e:
            logger.error(f"فشل تحديث الملخص: {type(e).__name__}")
        finally:
            conn.close()

    def load_movements(self):
        conn = get_conn()
        cur = conn.cursor()
        try:
            # استخدم mov_date إذا كان موجوداً وإلا open_date
            date_widget = getattr(self, 'mov_date', self.open_date)
            selected_date = date_widget.date().toString("yyyy-MM-dd")
            selected_date = selected_date.translate(
                str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
            )
            next_date = (datetime.strptime(selected_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
            cur.execute("""
                SELECT التاريخ, 'مصروف' as النوع, المبلغ, الوصف,
                       نوع_المصروف as التفاصيل, العملة
                FROM المصروفات
                WHERE التاريخ >= ? AND التاريخ < ?
                UNION ALL
                SELECT التاريخ, 'سحب' as النوع, المبلغ, الوصف,
                       '' as التفاصيل, العملة
                FROM السحوبات
                WHERE التاريخ >= ? AND التاريخ < ?
                ORDER BY التاريخ DESC
                LIMIT 20
            """, (selected_date, next_date, selected_date, next_date))
            rows = cur.fetchall()
            self.mov_table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                self.mov_table.setItem(r, 0, QTableWidgetItem(str(row["التاريخ"] or "")))
                type_item = QTableWidgetItem(str(row["النوع"] or ""))
                if row["النوع"] == "مصروف":
                    type_item.setForeground(Qt.red)
                else:
                    type_item.setForeground(Qt.darkMagenta)
                self.mov_table.setItem(r, 1, type_item)
                amount_item = QTableWidgetItem(f"{fmt(row['المبلغ'] or 0)} ({row['العملة'] or ''})")
                if row["النوع"] == "مصروف":
                    amount_item.setForeground(QColor("#e74c3c"))
                else:
                    amount_item.setForeground(QColor("#e67e22"))
                self.mov_table.setItem(r, 2, amount_item)
                self.mov_table.setItem(r, 3, QTableWidgetItem(str(row["الوصف"] or "")))
                detail = str(row["التفاصيل"] or "")
                if row["النوع"] == "مصروف":
                    detail = f"{detail} - {row['الوصف'] or ''}"
                self.mov_table.setItem(r, 4, QTableWidgetItem(detail))
        except Exception as e:
            logger.error(f"فشل تحميل الحركات: {type(e).__name__}")
        finally:
            conn.close()

    def save_expense(self):
        date_str = self.exp_date.date().toString("yyyy-MM-dd")
        date_str = date_str.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
        amt_txt = self.exp_amount.text().strip()
        desc = self.exp_desc.text().strip()
        exp_type = self.exp_type.currentText()

        if not amt_txt:
            QMessageBox.warning(self, "خطأ", "الرجاء إدخال المبلغ")
            return
        try:
            amt = float(amt_txt)
        except ValueError:
            QMessageBox.warning(self, "خطأ", "قيمة غير صالحة")
            return
        if amt <= 0:
            QMessageBox.warning(self, "خطأ", "المبلغ يجب أن يكون أكبر من صفر")
            return

        self.loading_overlay.start()
        QApplication.processEvents()
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute("BEGIN TRANSACTION")
            next_date = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
            cur.execute("SELECT مغلقة FROM أرصدة_الصندوق WHERE التاريخ >= ? AND التاريخ < ?", (date_str, next_date))
            day_row = cur.fetchone()
            if day_row and day_row[0]:
                conn.rollback()
                QMessageBox.warning(self, "خطأ", "لا يمكن تسجيل مصروف في يومية مُغلقة. يرجى إعادة فتح اليومية أولًا من شاشة النقدية.")
                return

            currency_row = cur.execute("SELECT العملة FROM أرصدة_الصندوق WHERE التاريخ >= ? AND التاريخ < ?", (date_str, next_date)).fetchone()
            currency = currency_row["العملة"] if currency_row else "ليرة_سورية"

            dt = f"{date_str} {datetime.now().strftime('%H:%M:%S')}"
            cur.execute("""
                INSERT INTO المصروفات (التاريخ, المبلغ, الوصف, نوع_المصروف, العملة, ملاحظات)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (dt, amt, desc, exp_type, currency, f"مصروف - {exp_type}"))
            expense_id = cur.lastrowid

            cur.execute("""
                SELECT COALESCE(الرصيد_بعد_الحركة, 0)
                FROM الخزنة ORDER BY معرف DESC LIMIT 1
            """)
            vault_row = cur.fetchone()
            vault_balance = float(vault_row[0]) if vault_row else 0.0

            new_vault = vault_balance - amt
            if new_vault < 0:
                reply = QMessageBox.question(
                    self, "تنبيه - رصيد الخزنة",
                    f"رصيد الخزنة ({fmt(vault_balance)}) أقل من المصروف ({fmt(amt)}).\n"
                    f"سيصبح رصيد الخزنة: {fmt(new_vault)} ل.س\n\n"
                    "هل تريد المتابعة؟",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    conn.rollback()
                    return

            cur.execute("""
                INSERT INTO الخزنة
                (التاريخ, البيان, سحب, الرصيد_بعد_الحركة, ملاحظات)
                VALUES (?, ?, ?, ?, ?)
            """, (dt, f"مصروف - {desc}", amt, new_vault,
                  f"مصروف {exp_type}"))

            cur.execute("""
                INSERT INTO سجل_العمليات_الأخيرة (نوع_العملية, معرف_السجل, التاريخ_المتأثر)
                VALUES (?, ?, ?)
            """, ('مصروف', expense_id, date_str))

            cur.execute("SELECT * FROM أرصدة_الصندوق WHERE التاريخ >= ? AND التاريخ < ?", (date_str, next_date))
            row = cur.fetchone()
            if row:
                cur.execute("""
                    UPDATE أرصدة_الصندوق SET مصروفات_اليوم = مصروفات_اليوم + ?
                    WHERE التاريخ >= ? AND التاريخ < ?
                """, (amt, date_str, next_date))

            conn.commit()
            self.exp_amount.clear()
            self.exp_desc.clear()
            self.refresh_status()
            app_events.emit_data_changed("expenses")
            app_events.emit_data_changed("cash")
            QMessageBox.information(self, "تم", "تم حفظ المصروف بنجاح")

            try:
                main_window = self.window()
                if isinstance(main_window, QMainWindow):
                    main_window.show_status("تم حفظ المصروف بنجاح", "success")
            except Exception:
                pass
        except Exception as e:
            logger.error(str(e))
            conn.rollback()
            QMessageBox.critical(self, "خطأ", str(e))
        finally:
            conn.close()
            self.loading_overlay.stop()

    def save_withdrawal(self):
        date_str = self.wd_date.date().toString("yyyy-MM-dd")
        date_str = date_str.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
        amt_txt = self.wd_amount.text().strip()
        desc = self.wd_desc.text().strip()

        if not amt_txt:
            QMessageBox.warning(self, "خطأ", "الرجاء إدخال المبلغ")
            return
        try:
            amt = float(amt_txt)
        except ValueError:
            QMessageBox.warning(self, "خطأ", "قيمة غير صالحة")
            return
        if amt <= 0:
            QMessageBox.warning(self, "خطأ", "المبلغ يجب أن يكون أكبر من صفر")
            return

        self.loading_overlay.start()
        QApplication.processEvents()
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute("BEGIN TRANSACTION")
            next_date = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
            cur.execute("SELECT مغلقة FROM أرصدة_الصندوق WHERE التاريخ >= ? AND التاريخ < ?", (date_str, next_date))
            day_row = cur.fetchone()
            if day_row and day_row[0]:
                conn.rollback()
                QMessageBox.warning(self, "خطأ", "لا يمكن تسجيل سحب في يومية مُغلقة. يرجى إعادة فتح اليومية أولًا من شاشة النقدية.")
                return

            currency_row = cur.execute("SELECT العملة FROM أرصدة_الصندوق WHERE التاريخ >= ? AND التاريخ < ?", (date_str, next_date)).fetchone()
            currency = currency_row["العملة"] if currency_row else "ليرة_سورية"

            dt = f"{date_str} {datetime.now().strftime('%H:%M:%S')}"
            cur.execute("""
                INSERT INTO السحوبات (التاريخ, المبلغ, الوصف, العملة, ملاحظات)
                VALUES (?, ?, ?, ?, ?)
            """, (dt, amt, desc, currency, f"سحب - {desc}"))
            withdrawal_id = cur.lastrowid

            cur.execute("""
                SELECT COALESCE(الرصيد_بعد_الحركة, 0)
                FROM الخزنة ORDER BY معرف DESC LIMIT 1
            """)
            vault_row = cur.fetchone()
            vault_balance = float(vault_row[0]) if vault_row else 0.0

            new_vault = vault_balance - amt
            if new_vault < 0:
                reply = QMessageBox.question(
                    self, "تنبيه - رصيد الخزنة",
                    f"رصيد الخزنة ({fmt(vault_balance)}) أقل من السحب ({fmt(amt)}).\n"
                    f"سيصبح رصيد الخزنة: {fmt(new_vault)} ل.س\n\n"
                    "هل تريد المتابعة؟",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    conn.rollback()
                    return

            cur.execute("""
                INSERT INTO الخزنة
                (التاريخ, البيان, سحب, الرصيد_بعد_الحركة, ملاحظات)
                VALUES (?, ?, ?, ?, ?)
            """, (dt, f"سحب - {desc}", amt, new_vault,
                  "سحب من الخزنة"))

            cur.execute("""
                INSERT INTO سجل_العمليات_الأخيرة (نوع_العملية, معرف_السجل, التاريخ_المتأثر)
                VALUES (?, ?, ?)
            """, ('سحب', withdrawal_id, date_str))

            cur.execute("SELECT * FROM أرصدة_الصندوق WHERE التاريخ >= ? AND التاريخ < ?", (date_str, next_date))
            row = cur.fetchone()
            if row:
                cur.execute("""
                    UPDATE أرصدة_الصندوق SET سحوبات_اليوم = سحوبات_اليوم + ?
                    WHERE التاريخ >= ? AND التاريخ < ?
                """, (amt, date_str, next_date))

            conn.commit()
            self.wd_amount.clear()
            self.wd_desc.clear()
            self.refresh_status()
            app_events.emit_data_changed("withdrawals")
            app_events.emit_data_changed("cash")
            QMessageBox.information(self, "تم", "تم حفظ السحب بنجاح")

            try:
                main_window = self.window()
                if isinstance(main_window, QMainWindow):
                    main_window.show_status("تم حفظ السحب بنجاح", "success")
            except Exception:
                pass
        except Exception as e:
            logger.error(str(e))
            conn.rollback()
            QMessageBox.critical(self, "خطأ", str(e))
        finally:
            conn.close()
            self.loading_overlay.stop()

    def _undo_operation(self, operation_type, table_name, balance_column, record_id_col="معرف"):
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT معرف, معرف_السجل, التاريخ_المتأثر FROM سجل_العمليات_الأخيرة
                WHERE نوع_العملية = ? AND تم_التراجع = 0
                ORDER BY وقت_التسجيل DESC LIMIT 1
            """, (operation_type,))
            row = cur.fetchone()
            if not row:
                QMessageBox.information(self, "معلومة", "لا توجد عملية حديثة للتراجع عنها")
                return

            log_id, record_id, affected_date = row

            next_date = (datetime.strptime(affected_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
            cur.execute("SELECT مغلقة FROM أرصدة_الصندوق WHERE التاريخ >= ? AND التاريخ < ?", (affected_date, next_date))
            day_row = cur.fetchone()
            if day_row and day_row[0]:
                QMessageBox.warning(self, "تنبيه", "لا يمكن التراجع، اليومية لهذا التاريخ مغلقة. أعد فتحها أولاً من شاشة النقدية")
                return

            cur.execute(f"SELECT المبلغ, الوصف FROM {table_name} WHERE {record_id_col} = ?", (record_id,))
            record = cur.fetchone()
            if not record:
                QMessageBox.warning(self, "تنبيه", "السجل المراد التراجع عنه غير موجود")
                return

            amount = record["المبلغ"]
            desc = record["الوصف"]
            msg = f"المبلغ: {amount}\nالتاريخ: {affected_date}\nالوصف: {desc}"
            reply = QMessageBox.question(
                self, "تأكيد التراجع",
                f"هل أنت متأكد من التراجع عن آخر عملية {operation_type}؟\n{msg}",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

            cur.execute("BEGIN TRANSACTION")
            cur.execute(f"DELETE FROM {table_name} WHERE {record_id_col} = ?", (record_id,))

            cur.execute("""
                SELECT COALESCE(الرصيد_بعد_الحركة, 0)
                FROM الخزنة ORDER BY معرف DESC LIMIT 1
            """)
            vault_row = cur.fetchone()
            vault_balance = float(vault_row[0]) if vault_row else 0.0
            new_vault = vault_balance + amount
            cur.execute("""
                INSERT INTO الخزنة
                (التاريخ, البيان, إيداع, الرصيد_بعد_الحركة, ملاحظات)
                VALUES (?, ?, ?, ?, ?)
            """, (
                affected_date + ' ' + datetime.now().strftime('%H:%M:%S'),
                f"تراجع عن {operation_type} - {desc}",
                amount,
                new_vault,
                f"تراجع عن {operation_type}"
            ))

            cur.execute("UPDATE سجل_العمليات_الأخيرة SET تم_التراجع = 1 WHERE معرف = ?", (log_id,))
            conn.commit()

            self.refresh_status()
            app_events.emit_data_changed(operation_type)
            app_events.emit_data_changed("cash")
            QMessageBox.information(self, "نجاح", f"تم التراجع عن آخر عملية {operation_type} بنجاح")
        except Exception as e:
            logger.error(str(e))
            if conn:
                conn.rollback()
            QMessageBox.critical(self, "خطأ", f"فشل التراجع:\n{str(e)}")
        finally:
            if conn:
                conn.close()

    def undo_last_expense(self):
        self._undo_operation("مصروف", "المصروفات", "مصروفات_اليوم")

    def undo_last_withdrawal(self):
        self._undo_operation("سحب", "السحوبات", "سحوبات_اليوم")
