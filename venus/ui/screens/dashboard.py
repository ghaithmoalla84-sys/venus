# -*- coding: utf-8 -*-
"""
شاشة لوحة المعلومات الرئيسية - Venus Coffee
ملخص سريع لحالة المتجر: النقدية، المبيعات، المصروفات، المخزون، الديون
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox, QMessageBox, QStyle, QApplication,
    QTabWidget, QSizePolicy, QFrame, QScrollArea
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor
from datetime import datetime, timedelta

from venus.core.database import get_conn, today_str, patch_db_path
from venus.core.events import app_events
from venus.ui.widgets.loading_overlay import LoadingOverlay
from venus.ui.widgets.sales_chart_widget import SalesChartWidget
from venus.ui.styles import (
    Colors, FontSizes, Spacing, BorderRadius, ButtonHeight,
    title_label_style, card_group_box_style, group_box_style,
    table_style, primary_button_style, _px
)
from venus.utils.currency import fmt, fmt_syp
from venus.utils.logger import setup_logger
from venus.utils.net_capital import calculate_net_capital, get_yesterday_net_capital
logger = setup_logger()


class DashboardScreen(QWidget):
    """شاشة لوحة المعلومات الرئيسية"""

    def __init__(self):
        super().__init__()
        self.setLayoutDirection(Qt.RightToLeft)
        self.init_ui()

        timer = QTimer(self)
        timer.timeout.connect(self.refresh_data)
        timer.start(30000)

        app_events.data_changed.connect(self._on_app_data_changed)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(Spacing.MD)
        main_layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"background-color: {Colors.BACKGROUND}; border: none;")

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(Spacing.MD)
        container_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("🏠 لوحة المعلومات - Venus Coffee")
        title.setStyleSheet(title_label_style(font_size=FontSizes.XL3, color=Colors.DARK))
        title.setAlignment(Qt.AlignRight)
        container_layout.addWidget(title)

        self.journal_alert = QLabel("")
        self.journal_alert.setAlignment(Qt.AlignRight)
        self.journal_alert.setStyleSheet(f"""
            background-color: {Colors.WARNING};
            color: {Colors.WHITE};
            font-weight: bold;
            padding: {_px(Spacing.SM)} {_px(Spacing.MD)};
            border-radius: {BorderRadius.MD};
        """)
        self.journal_alert.setWordWrap(True)
        self.journal_alert.hide()
        container_layout.addWidget(self.journal_alert)

        self.net_capital_group = QFrame()
        self.net_capital_group.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.FOCUS_TEAL};
                border-radius: {BorderRadius.XL};
                border: none;
            }}
        """)
        self.net_capital_group.setToolTip("تقدير تقريبي بناءً على آخر سعر شراء للمواد، وليس تقييماً محاسبياً دقيقاً")
        nc_layout = QVBoxLayout(self.net_capital_group)
        nc_layout.setContentsMargins(Spacing.LG, Spacing.MD, Spacing.LG, Spacing.MD)
        nc_layout.setSpacing(Spacing.XS)

        self.net_capital_title = QLabel("💰 رأس المال الصافي التقديري")
        self.net_capital_title.setStyleSheet(f"""
            font-size: {FontSizes.LG};
            font-weight: bold;
            color: rgba(255, 255, 255, 0.9);
        """)
        self.net_capital_title.setAlignment(Qt.AlignRight)

        self.net_capital_value = QLabel("-")
        self.net_capital_value.setStyleSheet(f"""
            font-size: {FontSizes.XL5};
            font-weight: bold;
            color: white;
        """)
        self.net_capital_value.setAlignment(Qt.AlignRight)

        self.net_capital_subtitle = QLabel("تقدير تقريبي بناءً على آخر سعر شراء للمواد، وليس تقييماً محاسبياً دقيقاً")
        self.net_capital_subtitle.setWordWrap(True)
        self.net_capital_subtitle.setStyleSheet(f"""
            font-size: {FontSizes.SM};
            color: rgba(255, 255, 255, 0.8);
        """)
        self.net_capital_subtitle.setAlignment(Qt.AlignRight)

        self.net_capital_comparison = QLabel("")
        self.net_capital_comparison.setStyleSheet(f"""
            font-size: {FontSizes.MD};
            font-weight: bold;
            color: rgba(255, 255, 255, 0.9);
        """)
        self.net_capital_comparison.setAlignment(Qt.AlignRight)

        nc_layout.addWidget(self.net_capital_title)
        nc_layout.addWidget(self.net_capital_value)
        nc_layout.addWidget(self.net_capital_subtitle)
        nc_layout.addWidget(self.net_capital_comparison)

        container_layout.addWidget(self.net_capital_group)

        self.summary_cards_widget = QWidget()
        cards_layout = QGridLayout(self.summary_cards_widget)
        cards_layout.setSpacing(Spacing.MD)

        self.card_cash = self._make_mini_card("💵", "رصيد النقدية الحالي", "#4A90D9")
        self.card_sales = self._make_mini_card("🛒", "مبيعات اليوم", "#10B981")
        self.card_expenses = self._make_mini_card("💸", "مصروفات اليوم", "#EF4444")
        self.card_inventory = self._make_mini_card("📦", "مواد في المخزون", "#F59E0B")
        self.card_debts = self._make_mini_card("👥", "الديون النشطة", "#8B5CF6")

        cards_layout.addWidget(self.card_cash, 0, 0)
        cards_layout.addWidget(self.card_sales, 0, 1)
        cards_layout.addWidget(self.card_expenses, 0, 2)
        cards_layout.addWidget(self.card_inventory, 0, 3)
        cards_layout.addWidget(self.card_debts, 0, 4)

        for i in range(5):
            cards_layout.setColumnStretch(i, 1)

        container_layout.addWidget(self.summary_cards_widget)

        top_sellers_chart_widget = QWidget()
        top_sellers_chart_layout = QHBoxLayout(top_sellers_chart_widget)
        top_sellers_chart_layout.setSpacing(Spacing.MD)
        top_sellers_chart_layout.setContentsMargins(0, 0, 0, 0)

        self.top_sellers_group = self._make_section("🏆 الأفضل مبيعاً هذا الشهر", "#F59E0B", ["المجموعة", "المبلغ"])
        self.top_sellers_msg = QLabel("لا توجد مبيعات مسجلة هذا الشهر بعد")
        self.top_sellers_msg.setAlignment(Qt.AlignCenter)
        self.top_sellers_msg.setStyleSheet(f"""
            color: {Colors.SECONDARY_TEXT};
            font-size: {FontSizes.SM};
            padding: {_px(Spacing.SM)};
        """)
        self.top_sellers_msg.hide()
        self.top_sellers_group.layout().addWidget(self.top_sellers_msg)
        top_sellers_chart_layout.addWidget(self.top_sellers_group, stretch=1)

        self.sales_chart_group = QGroupBox("📈 مبيعات آخر 7 أيام")
        self.sales_chart_group.setStyleSheet(group_box_style(Colors.PRIMARY))
        chart_layout = QVBoxLayout(self.sales_chart_group)
        chart_layout.setContentsMargins(Spacing.SM, Spacing.MD, Spacing.SM, Spacing.SM)
        chart_layout.setSpacing(Spacing.XS)

        self.sales_chart_widget = SalesChartWidget()
        chart_layout.addWidget(self.sales_chart_widget)

        top_sellers_chart_layout.addWidget(self.sales_chart_group, stretch=2)
        container_layout.addWidget(top_sellers_chart_widget, stretch=1)

        self.sales_group = self._make_section("📋 آخر المبيعات", "#4A90D9", ["التاريخ", "المجموعة", "المبلغ"])
        self.debts_group = self._make_section("💳 آخر تحركات الديون", "#8B5CF6", ["التاريخ", "الدائن", "المبلغ", "النوع"])

        sales_debts_widget = QWidget()
        sales_debts_layout = QHBoxLayout(sales_debts_widget)
        sales_debts_layout.setSpacing(Spacing.MD)
        sales_debts_layout.setContentsMargins(0, 0, 0, 0)

        sales_debts_layout.addWidget(self.sales_group, stretch=1)
        sales_debts_layout.addWidget(self.debts_group, stretch=1)
        container_layout.addWidget(sales_debts_widget, stretch=1)

        self.low_stock_group = self._make_section("⚠️ المواد منخفضة المخزون", "#F59E0B", ["المادة", "المجموعة", "الكمية"])
        container_layout.addWidget(self.low_stock_group, stretch=1)

        refresh_btn = QPushButton("تحديث البيانات")
        refresh_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_BrowserReload))
        refresh_btn.setFixedHeight(ButtonHeight.XL)
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setStyleSheet(primary_button_style(
            bg=Colors.PRIMARY, hover=Colors.PRIMARY_HOVER,
            font_size=FontSizes.XL, padding="10px 24px"
        ))
        refresh_btn.clicked.connect(self.refresh_data)
        self.refresh_btn = refresh_btn
        container_layout.addWidget(refresh_btn, alignment=Qt.AlignRight)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        self.loading_overlay = LoadingOverlay(self)
        main_layout.addWidget(self.loading_overlay)

        self.refresh_data()

    def _make_mini_card(self, emoji, title_text, accent_color):
        container = QFrame()
        container.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.CARD_BG};
                border: 1px solid {Colors.BORDER};
                border-radius: {BorderRadius.LG};
            }}
        """)
        layout = QVBoxLayout(container)
        layout.setSpacing(Spacing.XS)
        layout.setContentsMargins(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD)

        icon_container = QWidget()
        accent_qcolor = QColor(accent_color)
        bg_rgba = f"rgba({accent_qcolor.red()}, {accent_qcolor.green()}, {accent_qcolor.blue()}, 0.12)"
        icon_container.setStyleSheet(f"""
            background-color: {bg_rgba};
            border-radius: {BorderRadius.MD};
        """)
        icon_layout = QHBoxLayout(icon_container)
        icon_layout.setContentsMargins(Spacing.XS, Spacing.XS, Spacing.XS, Spacing.XS)
        icon_layout.setSpacing(Spacing.XS)

        icon_label = QLabel(emoji)
        icon_label.setStyleSheet(f"font-size: 16px; background-color: transparent; border: none;")
        icon_label.setAlignment(Qt.AlignCenter)

        title = QLabel(title_text)
        title.setWordWrap(True)
        title.setStyleSheet(f"""
            font-size: {FontSizes.XS};
            color: {Colors.DARK_TEXT};
            font-weight: bold;
            background-color: transparent;
            border: none;
        """)
        title.setAlignment(Qt.AlignCenter)

        icon_layout.addStretch()
        icon_layout.addWidget(icon_label)
        icon_layout.addWidget(title)
        icon_layout.addStretch()

        value_label = QLabel("-")
        value_label.setStyleSheet(f"""
            font-size: {FontSizes.XL2};
            font-weight: bold;
            color: {Colors.DARK_TEXT};
            background-color: transparent;
            border: none;
        """)
        value_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(icon_container)
        layout.addWidget(value_label)

        container.value_label = value_label
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        return container

    def _make_section(self, title_text, header_color, headers):
        group = QGroupBox(title_text)
        group.setStyleSheet(group_box_style(header_color))

        layout = QVBoxLayout(group)
        layout.setContentsMargins(Spacing.SM, Spacing.MD, Spacing.SM, Spacing.SM)
        layout.setSpacing(Spacing.XS)

        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.horizontalHeader().setLayoutDirection(Qt.RightToLeft)
        table.setStyleSheet(table_style(header_color))
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(True)
        table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout.addWidget(table, 1)
        group.table = table
        group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        return group

    def _on_app_data_changed(self, entity_name):
        relevant = {"sales", "materials", "purchases", "creditors", "cash", "expenses", "withdrawals"}
        if entity_name in relevant:
            self.refresh_data()

    def refresh_data(self):
        self.loading_overlay.start()
        QApplication.processEvents()
        conn = get_conn()
        try:
            cur = conn.cursor()

            cur.execute("""
                SELECT الرصيد_بعد_الحركة FROM الخزنة
                ORDER BY معرف DESC LIMIT 1
            """)
            row = cur.fetchone()
            cash_balance = row["الرصيد_بعد_الحركة"] if row else 0

            cur.execute("""
                SELECT COUNT(*) as cnt FROM أرصدة_الصندوق WHERE التاريخ = ?
            """, (today_str(),))
            journal_row = cur.fetchone()
            journal_opened = journal_row["cnt"] > 0 if journal_row else False

            cur.execute("""
                SELECT COALESCE(SUM(المبلغ_الإجمالي), 0) as total
                FROM المبيعات_اليومية
                WHERE date(normalize_date(التاريخ)) = ?
            """, (today_str(),))
            row = cur.fetchone()
            sales_today = row["total"] if row else 0

            cur.execute("""
                SELECT COALESCE(SUM(المبلغ), 0) as total
                FROM المصروفات
                WHERE date(normalize_date(التاريخ)) = ?
            """, (today_str(),))
            row = cur.fetchone()
            expenses_today = row["total"] if row else 0

            cur.execute("""
                SELECT COUNT(*) as cnt FROM المخزون WHERE الكمية_المتوفرة > 0
            """)
            row = cur.fetchone()
            inventory_count = row["cnt"] if row else 0

            cur.execute("""
                SELECT COUNT(*) as cnt FROM الديون WHERE حالة_الدين = 'نشط'
            """)
            row = cur.fetchone()
            active_debts = row["cnt"] if row else 0

            today = today_str()
            first_day = today[:8] + "01"
            cur.execute("""
                SELECT ج.الاسم as اسم_المجموعة, SUM(م.المبلغ_الإجمالي) as الإجمالي
                FROM المبيعات_اليومية م
                JOIN المجموعات ج ON م.معرف_المجموعة = ج.معرف
                WHERE date(normalize_date(م.التاريخ)) >= ?
                  AND date(normalize_date(م.التاريخ)) <= ?
                  AND ج.الاسم != 'مبيعات غير مسجلة'
                GROUP BY م.معرف_المجموعة
                ORDER BY الإجمالي DESC
                LIMIT 3
            """, (first_day, today))
            top_sellers_rows = cur.fetchall()

            cur.execute("""
                SELECT date(normalize_date(التاريخ)) as day, SUM(المبلغ_الإجمالي) as total
                FROM المبيعات_اليومية
                WHERE date(normalize_date(التاريخ)) >= date('now', '-6 days')
                  AND date(normalize_date(التاريخ)) <= date('now')
                  AND معرف_المجموعة NOT IN (
                      SELECT معرف FROM المجموعات WHERE الاسم = 'مبيعات غير مسجلة'
                  )
                GROUP BY day
                ORDER BY day
            """)
            chart_rows = cur.fetchall()

            cur.execute("""
                SELECT م.التاريخ, ج.الاسم as اسم_المجموعة, م.المبلغ_الإجمالي
                FROM view_المبيعات_المفصلة م
                JOIN المجموعات ج ON م.معرف_المجموعة = ج.معرف
                ORDER BY م.معرف DESC
                LIMIT 5
            """)
            sales_rows = cur.fetchall()

            cur.execute("""
                SELECT م.الاسم, ج.الاسم as اسم_المجموعة, خ.الكمية_المتوفرة
                FROM المخزون خ
                JOIN المواد_الفرعية م ON خ.معرف_المادة_الفرعية = م.معرف
                JOIN المجموعات ج ON م.معرف_المجموعة = ج.معرف
                WHERE خ.الكمية_المتوفرة <= م.الحد_الأدنى
                ORDER BY خ.الكمية_المتوفرة ASC
                LIMIT 10
            """)
            low_stock_rows = cur.fetchall()

            cur.execute("""
                SELECT t.التاريخ, d.اسم_الطرف, t.المبلغ, t.نوع_الحركة
                FROM تحركات_الديون t
                JOIN الديون d ON t.معرف_الدين = d.معرف
                ORDER BY t.معرف DESC
                LIMIT 5
            """)
            debt_movements = cur.fetchall()

            self.card_cash.value_label.setText(fmt_syp(cash_balance))
            self.card_sales.value_label.setText(fmt_syp(sales_today))
            self.card_expenses.value_label.setText(fmt_syp(expenses_today))
            self.card_inventory.value_label.setText(str(inventory_count))
            self.card_debts.value_label.setText(str(active_debts))

            if not journal_opened:
                self.journal_alert.setText("⚠️ لم تُفتح اليومية بعد لهذا اليوم. لن تُسجَّل المبيعات والمصروفات حتى تُفتح من شاشة النقدية.")
                self.journal_alert.show()
            else:
                self.journal_alert.hide()

            net_capital = calculate_net_capital()
            self.net_capital_value.setText(fmt_syp(net_capital))

            yesterday_capital = get_yesterday_net_capital()
            if yesterday_capital is not None:
                diff = net_capital - yesterday_capital
                if diff > 0:
                    self.net_capital_comparison.setText(f"📈 +{fmt(diff)} ليرة سورية عن الأمس")
                    self.net_capital_comparison.setStyleSheet(f"font-size: {FontSizes.MD}; font-weight: bold; color: {Colors.SUCCESS};")
                elif diff < 0:
                    self.net_capital_comparison.setText(f"📉 {fmt(diff)} ليرة سورية عن الأمس")
                    self.net_capital_comparison.setStyleSheet(f"font-size: {FontSizes.MD}; font-weight: bold; color: {Colors.DANGER};")
                else:
                    self.net_capital_comparison.setText("➡️ لا تغيير عن الأمس")
                    self.net_capital_comparison.setStyleSheet(f"font-size: {FontSizes.MD}; font-weight: bold; color: {Colors.WARNING};")
            else:
                self.net_capital_comparison.setText("لا توجد بيانات كافية للمقارنة")
                self.net_capital_comparison.setStyleSheet(f"font-size: {FontSizes.SM}; color: rgba(255, 255, 255, 0.7); font-style: italic;")

            if not top_sellers_rows:
                self.top_sellers_group.table.hide()
                self.top_sellers_msg.show()
            else:
                self.top_sellers_group.table.show()
                self.top_sellers_msg.hide()
                self.top_sellers_group.table.setRowCount(len(top_sellers_rows))
                for r, row in enumerate(top_sellers_rows):
                    self.top_sellers_group.table.setItem(r, 0, QTableWidgetItem(str(row["اسم_المجموعة"] or "")))
                    amt = row["الإجمالي"] or 0
                    self.top_sellers_group.table.setItem(r, 1, QTableWidgetItem(fmt(amt)))

            chart_data = {}
            for row in chart_rows:
                day = row["day"]
                chart_data[day] = row["total"] or 0

            today = datetime.now().date()
            labels = []
            for i in range(6, -1, -1):
                d = today - timedelta(days=i)
                labels.append((d.strftime("%d/%m"), chart_data.get(d.strftime("%Y-%m-%d"), 0)))

            self.sales_chart_widget.set_data(labels)

            self.sales_group.table.setRowCount(len(sales_rows))
            for r, row in enumerate(sales_rows):
                date_str = str(row["التاريخ"] or "")[:10] if row["التاريخ"] else ""
                self.sales_group.table.setItem(r, 0, QTableWidgetItem(date_str))
                self.sales_group.table.setItem(r, 1, QTableWidgetItem(str(row["اسم_المجموعة"] or "")))
                amt = row["المبلغ_الإجمالي"] or 0
                self.sales_group.table.setItem(r, 2, QTableWidgetItem(fmt(amt)))

            self.low_stock_group.table.setRowCount(len(low_stock_rows))
            for r, row in enumerate(low_stock_rows):
                self.low_stock_group.table.setItem(r, 0, QTableWidgetItem(str(row["الاسم"] or "")))
                self.low_stock_group.table.setItem(r, 1, QTableWidgetItem(str(row["اسم_المجموعة"] or "")))
                qty = row["الكمية_المتوفرة"] or 0
                if qty == 0:
                    qty_item = QTableWidgetItem("نفذت الكمية")
                    qty_item.setForeground(QColor(Colors.DANGER))
                    qty_item.setFont(qty_item.font())
                    f = qty_item.font()
                    f.setBold(True)
                    qty_item.setFont(f)
                else:
                    qty_item = QTableWidgetItem(f"{qty:,.2f}")
                    qty_item.setForeground(QColor(Colors.WARNING))
                qty_item.setTextAlignment(Qt.AlignCenter)
                self.low_stock_group.table.setItem(r, 2, qty_item)

            self.debts_group.table.setRowCount(len(debt_movements))
            for r, row in enumerate(debt_movements):
                date_str = str(row["التاريخ"] or "")[:16] if row["التاريخ"] else ""
                self.debts_group.table.setItem(r, 0, QTableWidgetItem(date_str))
                self.debts_group.table.setItem(r, 1, QTableWidgetItem(str(row["اسم_الطرف"] or "")))
                amt = row["المبلغ"] or 0
                self.debts_group.table.setItem(r, 2, QTableWidgetItem(fmt(amt)))
                self.debts_group.table.setItem(r, 3, QTableWidgetItem(str(row["نوع_الحركة"] or "")))

        except Exception as e:
            logger.error(str(e))
        finally:
            conn.close()
            self.loading_overlay.stop()
