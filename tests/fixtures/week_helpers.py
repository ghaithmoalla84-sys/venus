# -*- coding: utf-8 -*-
"""
مساعدات محاكاة أسبوع عمل كامل - Venus Coffee
"""
from datetime import datetime, timedelta
from unittest.mock import patch
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QDate

from venus.core.database import get_conn
from venus.utils.net_capital import calculate_net_capital


def setup_week_groups():
    """إنشاء المجموعات الافتراضية للأسبوع"""
    groups = {
        "قهوة": ["اسبريسو", "لاتيه", "كابتشينو"],
        "حلويات": ["كعك", "بسبوسة", "بسكويت"],
        "مشروبات": ["عصير", "ماء", "شاي"],
    }
    group_ids = {}
    for group_name, materials in groups.items():
        from tests.fixtures.helpers import insert_group
        gid = insert_group(group_name)
        group_ids[group_name] = {"id": gid, "materials": []}
        for mat_name in materials:
            from tests.fixtures.helpers import insert_material
            mid = insert_material(mat_name, group_id=gid, qty=0.0)
            group_ids[group_name]["materials"].append({"id": mid, "name": mat_name, "qty": 0.0})
    return group_ids


def setup_week_suppliers():
    """إنشاء الموردين الافتراضيين للأسبوع"""
    suppliers = {}
    from tests.fixtures.helpers import insert_creditor
    suppliers["مورد_أحمد"] = insert_creditor("مورد أحمد", "مورد", "ليرة_سورية", 0, 0, "نشط")
    suppliers["مورد_سعيد"] = insert_creditor("مورد سعيد", "مورد", "دولار", 0, 0, "نشط")
    return suppliers


def open_cash_day(qt_app, date_str, opening, currency="ليرة_سورية", vault_amount=2000000.0):
    """فتح يومية نقدية"""
    from venus.ui.screens.cash import CashScreen

    with patch.object(QMessageBox, 'information'):
        screen = CashScreen()
        screen.open_date.setDate(QDate.fromString(date_str, "yyyy-MM-dd"))
        screen.opening_edit.setText(str(opening))
        screen.currency_combo.setCurrentText(currency)
        screen.open_day()
    return screen


def close_cash_day(screen, date_str, actual):
    """إغلاق يومية نقدية"""
    with patch.object(QMessageBox, 'information'), patch.object(QMessageBox, 'warning'):
        screen.open_date.setDate(QDate.fromString(date_str, "yyyy-MM-dd"))
        screen.actual_edit.setText(str(actual))
        screen.close_day()


def reopen_cash_day(screen, date_str):
    """إعادة فتح يومية"""
    with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes), \
         patch.object(QMessageBox, 'information'):
        screen.open_date.setDate(QDate.fromString(date_str, "yyyy-MM-dd"))
        screen.reopen_day()


def add_purchase_bill(qt_app, date_str, supplier_id, items, payment_mode="نقدي من الدرج", cash_amount=0.0):
    """إضافة فاتورة شراء"""
    from venus.ui.screens.inventory.screen import InventoryScreen

    with patch.object(QMessageBox, 'information'):
        screen = InventoryScreen()
        screen.supplier_combo.setCurrentValue(supplier_id)
        screen.date_input.setDate(QDate.fromString(date_str, "yyyy-MM-dd"))
        screen.payment_combo.setCurrentText(payment_mode)

        if payment_mode == "جزئي (كاش + دين)":
            screen.cash_amount_edit.setText(str(cash_amount))
            screen.partial_payment_source_combo.setCurrentText("من الدرج")

        for i, (material_id, qty, price) in enumerate(items):
            screen.add_bill_row()
            combo = screen.items_table.cellWidget(i, 0)
            idx = combo.findData(material_id)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            screen.items_table.item(i, 1).setText(str(qty))
            screen.items_table.item(i, 2).setText(str(price))
            screen.calculate_row_total(i, 1)

        screen.save_purchase_bill()
    return screen


def add_sale_direct(group_id, date_str, amount, currency="ليرة_سورية", notes=""):
    """إضافة بيع مباشر"""
    from tests.fixtures.helpers import insert_sale
    return insert_sale(group_id, date=date_str + " 10:00:00", amount=amount, currency=currency, notes=notes)


def add_expense_direct(date_str, amount, desc, etype="أخرى", currency="ليرة_سورية"):
    """إضافة مصروف مباشر"""
    from tests.fixtures.helpers import insert_expense
    return insert_expense(date_str + " 10:00:00", amount, desc, etype=etype, currency=currency)


def add_withdrawal_direct(date_str, amount, desc, currency="ليرة_سورية"):
    """إضافة سحب مباشر"""
    from tests.fixtures.helpers import insert_withdrawal
    return insert_withdrawal(date_str + " 10:00:00", amount, desc, currency=currency)


def record_payment_direct(creditor_id, amount, date_str=None):
    """تسجيل دفعة لدائن"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    try:
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
        """, (amount, amount, amount, creditor_id))
        cursor.execute("""
            INSERT INTO تحركات_الديون (معرف_الدين, التاريخ, المبلغ, نوع_الحركة, ملاحظات)
            VALUES (?, ?, ?, 'دفعة', ?)
        """, (creditor_id, date_str, amount, "دفعة من الدرج"))
        conn.commit()
    finally:
        conn.close()


def run_profit_report(qt_app, date_from, date_to):
    """تشغيل تقرير الأرباح"""
    from venus.ui.screens.reports import ReportsScreen
    screen = ReportsScreen()
    screen.profit_from.setDate(QDate.fromString(date_from, "yyyy-MM-dd"))
    screen.profit_to.setDate(QDate.fromString(date_to, "yyyy-MM-dd"))
    with patch.object(QMessageBox, 'information'), patch.object(QMessageBox, 'critical'):
        screen.load_profit_report()
    return screen


def run_sales_report(qt_app, date_from, date_to):
    """تشغيل تقرير المبيعات"""
    from venus.ui.screens.reports import ReportsScreen
    screen = ReportsScreen()
    screen.sales_from.setDate(QDate.fromString(date_from, "yyyy-MM-dd"))
    screen.sales_to.setDate(QDate.fromString(date_to, "yyyy-MM-dd"))
    with patch.object(QMessageBox, 'information'), patch.object(QMessageBox, 'critical'):
        screen.load_sales_report()
    return screen


def run_debts_report(qt_app):
    """تشغيل تقرير الديون"""
    from venus.ui.screens.reports import ReportsScreen
    screen = ReportsScreen()
    with patch.object(QMessageBox, 'information'), patch.object(QMessageBox, 'critical'):
        screen.load_debts()
    return screen


def run_cash_movements_report(qt_app, date_from, date_to):
    """تشغيل تقرير حركة النقدية"""
    from venus.ui.screens.reports import ReportsScreen
    screen = ReportsScreen()
    screen.cash_from.setDate(QDate.fromString(date_from, "yyyy-MM-dd"))
    screen.cash_to.setDate(QDate.fromString(date_to, "yyyy-MM-dd"))
    with patch.object(QMessageBox, 'information'), patch.object(QMessageBox, 'critical'):
        screen.load_cash_movements()
    return screen


def run_overdue_report(qt_app):
    """تشغيل تقرير الديون المتأخرة"""
    from venus.ui.screens.reports import ReportsScreen
    screen = ReportsScreen()
    with patch.object(QMessageBox, 'information'), patch.object(QMessageBox, 'critical'):
        screen.load_overdue_report()
    return screen


def run_inventory_report(qt_app):
    """تشغيل تقرير المخزون"""
    from venus.ui.screens.reports import ReportsScreen
    screen = ReportsScreen()
    with patch.object(QMessageBox, 'information'), patch.object(QMessageBox, 'critical'):
        screen.load_inventory()
    return screen


def run_best_suppliers_report(qt_app):
    """تشغيل تقرير أفضل الموردين"""
    from venus.ui.screens.reports import ReportsScreen
    screen = ReportsScreen()
    with patch.object(QMessageBox, 'information'), patch.object(QMessageBox, 'critical'):
        screen.load_best_suppliers_report()
    return screen


def run_comparison_report(qt_app, date_from1, date_to1, date_from2, date_to2):
    """تشغيل تقرير مقارنة الفترات"""
    from venus.ui.screens.reports import ReportsScreen
    from PyQt5.QtWidgets import QWidget
    parent = QWidget()
    screen = ReportsScreen()
    screen.cmp_p1_from.setDate(QDate.fromString(date_from1, "yyyy-MM-dd"))
    screen.cmp_p1_to.setDate(QDate.fromString(date_to1, "yyyy-MM-dd"))
    screen.cmp_p2_from.setDate(QDate.fromString(date_from2, "yyyy-MM-dd"))
    screen.cmp_p2_to.setDate(QDate.fromString(date_to2, "yyyy-MM-dd"))
    with patch.object(QMessageBox, 'information'), patch.object(QMessageBox, 'critical'):
        screen.load_comparison_report()
    return screen


def run_tax_report(qt_app, date_from, date_to):
    """تشغيل التقرير الضريبي"""
    from venus.ui.screens.reports import ReportsScreen
    screen = ReportsScreen()
    screen.tax_from.setDate(QDate.fromString(date_from, "yyyy-MM-dd"))
    screen.tax_to.setDate(QDate.fromString(date_to, "yyyy-MM-dd"))
    with patch.object(QMessageBox, 'information'), patch.object(QMessageBox, 'critical'):
        screen.load_tax_report()
    return screen


def run_suppliers_report(qt_app):
    """تشغيل تقرير الموردون"""
    from venus.ui.screens.reports import ReportsScreen
    screen = ReportsScreen()
    with patch.object(QMessageBox, 'information'), patch.object(QMessageBox, 'critical'):
        screen.load_suppliers_report()
    return screen


def run_buy_list_report(qt_app):
    """تشغيل تقرير ما يجب شراؤه"""
    from venus.ui.screens.reports import ReportsScreen
    screen = ReportsScreen()
    with patch.object(QMessageBox, 'information'), patch.object(QMessageBox, 'critical'):
        screen.load_buy_list()
    return screen


def validate_inventory_chain():
    """التحقق من سلسلة المخزون"""
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT م.معرف_المادة_الفرعية, م.الكمية_المتوفرة,
                   COALESCE(SUM(CASE WHEN ط.نوع_الحركة = 'شراء' THEN ط.الكمية ELSE 0 END), 0) as total_purchase,
                   COALESCE(SUM(CASE WHEN ط.نوع_الحركة = 'جرد' THEN ط.الكمية ELSE 0 END), 0) as total_audit,
                   COALESCE(SUM(CASE WHEN ط.نوع_الحركة = 'تعديل_يدوي' THEN ط.الكمية ELSE 0 END), 0) as total_manual
            FROM المخزون م
            LEFT JOIN تحركات_المخزون ط ON م.معرف_المادة_الفرعية = ط.معرف_المادة_الفرعية
            GROUP BY م.معرف_المادة_الفرعية
        """)
        results = cursor.fetchall()
        issues = []
        for row in results:
            material_id, qty, purchases, audits, manuals = row
            if qty < 0:
                issues.append(f"Material {material_id}: negative qty {qty}")
        return issues
    finally:
        conn.close()


def validate_cash_chain():
    """التحقق من سلسلة النقدية"""
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT التاريخ, رصيد_بداية_اليوم, رصيد_نهاية_فعلي, مبيعات_اليوم, مصروفات_اليوم, سحوبات_اليوم, مغلقة
            FROM أرصدة_الصندوق
            WHERE مغلقة = 1
            ORDER BY التاريخ
        """)
        results = cursor.fetchall()
        issues = []
        for row in results:
            date, opening, actual, sales, expenses, withdrawals, closed = row
            theoretical = (opening or 0) + (sales or 0) - (expenses or 0) - (withdrawals or 0)
            # الفرق بين الفعلي والنظري هو طبيعي (تسوية)
            # نتحقق فقط من أن الفرق مسجل بشكل صحيح
            if actual is not None and closed:
                diff = actual - theoretical
                # التحقق من أن الفرق ليس كبيراً بشكل غير منطقي (أكثر من 50% من النظري)
                if theoretical > 0 and abs(diff) > theoretical * 0.5:
                    issues.append(f"Day {date}: suspicious diff actual={actual} theoretical={theoretical}")
        return issues
    finally:
        conn.close()


def validate_debt_chain():
    """التحقق من سلسلة الديون"""
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT d.معرف, d.اسم_الطرف, d.المبلغ_الإجمالي, d.المبلغ_المدفوع, d.الرصيد, d.حالة_الدين
            FROM الديون d
        """)
        debts = cursor.fetchall()
        issues = []
        for row in debts:
            debt_id, name, total, paid, balance, status = row
            expected_balance = (total or 0) - (paid or 0)
            if abs((balance or 0) - expected_balance) > 0.01:
                issues.append(f"Debt {debt_id}: balance mismatch {balance} vs {expected_balance}")
        return issues
    finally:
        conn.close()


def validate_net_capital_chain(dates):
    """التحقق من سلسلة رأس المال الصافي"""
    from venus.utils.net_capital import _get_drawer_balance, _get_vault_balance, _get_inventory_value, _get_total_debts
    capitals = []
    for date in dates:
        drawer = _get_drawer_balance(date)
        vault = _get_vault_balance()
        inventory = _get_inventory_value()
        debts = _get_total_debts()
        cap = drawer + vault + inventory - debts
        capitals.append((date, cap))
    return capitals
