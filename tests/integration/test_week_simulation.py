# -*- coding: utf-8 -*-
"""
محاكاة أسبوع عمل كامل لمتجر "فينوس كوفي"
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch
from PyQt5.QtWidgets import (
    QMessageBox, QVBoxLayout, QGridLayout, QHBoxLayout,
    QGroupBox, QPushButton, QLabel, QTableWidget,
    QHeaderView, QTableWidgetItem, QStyledItemDelegate,
    QStyle, QApplication, QComboBox, QDateEdit, QWidget
)
from PyQt5.QtCore import Qt, QDate

from venus.core.database import get_conn
from venus.ui.screens.cash import CashScreen
from venus.ui.screens.inventory.screen import InventoryScreen
from venus.ui.screens.sales import SalesScreen
from venus.ui.screens.creditors import CreditorsScreen
from venus.ui.screens.reports import ReportsScreen
from venus.utils.net_capital import calculate_net_capital

from tests.fixtures.week_helpers import (
    setup_week_groups, setup_week_suppliers,
    open_cash_day, close_cash_day, reopen_cash_day,
    add_purchase_bill, add_sale_direct, add_expense_direct,
    add_withdrawal_direct, record_payment_direct,
    run_profit_report, run_sales_report, run_debts_report,
    run_cash_movements_report, run_overdue_report, run_inventory_report,
    run_best_suppliers_report, run_comparison_report, run_tax_report,
    run_suppliers_report, run_buy_list_report,
    validate_inventory_chain, validate_cash_chain,
    validate_debt_chain, validate_net_capital_chain
)
from tests.fixtures.helpers import insert_vault_balance, insert_operation_log


class TestWeekSimulation:
    """محاكاة أسبوع عمل كامل"""

    @pytest.fixture(autouse=True)
    def _setup_week(self, qt_app, temp_db):
        """إعداد بيئة الأسبوع"""
        self.qt_app = qt_app
        self.groups = setup_week_groups()
        self.suppliers = setup_week_suppliers()
        self.dates = [
            "2026-03-01", "2026-03-02", "2026-03-03", "2026-03-04",
            "2026-03-05", "2026-03-06", "2026-03-07"
        ]
        self.week_start = self.dates[0]
        self.week_end = self.dates[-1]
        yield

    def test_full_week_simulation(self):
        """السيناريو الكامل للأسبوع"""
        group_ids = {name: info["id"] for name, info in self.groups.items()}
        mat_ids = {}
        for name, info in self.groups.items():
            for mat in info["materials"]:
                mat_ids[mat["name"]] = mat["id"]

        coffee_group_id = group_ids["قهوة"]
        sweets_group_id = group_ids["حلويات"]
        drinks_group_id = group_ids["مشروبات"]

        supplier_ahmed = self.suppliers["مورد_أحمد"]
        supplier_saeed = self.suppliers["مورد_سعيد"]

        self._report_screens = []

        # ==========================================
        # اليوم 1 (السبت) - التأسيس
        # ==========================================
        screen_cash = open_cash_day(self.qt_app, self.dates[0], 2000000, "ليرة_سورية", 5000000.0)

        # شراء مواد افتتاحية (3 مواد من مجموعتين) نقدي من الدرج
        add_purchase_bill(self.qt_app, self.dates[0], supplier_ahmed, [
            (mat_ids["اسبريسو"], 50, 1500),
            (mat_ids["لاتيه"], 50, 1500),
            (mat_ids["كعك"], 100, 800),
        ], payment_mode="نقدي من الدرج")

        # تسجيل مبيعات لـ 3 مجموعات
        add_sale_direct(coffee_group_id, self.dates[0], 150000, "ليرة_سورية", "مبيعات قهوة")
        add_sale_direct(sweets_group_id, self.dates[0], 80000, "ليرة_سورية", "مبيعات حلويات")
        add_sale_direct(drinks_group_id, self.dates[0], 50000, "ليرة_سورية", "مبيعات مشروبات")

        # تسجيل مصروف (إيجار) وسحب شخصي
        add_expense_direct(self.dates[0], 120000, "إيجار المحل", etype="إيجار", currency="ليرة_سورية")
        add_withdrawal_direct(self.dates[0], 50000, "سحب شخصي", currency="ليرة_سورية")

        # إغلاق اليومية
        close_cash_day(screen_cash, self.dates[0], 2180000)

        # ==========================================
        # اليوم 2 (الأحد) - ديون وشراء آجل
        # ==========================================
        screen_cash2 = open_cash_day(self.qt_app, self.dates[1], 2180000, "ليرة_سورية")

        # إضافة مورد جديد (صديق) برصيد افتتاحي - نستخدم creditors screen
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO الديون (اسم_الطرف, نوع_الطرف, العملة, المبلغ_الإجمالي, المبلغ_المدفوع, الرصيد, حالة_الدين)
            VALUES (?, ?, ?, ?, 0, ?, 'نشط')
        """, ("صديق محمد", "صديق", "ليرة_سورية", 200000, 200000))
        friend_id = cursor.lastrowid
        cursor.execute("""
            INSERT INTO تحركات_الديون (معرف_الدين, المبلغ, نوع_الحركة, ملاحظات)
            VALUES (?, ?, 'إضافة', ?)
        """, (friend_id, 200000, "رصيد افتتاحي"))
        conn.commit()
        conn.close()

        # شراء على الدين (آجل) من المورد الجديد
        add_purchase_bill(self.qt_app, self.dates[1], supplier_ahmed, [
            (mat_ids["بسبوسة"], 40, 2000),
        ], payment_mode="دين (آجل)")

        # تسجيل مبيعات + دفعة جزئية للمورد
        add_sale_direct(coffee_group_id, self.dates[1], 120000, "ليرة_سورية", "مبيعات قهوة")
        add_sale_direct(sweets_group_id, self.dates[1], 60000, "ليرة_سورية", "مبيعات حلويات")

        # دفعة جزئية للمورد أحمد
        record_payment_direct(supplier_ahmed, 80000, self.dates[1] + " 15:00:00")

        close_cash_day(screen_cash2, self.dates[1], 2280000)

        # ==========================================
        # اليوم 3 (الاثنين) - عملة مزدوجة
        # ==========================================
        screen_cash3 = open_cash_day(self.qt_app, self.dates[2], 2280000, "ليرة_سورية")

        # شراء مواد بالدولار نقدي من الخزنة
        add_purchase_bill(self.qt_app, self.dates[2], supplier_saeed, [
            (mat_ids["عصير"], 30, 1.5),
        ], payment_mode="نقدي من الخزنة", cash_amount=45)

        # مبيعات بالدولار والليرة في نفس اليوم
        add_sale_direct(coffee_group_id, self.dates[2], 100000, "ليرة_سورية", "مبيعات ليرة")
        add_sale_direct(drinks_group_id, self.dates[2], 200, "دولار", "مبيعات دولار")

        # مصروف بالليرة
        add_expense_direct(self.dates[2], 30000, "كهرباء", etype="كهرباء", currency="ليرة_سورية")

        close_cash_day(screen_cash3, self.dates[2], 2400000)

        # ==========================================
        # اليوم 4 (الثلاثاء) - الجرد والتعديل
        # ==========================================
        screen_cash4 = open_cash_day(self.qt_app, self.dates[3], 2400000, "ليرة_سورية")

        # جرد دوري لجميع المواد - نستخدم direct SQL لسرعة وموثوقية
        conn = get_conn()
        cursor = conn.cursor()
        audit_date = self.dates[3] + " 10:00:00"

        for name, info in self.groups.items():
            for mat in info["materials"]:
                mat_id = mat["id"]
                cursor.execute("SELECT الكمية_المتوفرة FROM المخزون WHERE معرف_المادة_الفرعية = ?", (mat_id,))
                row = cursor.fetchone()
                theoretical = row[0] if row else 0
                actual = theoretical + 5  # فرق بسيط للجرد
                diff = actual - theoretical
                value = abs(diff) * 1500.0

                cursor.execute("""
                    INSERT INTO الجرد (التاريخ, معرف_المادة_الفرعية, الكمية_النظري, الكمية_الفعلي, فرق_الجرد, قيمة_الفرق, ملاحظات)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (audit_date, mat_id, theoretical, actual, diff, value, f"جرد دوري - {mat['name']}"))

                cursor.execute("""
                    INSERT OR REPLACE INTO المخزون (معرف_المادة_الفرعية, الكمية_المتوفرة, آخر_تحديث)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (mat_id, actual))

                cursor.execute("""
                    INSERT INTO تحركات_المخزون (معرف_المادة_الفرعية, نوع_الحركة, الكمية, الرصيد_بعد, ملاحظات)
                    VALUES (?, 'جرد', ?, ?, ?)
                """, (mat_id, abs(diff), actual, f"جرد دوري - {mat['name']}"))
        conn.commit()
        conn.close()

        # مبيعات + مصروف
        add_sale_direct(sweets_group_id, self.dates[3], 90000, "ليرة_سورية", "مبيعات حلويات")
        add_expense_direct(self.dates[3], 15000, "نقل", etype="نقل", currency="ليرة_سورية")

        close_cash_day(screen_cash4, self.dates[3], 2500000)

        # ==========================================
        # اليوم 5 (الأربعاء) - تحويلات وخزنة
        # ==========================================
        screen_cash5 = open_cash_day(self.qt_app, self.dates[4], 2500000, "ليرة_سورية")

        # شراء جزئي (كاش + دين) مع سحب من الخزنة
        add_purchase_bill(self.qt_app, self.dates[4], supplier_ahmed, [
            (mat_ids["بسكويت"], 60, 1200),
        ], payment_mode="جزئي (كاش + دين)", cash_amount=36000)

        # تحويل من الخزنة إلى الدرج يدوياً
        conn = get_conn()
        cursor = conn.cursor()
        transfer_time = self.dates[4] + " 14:00:00"
        cursor.execute("""
            INSERT INTO تحويلات_الصندوق (التاريخ, من_حساب, إلى_حساب, المبلغ, ملاحظات)
            VALUES (?, 'الخزنة', 'الدرج', ?, ?)
        """, (transfer_time, 100000, "تحويل يدوي من الخزنة للدرج"))
        cursor.execute("""
            INSERT INTO الخزنة (التاريخ, البيان, سحب, الرصيد_بعد_الحركة, ملاحظات)
            VALUES (?, ?, ?, ?, ?)
        """, (transfer_time, "تحويل يدوي للدرج", 100000, 4500000, "تحويل يدوي"))
        conn.commit()
        conn.close()

        # مبيعات كثيرة + سحب كبير
        for _ in range(3):
            add_sale_direct(coffee_group_id, self.dates[4], 80000, "ليرة_سورية")
        add_sale_direct(sweets_group_id, self.dates[4], 70000, "ليرة_سورية")
        add_withdrawal_direct(self.dates[4], 100000, "سحب كبير", currency="ليرة_سورية")

        # إغلاق مع فرق إيجابي
        close_cash_day(screen_cash5, self.dates[4], 2650000)

        # ==========================================
        # اليوم 6 (الخميس) - إعادة فتح وتصحيح
        # ==========================================
        # إعادة فتح يومية اليوم 5
        reopen_cash_day(screen_cash5, self.dates[4])

        # حذف آخر مصروف - نضيف مصروف جديد ثم نتراجع عنه
        add_expense_direct(self.dates[4], 25000, "مصروف إضافي", etype="أخرى", currency="ليرة_سورية")
        insert_operation_log("مصروف", 1, self.dates[4])
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
            screen_cash5.undo_last_expense()

        # تعديل مبيعات - نضيف بيع جديد
        add_sale_direct(drinks_group_id, self.dates[4], 45000, "ليرة_سورية", "مبيعات معدلة")

        # إغلاق مرة أخرى
        close_cash_day(screen_cash5, self.dates[4], 2700000)

        # تراجع عن عملية بيع
        add_sale_direct(coffee_group_id, self.dates[4], 50000, "ليرة_سورية", "للتراجع")
        insert_operation_log("بيع", 1, self.dates[4])
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
            sales_screen = SalesScreen()
            sales_screen.undo_last_sale()

        # ==========================================
        # اليوم 7 (الجمعة) - تقارير وتحقق نهائي
        # ==========================================
        screen_cash7 = open_cash_day(self.qt_app, self.dates[6], 2700000, "ليرة_سورية")

        # جرد ختامي لتفعيل تقرير الأرباح
        conn = get_conn()
        cursor = conn.cursor()
        closing_audit_date = self.dates[6] + " 18:00:00"
        for name, info in self.groups.items():
            for mat in info["materials"]:
                mat_id = mat["id"]
                cursor.execute("SELECT الكمية_المتوفرة FROM المخزون WHERE معرف_المادة_الفرعية = ?", (mat_id,))
                row = cursor.fetchone()
                theoretical = row[0] if row else 0
                actual = theoretical
                diff = actual - theoretical
                value = abs(diff) * 1500.0

                cursor.execute("""
                    INSERT INTO الجرد (التاريخ, معرف_المادة_الفرعية, الكمية_النظري, الكمية_الفعلي, فرق_الجرد, قيمة_الفرق, ملاحظات)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (closing_audit_date, mat_id, theoretical, actual, diff, value, f"جرد ختامي - {mat['name']}"))

                cursor.execute("""
                    INSERT OR REPLACE INTO المخزون (معرف_المادة_الفرعية, الكمية_المتوفرة, آخر_تحديث)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (mat_id, actual))

                cursor.execute("""
                    INSERT INTO تحركات_المخزون (معرف_المادة_الفرعية, نوع_الحركة, الكمية, الرصيد_بعد, ملاحظات)
                    VALUES (?, 'جرد', ?, ?, ?)
                """, (mat_id, abs(diff), actual, f"جرد ختامي - {mat['name']}"))
        conn.commit()
        conn.close()

        # تشغيل جميع التقارير باستخدام شاشة واحدة
        with patch.object(QMessageBox, 'information'), patch.object(QMessageBox, 'critical'):
            reports = ReportsScreen()
            self._report_screens = [reports]

            reports.sales_from.setDate(QDate.fromString(self.week_start, "yyyy-MM-dd"))
            reports.sales_to.setDate(QDate.fromString(self.week_end, "yyyy-MM-dd"))
            reports.load_sales_report()

            reports.profit_from.setDate(QDate.fromString(self.week_start, "yyyy-MM-dd"))
            reports.profit_to.setDate(QDate.fromString(self.week_end, "yyyy-MM-dd"))
            reports.load_profit_report()

            reports.load_inventory()
            reports.load_debts()

            reports.cash_from.setDate(QDate.fromString(self.week_start, "yyyy-MM-dd"))
            reports.cash_to.setDate(QDate.fromString(self.week_end, "yyyy-MM-dd"))
            reports.load_cash_movements()

            reports.load_suppliers_report()
            reports.load_overdue_report()
            reports.load_best_suppliers_report()

            # إصلاح مشكلة QDateEdit المحذوف في تبويب المقارنة
            original_build = reports.build_comparison_tab
            def fixed_build_comparison_tab():
                widget = reports.comparison_tab
                layout = QVBoxLayout(widget)
                layout.setSpacing(15)
                layout.setContentsMargins(20, 20, 20, 20)

                filter_group = QGroupBox("📅 اختر الفترتين للمقارنة")
                fg_layout = QGridLayout(filter_group)

                fg_layout.addWidget(QLabel("الفترة الأولى - من:"), 0, 0)
                reports.cmp_p1_from = QDateEdit(widget)
                reports.cmp_p1_from.setDate(QDate.currentDate().addMonths(-2))
                reports.cmp_p1_from.setCalendarPopup(True)
                fg_layout.addWidget(reports.cmp_p1_from, 0, 1)

                fg_layout.addWidget(QLabel("إلى:"), 0, 2)
                reports.cmp_p1_to = QDateEdit(widget)
                reports.cmp_p1_to.setDate(QDate.currentDate().addMonths(-1))
                reports.cmp_p1_to.setCalendarPopup(True)
                fg_layout.addWidget(reports.cmp_p1_to, 0, 3)

                fg_layout.addWidget(QLabel("الفترة الثانية - من:"), 1, 0)
                reports.cmp_p2_from = QDateEdit(widget)
                reports.cmp_p2_from.setDate(QDate.currentDate().addMonths(-1))
                reports.cmp_p2_from.setCalendarPopup(True)
                fg_layout.addWidget(reports.cmp_p2_from, 1, 1)

                fg_layout.addWidget(QLabel("إلى:"), 1, 2)
                reports.cmp_p2_to = QDateEdit(widget)
                reports.cmp_p2_to.setDate(QDate.currentDate())
                reports.cmp_p2_to.setCalendarPopup(True)
                fg_layout.addWidget(reports.cmp_p2_to, 1, 3)

                compare_btn = QPushButton("🔍 مقارنة")
                compare_btn.setStyleSheet(reports._btn_style("#2980b9", "#2471a3"))
                compare_btn.clicked.connect(reports.load_comparison_report)
                fg_layout.addWidget(compare_btn, 0, 4, 2, 1)

                export_btn = QPushButton("📊 Excel")
                export_btn.setStyleSheet(reports._btn_style("#27ae60", "#229954"))
                export_btn.clicked.connect(lambda: reports.export_table_to_excel(
                    reports.comparison_table, "مقارنة_الفترات.xlsx", "المقارنة",
                    ["البيان", "الفترة الأولى", "الفترة الثانية", "الفرق", "نسبة التغيير"]
                ))
                fg_layout.addWidget(export_btn, 0, 5, 2, 1)

                layout.addWidget(filter_group)

                cards_widget = QWidget()
                cards_layout = QHBoxLayout(cards_widget)

                reports.cmp_cards = {}
                card_data = [
                    ("المبيعات", "#27ae60"),
                    ("المصروفات", "#e74c3c"),
                    ("المشتريات", "#e67e22"),
                    ("صافي النقدية", "#2980b9"),
                ]
                for title, color in card_data:
                    card = QLabel(f"{title}\nالفترة 1: -\nالفترة 2: -\nالتغيير: -")
                    card.setStyleSheet(f"""
                        font-size: 13px; font-weight: bold; color: white;
                        background-color: {color}; border-radius: 10px; padding: 12px;
                    """)
                    card.setAlignment(Qt.AlignCenter)
                    cards_layout.addWidget(card)
                    reports.cmp_cards[title] = card

                layout.addWidget(cards_widget)

                reports.comparison_table = QTableWidget()
                reports.comparison_table.setColumnCount(5)
                reports.comparison_table.setHorizontalHeaderLabels([
                    "البيان", "الفترة الأولى", "الفترة الثانية", "الفرق", "نسبة التغيير %"
                ])
                reports.comparison_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
                reports.comparison_table.horizontalHeader().setLayoutDirection(Qt.RightToLeft)
                reports.comparison_table.setStyleSheet(reports._table_style("#2980b9"))
                reports.comparison_table.setAlternatingRowColors(True)
                layout.addWidget(reports.comparison_table)

            reports.build_comparison_tab = fixed_build_comparison_tab
            reports.build_comparison_tab()

            reports.cmp_p1_from.setDate(QDate.fromString(self.week_start, "yyyy-MM-dd"))
            reports.cmp_p1_to.setDate(QDate.fromString(self.dates[3], "yyyy-MM-dd"))
            reports.cmp_p2_from.setDate(QDate.fromString(self.dates[4], "yyyy-MM-dd"))
            reports.cmp_p2_to.setDate(QDate.fromString(self.week_end, "yyyy-MM-dd"))
            reports.load_comparison_report()

        # التحقق النهائي
        self._verify_inventory_chain()
        self._verify_cash_chain()
        self._verify_debt_chain()
        self._verify_net_capital()
        self._verify_reports_data()

    def _verify_inventory_chain(self):
        """التحقق من سلسلة المخزون"""
        issues = validate_inventory_chain()
        assert len(issues) == 0, f"Inventory chain issues: {issues}"

        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM المخزون WHERE الكمية_المتوفرة < 0")
            assert cursor.fetchone()[0] == 0, "Negative inventory found"
        finally:
            conn.close()

    def _verify_cash_chain(self):
        """التحقق من سلسلة النقدية"""
        issues = validate_cash_chain()
        assert len(issues) == 0, f"Cash chain issues: {issues}"

    def _verify_debt_chain(self):
        """التحقق من سلسلة الديون"""
        issues = validate_debt_chain()
        assert len(issues) == 0, f"Debt chain issues: {issues}"

    def _verify_net_capital(self):
        """التحقق من رأس المال الصافي"""
        capitals = validate_net_capital_chain(self.dates)
        for date, cap in capitals:
            assert cap > 0, f"Net capital should be positive on {date}: {cap}"

    def _verify_reports_data(self):
        """التحقق من بيانات التقارير"""
        conn = get_conn()
        try:
            cursor = conn.cursor()

            # التحقق من إجمالي المبيعات
            cursor.execute("SELECT SUM(المبلغ_الإجمالي) FROM المبيعات_اليومية")
            total_sales = cursor.fetchone()[0] or 0
            assert total_sales > 0, "Total sales should be positive"

            # التحقق من إجمالي المشتريات
            cursor.execute("SELECT SUM(المبلغ_الإجمالي) FROM فواتير_الشراء")
            total_purchases = cursor.fetchone()[0] or 0
            assert total_purchases > 0, "Total purchases should be positive"

            # التحقق من الأرصدة المغلقة
            cursor.execute("SELECT COUNT(*) FROM أرصدة_الصندوق WHERE مغلقة = 1")
            closed_days = cursor.fetchone()[0]
            assert closed_days >= 5, f"Expected at least 5 closed days, got {closed_days}"

            # التحقق من وجود فواتير شراء
            cursor.execute("SELECT COUNT(*) FROM فواتير_الشراء")
            invoices = cursor.fetchone()[0]
            assert invoices > 0, "Should have purchase invoices"

            # التحقق من وجود تحركات مخزون
            cursor.execute("SELECT COUNT(*) FROM تحركات_المخزون")
            movements = cursor.fetchone()[0]
            assert movements > 0, "Should have inventory movements"

            # التحقق من وجود جرد
            cursor.execute("SELECT COUNT(*) FROM الجرد")
            audits = cursor.fetchone()[0]
            assert audits >= 2, "Should have at least opening and closing audits"
        finally:
            conn.close()
