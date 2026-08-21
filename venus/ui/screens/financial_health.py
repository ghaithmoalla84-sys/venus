# -*- coding: utf-8 -*-
"""
شاشة الصحة المالية - Venus Coffee
ملخص شامل لحالة المتجر المالية: رأس المال، المخزون، السيولة، الديون، وحركة آخر 30 يوم
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox, QMessageBox,
    QStyle, QApplication, QScrollArea, QFrame, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer
from datetime import datetime

from venus.core.database import get_conn, today_str
from venus.core.events import app_events
from venus.core.repositories.financial import (
    get_total_debts_in_syp,
    get_vault_balance as get_vault_balance_central
)
from venus.ui.widgets.loading_overlay import LoadingOverlay
from PyQt5.QtGui import QColor

from venus.ui.styles import (
    Colors, FontSizes, Spacing, BorderRadius,
    title_label_style, group_box_style, table_style, primary_button_style
)
from venus.utils.currency import fmt, fmt_syp, round_currency
from venus.utils.logger import setup_logger
logger = setup_logger()

CARD_COLORS = {
    "رأس_المال": "#2980b9",
    "مخزون": "#27ae60",
    "سيولة": "#e67e22",
    "ديون": "#e74c3c"
}

CARD_ICONS = {
    "رأس_المال": "💰",
    "مخزون": "📦",
    "سيولة": "🏦",
    "ديون": "💳"
}

CARD_TITLES = {
    "رأس_المال": "رأس المال الصافي",
    "مخزون": "قيمة المخزون",
    "سيولة": "السيولة النقدية",
    "ديون": "إجمالي الديون"
}


class FinancialHealthScreen(QWidget):
    """شاشة الصحة المالية"""

    def __init__(self):
        super().__init__()
        self.setLayoutDirection(Qt.RightToLeft)
        self._build_ui()
        self._setup_timer()

        app_events.data_changed.connect(self._on_app_data_changed)

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setSpacing(15)
        main.setContentsMargins(20, 20, 20, 20)

        title = QLabel("📈 الصحة المالية - Venus Coffee")
        title.setStyleSheet(title_label_style(font_size=FontSizes.XL4, color=Colors.DARK))
        title.setAlignment(Qt.AlignRight)
        main.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"background-color: {Colors.BACKGROUND}; border: none;")

        container = QWidget()
        container.setStyleSheet(f"background-color: {Colors.BACKGROUND};")
        self._container_layout = QVBoxLayout(container)
        self._container_layout.setSpacing(15)
        self._container_layout.setContentsMargins(0, 0, 0, 0)

        self._build_summary_cards()
        self._build_health_indicator()
        self._build_inventory_section()
        self._build_debts_section()
        self._build_activity_section()

        self._container_layout.addStretch(1)

        scroll.setWidget(container)
        main.addWidget(scroll, stretch=1)

        refresh_btn = QPushButton("تحديث البيانات")
        refresh_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_BrowserReload))
        refresh_btn.setFixedHeight(45)
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setStyleSheet(primary_button_style(
            bg=Colors.PRIMARY, hover=Colors.PRIMARY_HOVER,
            font_size=FontSizes.XL, padding="10px 24px"
        ))
        refresh_btn.clicked.connect(self.load_data)
        self.refresh_btn = refresh_btn
        main.addWidget(refresh_btn, alignment=Qt.AlignRight)

        self.loading_overlay = LoadingOverlay(self)
        main.addWidget(self.loading_overlay)

        self.load_data()

    def _setup_timer(self):
        timer = QTimer(self)
        timer.timeout.connect(self.load_data)
        timer.start(60000)

    def _build_summary_cards(self):
        cards_grid = QGridLayout()
        cards_grid.setSpacing(15)

        self.card_labels = {}
        keys = ["رأس_المال", "مخزون", "سيولة", "ديون"]
        for idx, key in enumerate(keys):
            card = QFrame()
            accent_color = QColor(CARD_COLORS[key])
            bg_rgba = f"rgba({accent_color.red()}, {accent_color.green()}, {accent_color.blue()}, 0.12)"
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: {Colors.CARD_BG};
                    border: 1px solid {Colors.BORDER};
                    border-radius: {BorderRadius.LG};
                }}
            """)

            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(8)
            card_layout.setContentsMargins(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD)

            icon_container = QWidget()
            icon_container.setStyleSheet(f"""
                background-color: {bg_rgba};
                border-radius: {BorderRadius.MD};
            """)
            icon_layout = QHBoxLayout(icon_container)
            icon_layout.setContentsMargins(Spacing.XS, Spacing.XS, Spacing.XS, Spacing.XS)
            icon_layout.setSpacing(Spacing.XS)

            icon_label = QLabel(CARD_ICONS[key])
            icon_label.setStyleSheet(f"font-size: 16px; background-color: transparent; border: none;")
            icon_label.setAlignment(Qt.AlignCenter)

            title_lbl = QLabel(CARD_TITLES[key])
            title_lbl.setWordWrap(True)
            title_lbl.setStyleSheet(f"""
                font-size: {FontSizes.XS};
                color: {Colors.DARK_TEXT};
                font-weight: bold;
                background-color: transparent;
                border: none;
            """)
            title_lbl.setAlignment(Qt.AlignCenter)

            icon_layout.addStretch()
            icon_layout.addWidget(icon_label)
            icon_layout.addWidget(title_lbl)
            icon_layout.addStretch()

            value_lbl = QLabel("-")
            value_lbl.setStyleSheet(f"""
                font-size: {FontSizes.XL2};
                font-weight: bold;
                color: {Colors.DARK_TEXT};
            """)
            value_lbl.setAlignment(Qt.AlignRight)

            card_layout.addWidget(icon_container)
            card_layout.addWidget(value_lbl)

            self.card_labels[key] = value_lbl
            cards_grid.addWidget(card, 0, idx)

        for i in range(4):
            cards_grid.setColumnStretch(i, 1)

        self._container_layout.addLayout(cards_grid)

    def _build_health_indicator(self):
        self.health_container = QWidget()
        hbox = QHBoxLayout(self.health_container)
        hbox.setContentsMargins(15, 10, 15, 10)
        hbox.setSpacing(10)

        self.health_icon = QLabel("-")
        self.health_icon.setStyleSheet(f"font-size: 28px;")

        self.health_text = QLabel("جاري الحساب...")
        self.health_text.setStyleSheet(f"""
            font-size: {FontSizes.XL2};
            font-weight: bold;
            color: {Colors.DARK};
        """)

        hbox.addWidget(self.health_icon)
        hbox.addWidget(self.health_text)
        hbox.addStretch()

        self._container_layout.addWidget(self.health_container)

    def _build_inventory_section(self):
        group = QGroupBox("📦 تفاصيل المخزون")
        group.setStyleSheet(group_box_style(Colors.SUCCESS))
        layout = QVBoxLayout(group)
        layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        layout.setSpacing(Spacing.LG)

        self.inventory_table = QTableWidget()
        self.inventory_table.setColumnCount(5)
        self.inventory_table.setHorizontalHeaderLabels(["المادة", "المجموعة", "الوحدة", "الكمية", "القيمة الإجمالية"])
        self.inventory_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.inventory_table.horizontalHeader().setLayoutDirection(Qt.RightToLeft)
        self.inventory_table.setStyleSheet(table_style(Colors.SUCCESS))
        self.inventory_table.setAlternatingRowColors(True)
        self.inventory_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.inventory_table.verticalHeader().setVisible(False)
        self.inventory_table.setShowGrid(True)
        layout.addWidget(self.inventory_table, stretch=1)

        self.inventory_total = QLabel("الإجمالي: 0 ليرة سورية")
        self.inventory_total.setStyleSheet(f"""
            font-size: {FontSizes.LG};
            font-weight: bold;
            color: {Colors.DARK};
            padding: {Spacing.SM}px 0;
        """)
        self.inventory_total.setAlignment(Qt.AlignRight)
        layout.addWidget(self.inventory_total)

        self._container_layout.addWidget(group)

    def _build_debts_section(self):
        group = QGroupBox("💳 توزيع الديون")
        group.setStyleSheet(group_box_style(Colors.DANGER))
        layout = QVBoxLayout(group)
        layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        layout.setSpacing(Spacing.LG)

        self.debts_table = QTableWidget()
        self.debts_table.setColumnCount(5)
        self.debts_table.setHorizontalHeaderLabels(["الطرف", "النوع", "العملة", "الرصيد", "الحالة"])
        self.debts_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.debts_table.horizontalHeader().setLayoutDirection(Qt.RightToLeft)
        self.debts_table.setStyleSheet(table_style(Colors.DANGER))
        self.debts_table.setAlternatingRowColors(True)
        self.debts_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.debts_table.verticalHeader().setVisible(False)
        self.debts_table.setShowGrid(True)
        layout.addWidget(self.debts_table, stretch=1)

        self.debts_total = QLabel("إجمالي الديون بالليرة: 0 ليرة سورية")
        self.debts_total.setStyleSheet(f"""
            font-size: {FontSizes.LG};
            font-weight: bold;
            color: {Colors.DANGER};
            padding: {Spacing.SM}px 0;
        """)
        self.debts_total.setAlignment(Qt.AlignRight)
        layout.addWidget(self.debts_total)

        self._container_layout.addWidget(group)

    def _build_activity_section(self):
        group = QGroupBox("📅 ملخص حركة آخر 30 يوم")
        group.setStyleSheet(group_box_style(Colors.PRIMARY))
        layout = QVBoxLayout(group)
        layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        layout.setSpacing(Spacing.LG)

        self.activity_labels = {}

        sales_widget = QWidget()
        sales_layout = QHBoxLayout(sales_widget)
        sales_layout.setContentsMargins(0, 0, 0, 0)
        sales_layout.setSpacing(Spacing.LG)
        sales_layout.addWidget(QLabel("🛒 المبيعات:"))
        self.activity_labels["sales"] = QLabel("0 ليرة سورية")
        self.activity_labels["sales"].setStyleSheet(f"font-size: {FontSizes.LG}; font-weight: bold; color: {Colors.SUCCESS};")
        sales_layout.addWidget(self.activity_labels["sales"])
        sales_layout.addStretch()
        layout.addWidget(sales_widget)

        expenses_widget = QWidget()
        expenses_layout = QHBoxLayout(expenses_widget)
        expenses_layout.setContentsMargins(0, 0, 0, 0)
        expenses_layout.setSpacing(Spacing.LG)
        expenses_layout.addWidget(QLabel("💸 المصروفات:"))
        self.activity_labels["expenses"] = QLabel("0 ليرة سورية")
        self.activity_labels["expenses"].setStyleSheet(f"font-size: {FontSizes.LG}; font-weight: bold; color: {Colors.DANGER};")
        expenses_layout.addWidget(self.activity_labels["expenses"])
        expenses_layout.addStretch()
        layout.addWidget(expenses_widget)

        purchases_widget = QWidget()
        purchases_layout = QHBoxLayout(purchases_widget)
        purchases_layout.setContentsMargins(0, 0, 0, 0)
        purchases_layout.setSpacing(Spacing.LG)
        purchases_layout.addWidget(QLabel("📥 المشتريات:"))
        self.activity_labels["purchases"] = QLabel("0 ليرة سورية")
        self.activity_labels["purchases"].setStyleSheet(f"font-size: {FontSizes.LG}; font-weight: bold; color: {Colors.WARNING};")
        purchases_layout.addWidget(self.activity_labels["purchases"])
        purchases_layout.addStretch()
        layout.addWidget(purchases_widget)

        net_widget = QWidget()
        net_widget.setStyleSheet(f"""
            background-color: {Colors.LIGHT_GRAY};
            border-radius: {BorderRadius.LG};
            padding: {Spacing.LG}px;
        """)
        net_layout = QHBoxLayout(net_widget)
        net_layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        net_layout.setSpacing(Spacing.LG)
        net_layout.addWidget(QLabel("📊 صافي آخر 30 يوم:"))
        self.activity_labels["net"] = QLabel("0 ليرة سورية")
        self.activity_labels["net"].setStyleSheet(f"font-size: {FontSizes.XL}; font-weight: bold; color: {Colors.DARK};")
        net_layout.addWidget(self.activity_labels["net"])
        net_layout.addStretch()
        layout.addWidget(net_widget)

        self._container_layout.addWidget(group)

    def _on_app_data_changed(self, entity_name):
        relevant = {"sales", "materials", "purchases", "creditors", "cash", "expenses", "withdrawals"}
        if entity_name in relevant:
            self.load_data()

    def _get_exchange_rate(self):
        from venus.utils.currency import get_exchange_rate
        rate = get_exchange_rate()
        return rate if rate is not None else 8500.0

    def _convert_to_syp(self, amount, currency):
        if currency == "دولار":
            return round_currency(float(amount or 0) * self._get_exchange_rate())
        return round_currency(amount or 0)

    def load_data(self):
        self.loading_overlay.start()
        QApplication.processEvents()
        conn = None
        try:
            conn = get_conn()
            cur = conn.cursor()
            exchange_rate = self._get_exchange_rate()

            net_capital = 0.0
            inventory_value = 0.0
            total_debts = 0.0
            liquidity = 0.0

            cur.execute("""
                SELECT م.الاسم, ج.الاسم as المجموعة, م.الوحدة,
                       خ.الكمية_المتوفرة,
                       م.سعر_الشراء_الأخير,
                       (خ.الكمية_المتوفرة * م.سعر_الشراء_الأخير) as القيمة_الإجمالية
                FROM المخزون خ
                JOIN المواد_الفرعية م ON خ.معرف_المادة_الفرعية = م.معرف
                JOIN المجموعات ج ON م.معرف_المجموعة = ج.معرف
                ORDER BY القيمة_الإجمالية DESC
            """)
            inventory_rows = cur.fetchall()

            cur.execute("""
                SELECT SUM(خ.الكمية_المتوفرة * م.سعر_الشراء_الأخير)
                FROM المخزون خ
                JOIN المواد_الفرعية م ON خ.معرف_المادة_الفرعية = م.معرف
                WHERE م.سعر_الشراء_الأخير > 0
            """)
            row = cur.fetchone()
            inventory_value = float(row[0]) if row and row[0] is not None else 0.0

            total_debts = get_total_debts_in_syp()

            cur.execute("SELECT الرصيد_بعد_الحركة FROM الخزنة ORDER BY معرف DESC LIMIT 1")
            row = cur.fetchone()
            vault_balance = round_currency(row["الرصيد_بعد_الحركة"]) if row and row["الرصيد_بعد_الحركة"] is not None else 0

            cur.execute("SELECT رصيد_بداية_اليوم FROM أرصدة_الصندوق WHERE التاريخ = ?", (today_str(),))
            row = cur.fetchone()
            opening = round_currency(row["رصيد_بداية_اليوم"]) if row and row["رصيد_بداية_اليوم"] is not None else 0

            cur.execute("""
                SELECT COALESCE(SUM(المبلغ_الإجمالي), 0) as total
                FROM المبيعات_اليومية
                WHERE date(normalize_date(التاريخ)) = ?
            """, (today_str(),))
            sales_today = round_currency(cur.fetchone()["total"])

            drawer_today = opening + sales_today
            if drawer_today < 0:
                drawer_today = 0

            liquidity = vault_balance + drawer_today
            net_capital = inventory_value + liquidity - total_debts

            self.card_labels["رأس_المال"].setText(fmt_syp(net_capital))
            self.card_labels["مخزون"].setText(fmt_syp(inventory_value))
            self.card_labels["سيولة"].setText(fmt_syp(liquidity))
            self.card_labels["ديون"].setText(fmt_syp(total_debts))

            if net_capital > 0:
                if total_debts < net_capital * 0.3:
                    self.health_icon.setText("🟢")
                    self.health_text.setText("ممتاز")
                    self.health_text.setStyleSheet(f"font-size: {FontSizes.XL2}; font-weight: bold; color: #27ae60;")
                elif total_debts < net_capital * 0.6:
                    self.health_icon.setText("🟡")
                    self.health_text.setText("جيد")
                    self.health_text.setStyleSheet(f"font-size: {FontSizes.XL2}; font-weight: bold; color: #f39c12;")
                else:
                    self.health_icon.setText("🔴")
                    self.health_text.setText("يحتاج انتباه")
                    self.health_text.setStyleSheet(f"font-size: {FontSizes.XL2}; font-weight: bold; color: #e74c3c;")
            else:
                self.health_icon.setText("🔴")
                self.health_text.setText("يحتاج انتباه")
                self.health_text.setStyleSheet(f"font-size: {FontSizes.XL2}; font-weight: bold; color: #e74c3c;")

            self.inventory_table.setRowCount(len(inventory_rows))
            for r, row in enumerate(inventory_rows):
                qty = float(row["الكمية_المتوفرة"] or 0)
                price = float(row["سعر_الشراء_الأخير"] or 0)
                val = qty * price
                if row["الوحدة"] == "دولار":
                    val = val * exchange_rate
                    val_syp = round_currency(val)
                    val_str = f"{fmt(val)} دولار ({fmt_syp(val_syp)})"
                else:
                    val_syp = round_currency(val)
                    val_str = fmt_syp(val_syp)

                self.inventory_table.setItem(r, 0, QTableWidgetItem(str(row["الاسم"] or "")))
                self.inventory_table.setItem(r, 1, QTableWidgetItem(str(row["المجموعة"] or "")))
                self.inventory_table.setItem(r, 2, QTableWidgetItem(str(row["الوحدة"] or "")))
                qty_item = QTableWidgetItem(f"{qty:,.2f}")
                qty_item.setTextAlignment(Qt.AlignCenter)
                self.inventory_table.setItem(r, 3, qty_item)
                val_item = QTableWidgetItem(val_str)
                val_item.setTextAlignment(Qt.AlignRight)
                self.inventory_table.setItem(r, 4, val_item)

            self.inventory_total.setText(f"الإجمالي: {fmt_syp(round_currency(inventory_value))}")

            cur.execute("""
                SELECT اسم_الطرف, نوع_الطرف, العملة, الرصيد, حالة_الدين
                FROM الديون
                WHERE حالة_الدين != 'مسدد'
                ORDER BY الرصيد DESC
            """)
            debt_rows = cur.fetchall()

            self.debts_table.setRowCount(len(debt_rows))
            total_syp = 0.0
            for r, row in enumerate(debt_rows):
                self.debts_table.setItem(r, 0, QTableWidgetItem(str(row["اسم_الطرف"] or "")))
                self.debts_table.setItem(r, 1, QTableWidgetItem(str(row["نوع_الطرف"] or "")))
                self.debts_table.setItem(r, 2, QTableWidgetItem(str(row["العملة"] or "ليرة_سورية")))
                syp_val = self._convert_to_syp(row["الرصيد"], row["العملة"])
                total_syp += syp_val
                self.debts_table.setItem(r, 3, QTableWidgetItem(fmt_syp(syp_val)))
                self.debts_table.setItem(r, 4, QTableWidgetItem(str(row["حالة_الدين"] or "")))

            self.debts_total.setText(f"إجمالي الديون بالليرة: {fmt_syp(round_currency(total_syp))}")

            cur.execute("""
                SELECT COALESCE(SUM(المبلغ_الإجمالي), 0) as total
                FROM المبيعات_اليومية
                WHERE التاريخ >= date('now', '-30 days')
            """)
            sales_30 = round_currency(cur.fetchone()["total"])

            cur.execute("""
                SELECT COALESCE(SUM(المبلغ), 0) as total
                FROM المصروفات
                WHERE التاريخ >= date('now', '-30 days')
            """)
            expenses_30 = round_currency(cur.fetchone()["total"])

            cur.execute("""
                SELECT COALESCE(SUM(المبلغ_الإجمالي), 0) as total
                FROM فواتير_الشراء
                WHERE التاريخ >= date('now', '-30 days')
            """)
            purchases_30 = round_currency(cur.fetchone()["total"])

            net_30 = sales_30 - expenses_30 - purchases_30

            self.activity_labels["sales"].setText(fmt_syp(sales_30))
            self.activity_labels["expenses"].setText(fmt_syp(expenses_30))
            self.activity_labels["purchases"].setText(fmt_syp(purchases_30))
            self.activity_labels["net"].setText(fmt_syp(net_30))

        except Exception as e:
            logger.error(str(e))
            QMessageBox.warning(self, "تنبيه", "فشل تحديث البيانات")
        finally:
            if conn:
                conn.close()
            self.loading_overlay.stop()
