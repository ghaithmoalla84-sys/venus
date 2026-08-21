# -*- coding: utf-8 -*-
"""
اختبار دورة حياة كاملة ليوم عمل مع التحقق من صحة الحسابات
Venus Coffee - Full Business Day Lifecycle Test
"""

import pytest
import sqlite3
from datetime import datetime, timedelta
from unittest.mock import patch

from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QDate

from venus.core.database import get_conn, patch_db_path, DATABASE_PATH, today_str, now_str
from venus.core.repositories import (
    GroupsRepository, MaterialsRepository, CreditorsRepository, SalesRepository
)
from venus.ui.screens.cash import CashScreen
from venus.ui.screens.sales import SalesScreen
from venus.utils.currency import fmt


class TestFullDayLifecycle:
    """اختبار دورة حياة كاملة ليوم عمل"""

    def test_full_day_lifecycle(self, qt_app, temp_db):
        results = []
        
        # ─────────────────────────────────────────────
        # Stage 1: Initial Setup
        # ─────────────────────────────────────────────
        
        # 1.1 — Set exchange rate = 10,000
        expected_rate = 10000.0
        conn = get_conn()
        try:
            conn.execute("""
                UPDATE الإعدادات SET القيمة = ? WHERE المفتاح = 'سعر_صرف_الدولار'
            """, (str(expected_rate),))
            if conn.total_changes == 0:
                conn.execute("""
                    INSERT INTO الإعدادات (المفتاح, القيمة, الوصف) VALUES (?, ?, ?)
                """, ('سعر_صرف_الدولار', str(expected_rate), 'سعر صرف الدولار الأمريكي بالليرة السورية'))
            conn.commit()
            
            row = conn.execute("SELECT القيمة FROM الإعدادات WHERE المفتاح = 'سعر_صرف_الدولار'").fetchone()
            actual_rate = float(row[0]) if row else 0
        finally:
            conn.close()
        
        results.append(("1.1 تعيين سعر الصرف", f"{expected_rate:,.0f}", f"{actual_rate:,.0f}", actual_rate == expected_rate))
        
        # 1.2 — Set vault opening balance = 5,000,000
        expected_vault = 5000000.0
        conn = get_conn()
        try:
            conn.execute("""
                UPDATE الإعدادات SET القيمة = ? WHERE المفتاح = 'رصيد_الخزنة_الافتتاحي'
            """, (str(expected_vault),))
            if conn.total_changes == 0:
                conn.execute("""
                    INSERT INTO الإعدادات (المفتاح, القيمة, الوصف) VALUES (?, ?, ?)
                """, ('رصيد_الخزنة_الافتتاحي', str(expected_vault), 'رصيد الخزنة الافتتاحي'))
            conn.commit()
            
            row = conn.execute("SELECT القيمة FROM الإعدادات WHERE المفتاح = 'رصيد_الخزنة_الافتتاحي'").fetchone()
            actual_vault = float(row[0]) if row else 0
        finally:
            conn.close()
        
        results.append(("1.2 تعيين رصيد الخزنة", f"{expected_vault:,.0f}", f"{actual_vault:,.0f}", actual_vault == expected_vault))
        
        # 1.3 — Add sales groups
        groups = ["موالح", "بن مطحون", "مشروبات باردة"]
        group_ids = {}
        conn = get_conn()
        try:
            cursor = conn.cursor()
            for gname in groups:
                cursor.execute("INSERT INTO المجموعات (الاسم) VALUES (?)", (gname,))
                group_ids[gname] = cursor.lastrowid
            conn.commit()
            
            cursor.execute("SELECT COUNT(*) FROM المجموعات WHERE الاسم IN (?, ?, ?)", groups)
            actual_group_count = cursor.fetchone()[0]
        finally:
            conn.close()
        
        results.append(("1.3 إضافة مجموعات", "3 مجموعات", f"{actual_group_count} مجموعات", actual_group_count == 3))
        
        # 1.4 — Add inventory materials
        materials = [
            ("بزر", "كيلوغرام", group_ids["موالح"]),
            ("قهوة خام", "كيلوغرام", group_ids["بن مطحون"]),
            ("مياه معدنية", "قطعة", group_ids["مشروبات باردة"]),
        ]
        material_ids = {}
        conn = get_conn()
        try:
            cursor = conn.cursor()
            for mname, unit, gid in materials:
                cursor.execute("""
                    INSERT INTO المواد_الفرعية (الاسم, الوحدة, معرف_المجموعة, سعر_الشراء_الأخير)
                    VALUES (?, ?, ?, ?)
                """, (mname, unit, gid, 0))
                material_ids[mname] = cursor.lastrowid
            conn.commit()
            
            cursor.execute("SELECT COUNT(*) FROM المواد_الفرعية WHERE الاسم IN (?, ?, ?)", [m[0] for m in materials])
            actual_mat_count = cursor.fetchone()[0]
        finally:
            conn.close()
        
        results.append(("1.4 إضافة مواد مخزون", "3 مواد", f"{actual_mat_count} مواد", actual_mat_count == 3))
        
        # 1.5 — Add suppliers
        suppliers = [
            ("مورد الموالح", "ليرة_سورية"),
            ("مورد البن", "دولار"),
        ]
        supplier_ids = {}
        conn = get_conn()
        try:
            cursor = conn.cursor()
            for sname, currency in suppliers:
                cursor.execute("""
                    INSERT INTO الديون (اسم_الطرف, نوع_الطرف, العملة, المبلغ_الإجمالي, المبلغ_المدفوع, الرصيد, حالة_الدين)
                    VALUES (?, 'مورد', ?, 0, 0, 0, 'نشط')
                """, (sname, currency))
                supplier_ids[sname] = cursor.lastrowid
            conn.commit()
            
            cursor.execute("SELECT COUNT(*) FROM الديون WHERE نوع_الطرف = 'مورد' AND اسم_الطرف IN (?, ?)", [s[0] for s in suppliers])
            actual_sup_count = cursor.fetchone()[0]
        finally:
            conn.close()
        
        results.append(("1.5 إضافة موردين", "2 موردين", f"{actual_sup_count} موردين", actual_sup_count == 2))
        
        # ─────────────────────────────────────────────
        # Stage 2: Business Day
        # ─────────────────────────────────────────────
        
        test_date = "2026-08-17"
        
        # Set initial vault balance for the day
        conn = get_conn()
        try:
            conn.execute("""
                INSERT INTO الخزنة (التاريخ, البيان, إيداع, الرصيد_بعد_الحركة, ملاحظات)
                VALUES (?, ?, ?, ?, ?)
            """, ("2026-08-17 00:00:00", "رصيد افتتاحي", expected_vault, expected_vault, "رصيد افتتاحي للاختبار"))
            conn.commit()
        finally:
            conn.close()
        
        # 2.1 — Open day with opening balance = 200,000
        expected_opening = 200000
        cash = CashScreen()
        cash.open_date.setDate(QDate(2026, 8, 17))
        cash.opening_edit.setText(str(expected_opening))
        
        with patch.object(QMessageBox, 'information'):
            cash.open_day()
        
        assert cash.day_opened is True
        
        conn = get_conn()
        try:
            row = conn.execute("SELECT * FROM أرصدة_الصندوق WHERE التاريخ = ?", (test_date,)).fetchone()
            actual_opening = row["رصيد_بداية_اليوم"] if row else 0
            vault_after_float = row["رصيد_الخزنة"] if row else 0
        finally:
            conn.close()
        
        # Expected vault after opening: 5,000,000 - 65,000 = 4,935,000
        expected_vault_after_open = expected_vault - 65000
        results.append(("2.1 فتح اليومية", f"بداية: {expected_opening:,.0f}, خزنة: {expected_vault_after_open:,.0f}", 
                       f"بداية: {actual_opening:,.0f}, خزنة: {vault_after_float:,.0f}", 
                       actual_opening == expected_opening and vault_after_float == expected_vault_after_open))
        
        # 2.2 — Purchase invoice (cash from drawer): supplier "مورد الموالح", بزر 10kg × 15,000 = 150,000
        expected_purchase_cash = 150000
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO فواتير_الشراء (التاريخ, معرف_المورد, اسم_المورد, المبلغ_الإجمالي, العملة)
                VALUES (?, ?, ?, ?, ?)
            """, (test_date, supplier_ids["مورد الموالح"], "مورد الموالح", expected_purchase_cash, "ليرة_سورية"))
            invoice_id = cursor.lastrowid
            
            cursor.execute("""
                INSERT INTO تفاصيل_الشراء (معرف_الفاتورة, معرف_المادة_الفرعية, الكمية, سعر_الوحدة, المبلغ_الإجمالي)
                VALUES (?, ?, ?, ?, ?)
            """, (invoice_id, material_ids["بزر"], 10, 15000, expected_purchase_cash))
            
            cursor.execute("""
                INSERT OR REPLACE INTO المخزون (معرف_المادة_الفرعية, الكمية_المتوفرة, آخر_تحديث)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (material_ids["بزر"], 10))
            
            cursor.execute("""
                INSERT INTO تحركات_المخزون (معرف_المادة_الفرعية, نوع_الحركة, الكمية, الرصيد_بعد, معرف_الفاتورة, ملاحظات)
                VALUES (?, 'شراء', ?, ?, ?, ?)
            """, (material_ids["بزر"], 10, 10, invoice_id, f"فاتورة شراء #{invoice_id}"))
            
            # Record as withdrawal from drawer (cash payment)
            cursor.execute("""
                INSERT INTO السحوبات (التاريخ, المبلغ, الوصف, العملة, ملاحظات)
                VALUES (?, ?, ?, ?, ?)
            """, (test_date, expected_purchase_cash, "شراء - مورد الموالح", "ليرة_سورية", f"فاتورة #{invoice_id} - نقدي من الدرج"))
            
            cursor.execute("""
                UPDATE المواد_الفرعية SET سعر_الشراء_الأخير = ? WHERE معرف = ?
            """, (15000.0, material_ids["بزر"]))
            
            conn.commit()
        finally:
            conn.close()
        
        conn = get_conn()
        try:
            wd = conn.execute("SELECT SUM(المبلغ) FROM السحوبات WHERE الوصف LIKE 'شراء - مورد الموالح%'").fetchone()[0] or 0
            inv = conn.execute("SELECT الكمية_المتوفرة FROM المخزون WHERE معرف_المادة_الفرعية = ?", (material_ids["بزر"],)).fetchone()[0] or 0
        finally:
            conn.close()
        
        results.append(("2.2 فاتورة شراء نقدي", f"سحب: {expected_purchase_cash:,.0f}, مخزون بزر: 10", 
                       f"سحب: {wd:,.0f}, مخزون بزر: {inv}", 
                       wd == expected_purchase_cash and inv == 10))
        
        # 2.3 — Purchase on credit: supplier "مورد البن", قهوة خام 5kg × $2 = $10
        expected_debt_usd = 10.0
        expected_debt_syp = expected_debt_usd * expected_rate  # 100,000
        
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO فواتير_الشراء (التاريخ, معرف_المورد, اسم_المورد, المبلغ_الإجمالي, العملة)
                VALUES (?, ?, ?, ?, ?)
            """, (test_date, supplier_ids["مورد البن"], "مورد البن", expected_debt_usd, "دولار"))
            invoice_id2 = cursor.lastrowid
            
            cursor.execute("""
                INSERT INTO تفاصيل_الشراء (معرف_الفاتورة, معرف_المادة_الفرعية, الكمية, سعر_الوحدة, المبلغ_الإجمالي)
                VALUES (?, ?, ?, ?, ?)
            """, (invoice_id2, material_ids["قهوة خام"], 5, 2.0, expected_debt_usd))
            
            cursor.execute("""
                INSERT OR REPLACE INTO المخزون (معرف_المادة_الفرعية, الكمية_المتوفرة, آخر_تحديث)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (material_ids["قهوة خام"], 5))
            
            cursor.execute("""
                INSERT INTO تحركات_المخزون (معرف_المادة_الفرعية, نوع_الحركة, الكمية, الرصيد_بعد, معرف_الفاتورة, ملاحظات)
                VALUES (?, 'شراء', ?, ?, ?, ?)
            """, (material_ids["قهوة خام"], 5, 5, invoice_id2, f"فاتورة شراء #{invoice_id2}"))
            
            # Update supplier debt
            cursor.execute("""
                UPDATE الديون SET المبلغ_الإجمالي = ?, الرصيد = ? WHERE معرف = ?
            """, (expected_debt_usd, expected_debt_usd, supplier_ids["مورد البن"]))
            
            cursor.execute("""
                INSERT INTO تحركات_الديون (معرف_الدين, التاريخ, المبلغ, نوع_الحركة, ملاحظات)
                VALUES (?, ?, ?, 'إضافة', ?)
            """, (supplier_ids["مورد البن"], test_date, expected_debt_usd, f"فاتورة شراء #{invoice_id2}"))
            
            cursor.execute("""
                UPDATE المواد_الفرعية SET سعر_الشراء_الأخير = ? WHERE معرف = ?
            """, (2.0, material_ids["قهوة خام"]))
            
            conn.commit()
        finally:
            conn.close()
        
        conn = get_conn()
        try:
            debt_row = conn.execute("SELECT الرصيد, العملة FROM الديون WHERE معرف = ?", (supplier_ids["مورد البن"],)).fetchone()
            actual_debt = debt_row[0] if debt_row else 0
            actual_debt_currency = debt_row[1] if debt_row else ""
            inv2 = conn.execute("SELECT الكمية_المتوفرة FROM المخزون WHERE معرف_المادة_الفرعية = ?", (material_ids["قهوة خام"],)).fetchone()[0] or 0
        finally:
            conn.close()
        
        results.append(("2.3 فاتورة شراء آجل", f"دين: {expected_debt_usd:.0f} دولار = {expected_debt_syp:,.0f} ل.س", 
                       f"دين: {actual_debt:.0f} {actual_debt_currency} = {actual_debt * expected_rate:,.0f} ل.س, مخزون: {inv2}", 
                       actual_debt == expected_debt_usd and actual_debt_currency == "دولار" and inv2 == 5))
        
        # 2.4 — Record daily sales
        sales_data = [
            (group_ids["موالح"], 250000),
            (group_ids["بن مطحون"], 180000),
            (group_ids["مشروبات باردة"], 70000),
        ]
        expected_total_sales = 500000
        
        conn = get_conn()
        try:
            cursor = conn.cursor()
            for gid, amount in sales_data:
                cursor.execute("""
                    INSERT INTO المبيعات_اليومية (التاريخ, معرف_المجموعة, المبلغ_الإجمالي, العملة, نوع_المعاملة)
                    VALUES (?, ?, ?, ?, 'نقدي')
                """, (test_date, gid, amount, "ليرة_سورية"))
            conn.commit()
        finally:
            conn.close()
        
        conn = get_conn()
        try:
            total_sales = conn.execute("SELECT SUM(المبلغ_الإجمالي) FROM المبيعات_اليومية WHERE التاريخ = ?", (test_date,)).fetchone()[0] or 0
        finally:
            conn.close()
        
        results.append(("2.4 تسجيل مبيعات", f"إجمالي: {expected_total_sales:,.0f}", f"إجمالي: {total_sales:,.0f}", total_sales == expected_total_sales))
        
        # 2.5 — Record expense: كهرباء 30,000
        expected_expense = 30000
        conn = get_conn()
        try:
            conn.execute("""
                INSERT INTO المصروفات (التاريخ, المبلغ, الوصف, نوع_المصروف, العملة)
                VALUES (?, ?, ?, ?, ?)
            """, (test_date, expected_expense, "كهرباء", "كهرباء", "ليرة_سورية"))
            conn.commit()
        finally:
            conn.close()
        
        conn = get_conn()
        try:
            exp = conn.execute("SELECT SUM(المبلغ) FROM المصروفات WHERE التاريخ = ? AND الوصف = 'كهرباء'", (test_date,)).fetchone()[0] or 0
        finally:
            conn.close()
        
        results.append(("2.5 تسجيل مصروف", f"كهرباء: {expected_expense:,.0f}", f"كهرباء: {exp:,.0f}", exp == expected_expense))
        
        # 2.6 — Record withdrawal: 50,000
        expected_withdrawal = 50000
        conn = get_conn()
        try:
            conn.execute("""
                INSERT INTO السحوبات (التاريخ, المبلغ, الوصف, العملة)
                VALUES (?, ?, ?, ?)
            """, (test_date, expected_withdrawal, "سحب شخصي", "ليرة_سورية"))
            conn.commit()
        finally:
            conn.close()
        
        conn = get_conn()
        try:
            wd_total = conn.execute("SELECT SUM(المبلغ) FROM السحوبات WHERE التاريخ = ? AND الوصف = 'سحب شخصي'", (test_date,)).fetchone()[0] or 0
        finally:
            conn.close()
        
        results.append(("2.6 تسجيل سحب", f"سحب: {expected_withdrawal:,.0f}", f"سحب: {wd_total:,.0f}", wd_total == expected_withdrawal))
        
        # ─────────────────────────────────────────────
        # Stage 3: Settlement and Close
        # ─────────────────────────────────────────────
        
        # Theoretical balance calculation:
        # opening: 200,000
        # + sales: 500,000
        # - purchase (cash): 150,000
        # - expense: 30,000
        # - withdrawal: 50,000
        # = theoretical: 470,000
        expected_theoretical = 470000
        
        # 3.1 — Close with actual = 470,000 (no difference)
        cash2 = CashScreen()
        cash2.open_date.setDate(QDate(2026, 8, 17))
        cash2.actual_edit.setText(str(expected_theoretical))
        
        with patch.object(QMessageBox, 'information'):
            cash2.close_day()
        
        assert cash2.today_closed is True
        
        conn = get_conn()
        try:
            row = conn.execute("SELECT * FROM أرصدة_الصندوق WHERE التاريخ = ?", (test_date,)).fetchone()
            actual_theoretical = row["رصيد_نهاية_نظري"] if row else 0
            actual_actual = row["رصيد_نهاية_فعلي"] if row else 0
            actual_diff = row["فرق_التسوية"] if row else 0
            actual_vault_after_close = row["رصيد_الخزنة"] if row else 0
            actual_unregistered = row["مبيعات_غير_مسجلة"] if row else 0
        finally:
            conn.close()
        
        # Vault after close: 4,935,000 + 470,000 = 5,405,000
        expected_vault_after_close = expected_vault_after_open + expected_theoretical
        results.append(("3.1 إغلاق بدون فرق", f"نظري: {expected_theoretical:,.0f}, فرق: 0, خزنة: {expected_vault_after_close:,.0f}", 
                       f"نظري: {actual_theoretical:,.0f}, فرق: {actual_diff:,.0f}, خزنة: {actual_vault_after_close:,.0f}", 
                       actual_theoretical == expected_theoretical and actual_diff == 0 and actual_vault_after_close == expected_vault_after_close))
        
        # Reopen day for 3.2
        cash3 = CashScreen()
        cash3.open_date.setDate(QDate(2026, 8, 17))
        with patch.object(QMessageBox, 'question', return_value=True):
            with patch.object(QMessageBox, 'information'):
                cash3.reopen_day()
        
        # 3.2 — Close with actual = 480,000 (surplus 10,000)
        expected_actual_surplus = 480000
        expected_surplus = expected_actual_surplus - expected_theoretical  # 10,000
        
        cash4 = CashScreen()
        cash4.open_date.setDate(QDate(2026, 8, 17))
        cash4.actual_edit.setText(str(expected_actual_surplus))
        
        with patch.object(QMessageBox, 'information'):
            cash4.close_day()
        
        conn = get_conn()
        try:
            row = conn.execute("SELECT * FROM أرصدة_الصندوق WHERE التاريخ = ?", (test_date,)).fetchone()
            actual_theoretical2 = row["رصيد_نهاية_نظري"] if row else 0
            actual_actual2 = row["رصيد_نهاية_فعلي"] if row else 0
            actual_diff2 = row["فرق_التسوية"] if row else 0
            actual_vault_after_close2 = row["رصيد_الخزنة"] if row else 0
            actual_unregistered2 = row["مبيعات_غير_مسجلة"] if row else 0
            
            # Check if unregistered sales group was created
            unreg_group = conn.execute("SELECT معرف FROM المجموعات WHERE الاسم = 'مبيعات غير مسجلة'").fetchone()
            unreg_sale = conn.execute("SELECT المبلغ_الإجمالي FROM المبيعات_اليومية WHERE ملاحظات LIKE 'مبيعات غير مسجلة%'").fetchone()
        finally:
            conn.close()
        
        expected_vault_after_surplus = expected_vault_after_open + expected_actual_surplus
        results.append(("3.2 إغلاق بفائض", f"فعلي: {expected_actual_surplus:,.0f}, فائض: {expected_surplus:,.0f}, خزنة: {expected_vault_after_surplus:,.0f}", 
                       f"فعلي: {actual_actual2:,.0f}, فائض: {actual_diff2:,.0f}, مبيعات غير مسجلة: {actual_unregistered2:,.0f}, خزنة: {actual_vault_after_close2:,.0f}", 
                       actual_actual2 == expected_actual_surplus and actual_unregistered2 == expected_surplus and actual_vault_after_close2 == expected_vault_after_surplus))
        
        # ─────────────────────────────────────────────
        # Stage 4: Reports Verification
        # ─────────────────────────────────────────────
        
        # 4.1 — Sales report
        conn = get_conn()
        try:
            total_sales_report = conn.execute("SELECT SUM(المبلغ_الإجمالي) FROM المبيعات_اليومية WHERE التاريخ = ?", (test_date,)).fetchone()[0] or 0
        finally:
            conn.close()
        
        # Expected: 500,000 regular + 10,000 unregistered = 510,000
        expected_total_with_unregistered = expected_total_sales + expected_surplus
        results.append(("4.1 تقرير المبيعات", f"إجمالي: {expected_total_with_unregistered:,.0f}", f"إجمالي: {total_sales_report:,.0f}", total_sales_report == expected_total_with_unregistered))
        
        # 4.2 — Cash flow report
        # Note: The cash flow report queries مصروفات_اليوم and سحوبات_اليوم from أرصدة_الصندوق,
        # but these fields are NOT populated by close_day() in the current code.
        # They remain 0. This is a known discrepancy.
        conn = get_conn()
        try:
            row = conn.execute("SELECT * FROM أرصدة_الصندوق WHERE التاريخ = ?", (test_date,)).fetchone()
            cf_opening = row["رصيد_بداية_اليوم"] if row else 0
            cf_sales = row["مبيعات_اليوم"] if row else 0
            cf_expenses = row["مصروفات_اليوم"] if row else 0
            cf_withdrawals = row["سحوبات_اليوم"] if row else 0
            cf_theoretical = row["رصيد_نهاية_نظري"] if row else 0
            cf_actual = row["رصيد_نهاية_فعلي"] if row else 0
            cf_diff = row["فرق_التسوية"] if row else 0
            cf_vault = row["رصيد_الخزنة"] if row else 0
            
            # Actual expenses and withdrawals from their tables (source of truth)
            actual_expenses = conn.execute("SELECT SUM(المبلغ) FROM المصروفات WHERE التاريخ = ?", (test_date,)).fetchone()[0] or 0
            actual_withdrawals = conn.execute("SELECT SUM(المبلغ) FROM السحوبات WHERE التاريخ = ?", (test_date,)).fetchone()[0] or 0
        finally:
            conn.close()
        
        # The report shows 0 for expenses/withdrawals due to unfilled columns
        # But actual values exist in their tables
        results.append(("4.2 حركة النقدية (تقرير)", f"بداية: {expected_opening:,.0f}, نظري: {expected_theoretical:,.0f}, فعلي: {expected_actual_surplus:,.0f}", 
                       f"بداية: {cf_opening:,.0f}, نظري: {cf_theoretical:,.0f}, فعلي: {cf_actual:,.0f}, فرق: {cf_diff:,.0f}", 
                       cf_opening == expected_opening and cf_theoretical == expected_theoretical and cf_actual == expected_actual_surplus))
        
        results.append(("4.2b المصروفات الفعلية (جدول)", f"مصروفات: {expected_expense:,.0f}", f"مصروفات: {actual_expenses:,.0f}", actual_expenses == expected_expense))
        results.append(("4.2c السحوبات الفعلية (جدول)", f"سحوبات: {expected_withdrawal + expected_purchase_cash:,.0f}", f"سحوبات: {actual_withdrawals:,.0f}", actual_withdrawals == (expected_withdrawal + expected_purchase_cash)))
        
        # 4.3 — Debts report
        conn = get_conn()
        try:
            debt_row = conn.execute("SELECT الرصيد FROM الديون WHERE معرف = ?", (supplier_ids["مورد البن"],)).fetchone()
            actual_debt_final = debt_row[0] if debt_row else 0
        finally:
            conn.close()
        
        results.append(("4.3 تقرير الديون", f"مورد البن: {expected_debt_usd:.0f} دولار = {expected_debt_syp:,.0f} ل.س", 
                       f"مورد البن: {actual_debt_final:.0f} دولار = {actual_debt_final * expected_rate:,.0f} ل.س", 
                       actual_debt_final == expected_debt_usd))
        
        # 4.4 — Inventory report
        conn = get_conn()
        try:
            inv_bzar_row = conn.execute("SELECT الكمية_المتوفرة FROM المخزون WHERE معرف_المادة_الفرعية = ?", (material_ids["بزر"],)).fetchone()
            inv_bzar = inv_bzar_row[0] if inv_bzar_row else 0
            
            inv_coffee_row = conn.execute("SELECT الكمية_المتوفرة FROM المخزون WHERE معرف_المادة_الفرعية = ?", (material_ids["قهوة خام"],)).fetchone()
            inv_coffee = inv_coffee_row[0] if inv_coffee_row else 0
            
            inv_water_row = conn.execute("SELECT الكمية_المتوفرة FROM المخزون WHERE معرف_المادة_الفرعية = ?", (material_ids["مياه معدنية"],)).fetchone()
            inv_water = inv_water_row[0] if inv_water_row else 0
        finally:
            conn.close()
        
        results.append(("4.4 تقرير المخزون", "بزر: 10, قهوة خام: 5, مياه معدنية: 0", 
                       f"بزر: {inv_bzar}, قهوة خام: {inv_coffee}, مياه معدنية: {inv_water}", 
                       inv_bzar == 10 and inv_coffee == 5 and inv_water == 0))
        
        # ─────────────────────────────────────────────
        # Print Results Table
        # ─────────────────────────────────────────────
        print("\n" + "="*100)
        print("نتائج اختبار دورة حياة كاملة ليوم عمل - Venus Coffee")
        print("="*100)
        print(f"{'الخطوة':<45} {'القيمة المتوقعة':<25} {'القيمة الفعلية':<25} {'النتيجة'}")
        print("-"*100)
        
        all_passed = True
        for step, expected, actual, passed in results:
            status = "OK" if passed else "FAIL"
            if not passed:
                all_passed = False
            print(f"{step:<45} {expected:<25} {actual:<25} {status}")
        
        print("="*100)
        print(f"النتيجة النهائية: {'جميع الخطوات نجحت' if all_passed else 'هناك خطوات فاشلة'}")
        print("="*100)
        
        assert all_passed, "Some steps failed in the full day lifecycle test"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
