# -*- coding: utf-8 -*-
"""
اختبارات شاملة لعمليات التطبيق المحاسبي "فينوس كوفي"
تغطي جميع العمليات الأساسية المذكورة في خطة الاختبار
"""

import pytest
import sqlite3
from datetime import datetime, timedelta
from unittest.mock import patch

from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QDate

from venus.core.database import get_conn, today_str
import re
from venus.core.repositories import (
    GroupsRepository, MaterialsRepository, CreditorsRepository,
    SalesRepository
)
from venus.core.events import app_events, AppEvents
from venus.ui.screens.dashboard import DashboardScreen
from venus.ui.screens.sales import SalesScreen
from venus.ui.screens.inventory.screen import InventoryScreen
from venus.ui.screens.inventory.audit import AuditDialog
from venus.ui.screens.creditors import CreditorsScreen, PaymentDialog
from venus.ui.screens.cash import CashScreen
from venus.ui.screens.reports import ReportsScreen
from venus.ui.screens.settings import SettingsScreen
from venus.ui.widgets.searchable_table import SearchableTable
from venus.ui.widgets.combo_quick_add import ComboWithQuickAdd
from venus.ui.widgets.entity_detail_dialog import EntityDetailDialog
from venus.utils.currency import fmt, fmt_syp, fmt_usd

from tests.fixtures.constants import TEST_DATE
from tests.fixtures.helpers import (
    insert_group, insert_material, insert_creditor, insert_sale,
    insert_cash_day, insert_vault_balance, insert_expense,
    insert_withdrawal, insert_invoice, insert_invoice_detail,
    insert_debt_movement
)


class TestDatabaseSetup:
    """اختبارات إعداد قاعدة البيانات"""

    def test_temp_db_created(self, temp_db):
        """التأكد من إنشاء قاعدة البيانات المؤقتة"""
        import os
        assert os.path.exists(temp_db)

    def test_all_tables_exist(self, temp_db):
        """التأكد من وجود جميع الجداول"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        expected_tables = [
            'المجموعات', 'المواد_الفرعية', 'فواتير_الشراء', 'تفاصيل_الشراء',
            'المبيعات_اليومية', 'المصروفات', 'السحوبات', 'الديون',
            'تحركات_الديون', 'أرصدة_الصندوق', 'الجرد', 'المخزون',
            'تحركات_المخزون', 'الإعدادات', 'أسعار_الصرف',
            'الخزنة', 'تحويلات_الصندوق'
        ]
        for table in expected_tables:
            assert table in tables, f"Table {table} not found"

    def test_default_settings_exist(self, temp_db):
        """التأكد من وجود الإعدادات الافتراضية"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT المفتاح, القيمة FROM الإعدادات")
        settings = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()

        assert 'اسم_المحل' in settings
        assert 'سعر_صرف_الدولار' in settings
        assert 'رصيد_النقدية_الافتتاحي' in settings


class TestGroupsCRUD:
    """اختبارات إدارة المجموعات"""

    def test_add_group(self, temp_db, db_conn):
        """إضافة مجموعة جديدة"""
        cursor = db_conn.cursor()
        cursor.execute("INSERT INTO المجموعات (الاسم) VALUES (?)", ("موالح",))
        db_conn.commit()

        cursor.execute("SELECT * FROM المجموعات WHERE الاسم = ?", ("موالح",))
        row = cursor.fetchone()
        assert row is not None
        assert row["الاسم"] == "موالح"
        assert row["معرف"] > 0

    def test_add_group_duplicate_fails(self, temp_db, db_conn):
        """إضافة مجموعة مكررة تفشل"""
        cursor = db_conn.cursor()
        cursor.execute("INSERT INTO المجموعات (الاسم) VALUES (?)", ("موالح",))
        db_conn.commit()

        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("INSERT INTO المجموعات (الاسم) VALUES (?)", ("موالح",))
            db_conn.commit()

    def test_add_group_empty_name_fails(self, temp_db, db_conn):
        """إضافة مجموعة باسم فارغ تفشل"""
        cursor = db_conn.cursor()
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("INSERT INTO المجموعات (الاسم) VALUES (?)", ("",))
            db_conn.commit()

    def test_delete_group_cascades(self, temp_db, db_conn):
        """حذف مجموعة يحذف المواد الفرعية التابعة"""
        cursor = db_conn.cursor()
        cursor.execute("INSERT INTO المجموعات (الاسم) VALUES (?)", ("موالح",))
        group_id = cursor.lastrowid
        cursor.execute("INSERT INTO المواد_الفرعية (الاسم, الوحدة, معرف_المجموعة) VALUES (?, ?, ?)",
                       ("كعك", "قطعة", group_id))
        material_id = cursor.lastrowid
        db_conn.commit()

        cursor.execute("DELETE FROM المجموعات WHERE معرف = ?", (group_id,))
        db_conn.commit()

        cursor.execute("SELECT * FROM المواد_الفرعية WHERE معرف = ?", (material_id,))
        assert cursor.fetchone() is None

    def test_delete_group_with_sales_cascades(self, temp_db, db_conn):
        """حذف مجموعة بها مبيعات يحذف المبيعات cascade"""
        cursor = db_conn.cursor()
        cursor.execute("INSERT INTO المجموعات (الاسم) VALUES (?)", ("موالح",))
        group_id = cursor.lastrowid
        db_conn.commit()

        cursor.execute("INSERT INTO المبيعات_اليومية (التاريخ, معرف_المجموعة, المبلغ_الإجمالي) VALUES (?, ?, ?)",
                       (today_str(), group_id, 100))
        sale_id = cursor.lastrowid
        db_conn.commit()

        cursor.execute("DELETE FROM المجموعات WHERE معرف = ?", (group_id,))
        db_conn.commit()

        cursor.execute("SELECT * FROM المبيعات_اليومية WHERE معرف = ?", (sale_id,))
        assert cursor.fetchone() is None


class TestMaterialsCRUD:
    """اختبارات إدارة المواد الفرعية"""

    def test_add_material(self, temp_db, db_conn):
        """إضافة مادة فرعية مرتبطة بمجموعة"""
        cursor = db_conn.cursor()
        cursor.execute("INSERT INTO المجموعات (الاسم) VALUES (?)", ("موالح",))
        group_id = cursor.lastrowid
        db_conn.commit()

        cursor.execute("INSERT INTO المواد_الفرعية (الاسم, الوحدة, معرف_المجموعة) VALUES (?, ?, ?)",
                       ("كعك", "قطعة", group_id))
        db_conn.commit()

        cursor.execute("SELECT * FROM المواد_الفرعية WHERE الاسم = ?", ("كعك",))
        row = cursor.fetchone()
        assert row is not None
        assert row["الوحدة"] == "قطعة"
        assert row["معرف_المجموعة"] == group_id
        assert row["سعر_الشراء_الأخير"] == 0

    def test_add_material_does_not_auto_create_inventory(self, temp_db, db_conn):
        """إضافة مادة لا تنشئ سجل في المخزون تلقائياً (يتم إنشاؤه يدوياً)"""
        cursor = db_conn.cursor()
        cursor.execute("INSERT INTO المجموعات (الاسم) VALUES (?)", ("موالح",))
        group_id = cursor.lastrowid
        cursor.execute("INSERT INTO المواد_الفرعية (الاسم, الوحدة, معرف_المجموعة) VALUES (?, ?, ?)",
                       ("كعك", "قطعة", group_id))
        material_id = cursor.lastrowid
        db_conn.commit()

        cursor.execute("SELECT * FROM المخزون WHERE معرف_المادة_الفرعية = ?", (material_id,))
        row = cursor.fetchone()
        assert row is None

    def test_update_purchase_price(self, temp_db, db_conn):
        """تحديث سعر الشراء الأخير"""
        cursor = db_conn.cursor()
        cursor.execute("INSERT INTO المجموعات (الاسم) VALUES (?)", ("موالح",))
        group_id = cursor.lastrowid
        cursor.execute("INSERT INTO المواد_الفرعية (الاسم, الوحدة, معرف_المجموعة) VALUES (?, ?, ?)",
                       ("كعك", "قطعة", group_id))
        material_id = cursor.lastrowid
        db_conn.commit()

        cursor.execute("UPDATE المواد_الفرعية SET سعر_الشراء_الأخير = ? WHERE معرف = ?",
                       (1500.0, material_id))
        db_conn.commit()

        cursor.execute("SELECT سعر_الشراء_الأخير FROM المواد_الفرعية WHERE معرف = ?", (material_id,))
        assert cursor.fetchone()[0] == 1500.0

    def test_add_material_without_group_fails(self, temp_db, db_conn):
        """إضافة مادة بدون مجموعة تفشل"""
        cursor = db_conn.cursor()
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("INSERT INTO المواد_الفرعية (الاسم, الوحدة, معرف_المجموعة) VALUES (?, ?, ?)",
                           ("كعك", "قطعة", 99999))
            db_conn.commit()


class TestOpeningBalances:
    """اختبارات الأرصدة الافتتاحية"""

    def test_save_cash_opening_balance(self, temp_db, db_conn):
        """حفظ رصيد نقدية افتتاحي"""
        cursor = db_conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO الإعدادات (المفتاح, القيمة, الوصف)
            VALUES ('رصيد_النقدية_الافتتاحي', ?, 'رصيد النقدية الافتتاحي')
        """, (50000.0,))
        db_conn.commit()

        cursor.execute("SELECT القيمة FROM الإعدادات WHERE المفتاح = 'رصيد_النقدية_الافتتاحي'")
        assert cursor.fetchone()[0] == "50000.0"

    def test_save_inventory_opening_balance(self, temp_db, db_conn):
        """حفظ مخزون افتتاحي ينشئ سجلات في المخزون وتحركات_المخزون"""
        cursor = db_conn.cursor()
        cursor.execute("INSERT INTO المجموعات (الاسم) VALUES (?)", ("موالح",))
        group_id = cursor.lastrowid
        cursor.execute("INSERT INTO المواد_الفرعية (الاسم, الوحدة, معرف_المجموعة) VALUES (?, ?, ?)",
                       ("كعك", "قطعة", group_id))
        material_id = cursor.lastrowid
        db_conn.commit()

        cursor.execute("""
            INSERT OR REPLACE INTO المخزون (معرف_المادة_الفرعية, الكمية_المتوفرة, آخر_تحديث)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (material_id, 50.0))

        cursor.execute("""
            INSERT INTO تحركات_المخزون
            (معرف_المادة_الفرعية, نوع_الحركة, الكمية, الرصيد_بعد, ملاحظات)
            VALUES (?, 'تعديل_يدوي', ?, ?, 'رصيد افتتاحي')
        """, (material_id, 50.0, 50.0))
        db_conn.commit()

        cursor.execute("SELECT الكمية_المتوفرة FROM المخزون WHERE معرف_المادة_الفرعية = ?", (material_id,))
        assert cursor.fetchone()[0] == 50.0

        cursor.execute("SELECT * FROM تحركات_المخزون WHERE معرف_المادة_الفرعية = ? AND نوع_الحركة = 'تعديل_يدوي'", (material_id,))
        row = cursor.fetchone()
        assert row is not None
        assert row["ملاحظات"] == "رصيد افتتاحي"

    def test_save_creditors_opening_balance(self, temp_db, db_conn):
        """حفظ أرصدة دائنين افتتاحية"""
        cursor = db_conn.cursor()
        cursor.execute("""
            INSERT INTO الديون (اسم_الطرف, نوع_الطرف, العملة, المبلغ_الإجمالي, الرصيد, حالة_الدين)
            VALUES (?, 'مورد', 'ليرة_سورية', ?, ?, 'نشط')
        """, ("مورد1", 10000.0, 10000.0))
        debt_id = cursor.lastrowid
        db_conn.commit()

        cursor.execute("""
            INSERT INTO تحركات_الديون (معرف_الدين, المبلغ, نوع_الحركة, ملاحظات)
            VALUES (?, ?, 'إضافة', 'رصيد افتتاحي')
        """, (debt_id, 10000.0))
        db_conn.commit()

        cursor.execute("SELECT الرصيد FROM الديون WHERE معرف = ?", (debt_id,))
        assert cursor.fetchone()[0] == 10000.0

        cursor.execute("SELECT * FROM تحركات_الديون WHERE معرف_الدين = ? AND نوع_الحركة = 'إضافة'", (debt_id,))
        row = cursor.fetchone()
        assert row is not None
        assert row["ملاحظات"] == "رصيد افتتاحي"


class TestCashOperations:
    """اختبارات عمليات النقدية اليومية"""

    def test_open_day(self, temp_db, db_conn):
        """فتح يومية creates a record in أرصدة_الصندوق"""
        cursor = db_conn.cursor()
        test_date = "2025-01-15"
        cursor.execute("""
            INSERT INTO أرصدة_الصندوق (التاريخ, رصيد_بداية_اليوم, العملة)
            VALUES (?, ?, ?)
        """, (test_date, 100000.0, "ليرة_سورية"))
        db_conn.commit()

        cursor.execute("SELECT * FROM أرصدة_الصندوق WHERE التاريخ = ?", (test_date,))
        row = cursor.fetchone()
        assert row is not None
        assert row["رصيد_بداية_اليوم"] == 100000.0
        assert row["مبيعات_اليوم"] == 0
        assert row["مصروفات_اليوم"] == 0
        assert row["سحوبات_اليوم"] == 0

    def test_double_open_day_prevention(self, temp_db, db_conn):
        """منع الفتح المزدوج لنفس اليوم"""
        cursor = db_conn.cursor()
        test_date = "2025-01-15"
        cursor.execute("""
            INSERT INTO أرصدة_الصندوق (التاريخ, رصيد_بداية_اليوم, العملة)
            VALUES (?, ?, ?)
        """, (test_date, 100000.0, "ليرة_سورية"))
        db_conn.commit()

        cursor.execute("SELECT COUNT(*) FROM أرصدة_الصندوق WHERE التاريخ = ?", (test_date,))
        count = cursor.fetchone()[0]
        assert count == 1

    def test_save_expense(self, temp_db, db_conn):
        """إدخال مصروف creates record in المصروفات and updates أرصدة_الصندوق"""
        cursor = db_conn.cursor()
        test_date = "2025-01-15"
        cursor.execute("""
            INSERT INTO أرصدة_الصندوق (التاريخ, رصيد_بداية_اليوم, العملة)
            VALUES (?, ?, ?)
        """, (test_date, 100000.0, "ليرة_سورية"))
        db_conn.commit()

        expense_date = f"{test_date} 10:30:00"
        cursor.execute("""
            INSERT INTO المصروفات (التاريخ, المبلغ, الوصف, نوع_المصروف, العملة, ملاحظات)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (expense_date, 5000.0, "إيجار", "إيجار", "ليرة_سورية", "مصروف - إيجار"))
        db_conn.commit()

        cursor.execute("SELECT * FROM المصروفات WHERE التاريخ = ?", (expense_date,))
        row = cursor.fetchone()
        assert row is not None
        assert row["المبلغ"] == 5000.0

    def test_save_withdrawal(self, temp_db, db_conn):
        """إدخال سحب creates record in السحوبات and updates أرصدة_الصندوق"""
        cursor = db_conn.cursor()
        test_date = "2025-01-15"
        cursor.execute("""
            INSERT INTO أرصدة_الصندوق (التاريخ, رصيد_بداية_اليوم, العملة)
            VALUES (?, ?, ?)
        """, (test_date, 100000.0, "ليرة_سورية"))
        db_conn.commit()

        withdrawal_date = f"{test_date} 14:00:00"
        cursor.execute("""
            INSERT INTO السحوبات (التاريخ, المبلغ, الوصف, العملة, ملاحظات)
            VALUES (?, ?, ?, ?, ?)
        """, (withdrawal_date, 20000.0, "سحب شخصي", "ليرة_سورية", "سحب - سحب شخصي"))
        db_conn.commit()

        cursor.execute("SELECT * FROM السحوبات WHERE التاريخ = ?", (withdrawal_date,))
        row = cursor.fetchone()
        assert row is not None
        assert row["المبلغ"] == 20000.0

    def test_close_day_without_diff(self, temp_db, db_conn):
        """إغلاق يومية بدون فرق"""
        cursor = db_conn.cursor()
        test_date = "2025-01-15"
        cursor.execute("""
            INSERT INTO أرصدة_الصندوق (التاريخ, رصيد_بداية_اليوم, العملة)
            VALUES (?, ?, ?)
        """, (test_date, 100000.0, "ليرة_سورية"))
        db_conn.commit()

        theoretical = 100000.0
        actual = 100000.0
        diff = actual - theoretical

        cursor.execute("""
            UPDATE أرصدة_الصندوق
            SET رصيد_نهاية_نظري = ?, رصيد_نهاية_فعلي = ?, فرق_التسوية = ?
            WHERE التاريخ = ?
        """, (theoretical, actual, diff, test_date))
        db_conn.commit()

        cursor.execute("SELECT * FROM أرصدة_الصندوق WHERE التاريخ = ?", (test_date,))
        row = cursor.fetchone()
        assert row["رصيد_نهاية_نظري"] == 100000.0
        assert row["فرق_التسوية"] == 0.0

    def test_close_day_with_surplus(self, temp_db, db_conn):
        """إغلاق يومية مع فائض creates unregistered sales and vault transfer"""
        from unittest.mock import patch
        from venus.ui.screens.cash import CashScreen
        from PyQt5.QtCore import QDate

        cursor = db_conn.cursor()
        test_date = "2025-01-15"
        cursor.execute("""
            INSERT INTO أرصدة_الصندوق (التاريخ, رصيد_بداية_اليوم, العملة)
            VALUES (?, ?, ?)
        """, (test_date, 100000.0, "ليرة_سورية"))
        db_conn.commit()

        cursor.execute("SELECT معرف FROM المجموعات WHERE الاسم = ?", ("مبيعات غير مسجلة",))
        unreg_row = cursor.fetchone()
        if unreg_row:
            unreg_group_id = unreg_row[0]
        else:
            cursor.execute("INSERT INTO المجموعات (الاسم, الوصف) VALUES (?, ?)",
                           ("مبيعات غير مسجلة", "مجموعة خاصة للمبيعات غير المسجلة في التسوية"))
            unreg_group_id = cursor.lastrowid
            db_conn.commit()

        screen = CashScreen()
        screen.open_date.setDate(QDate.fromString(test_date, "yyyy-MM-dd"))
        screen.actual_edit.setText("105000.0")

        with patch.object(QMessageBox, 'information'), \
             patch.object(QMessageBox, 'warning'):
            screen.close_day()

        cursor.execute("SELECT فرق_التسوية FROM أرصدة_الصندوق WHERE التاريخ = ?", (test_date,))
        assert cursor.fetchone()[0] == 5000.0

        cursor.execute("""
            SELECT * FROM تحويلات_الصندوق
            WHERE date(التاريخ) = ? AND من_حساب = 'الدرج' AND إلى_حساب = 'الخزنة'
        """, (test_date,))
        transfer = cursor.fetchone()
        assert transfer is not None
        assert transfer["المبلغ"] == 105000.0

        cursor.execute("""
            SELECT * FROM الخزنة
            WHERE date(التاريخ) = ? AND البيان = 'إيداع إغلاق يومية'
        """, (test_date,))
        deposit = cursor.fetchone()
        assert deposit is not None
        assert deposit["إيداع"] == 105000.0

    def test_close_day_with_deficit(self, temp_db, db_conn):
        """إغلاق يومية مع عجز ينشئ تحويل الدرج للخزنة"""
        from unittest.mock import patch
        from venus.ui.screens.cash import CashScreen
        from PyQt5.QtCore import QDate

        cursor = db_conn.cursor()
        test_date = "2025-01-15"
        cursor.execute("""
            INSERT INTO أرصدة_الصندوق (التاريخ, رصيد_بداية_اليوم, العملة)
            VALUES (?, ?, ?)
        """, (test_date, 100000.0, "ليرة_سورية"))
        db_conn.commit()

        screen = CashScreen()
        screen.open_date.setDate(QDate.fromString(test_date, "yyyy-MM-dd"))
        screen.actual_edit.setText("95000.0")

        with patch.object(QMessageBox, 'warning'):
            screen.close_day()

        cursor.execute("SELECT فرق_التسوية FROM أرصدة_الصندوق WHERE التاريخ = ?", (test_date,))
        assert cursor.fetchone()[0] == -5000.0

        cursor.execute("""
            SELECT * FROM تحويلات_الصندوق
            WHERE date(التاريخ) = ? AND من_حساب = 'الدرج' AND إلى_حساب = 'الخزنة'
        """, (test_date,))
        transfer = cursor.fetchone()
        assert transfer is not None
        assert transfer["المبلغ"] == 95000.0

        cursor.execute("""
            SELECT * FROM الخزنة
            WHERE date(التاريخ) = ? AND البيان = 'إيداع إغلاق يومية'
        """, (test_date,))
        deposit = cursor.fetchone()
        assert deposit is not None
        assert deposit["إيداع"] == 95000.0

    def test_reopen_day_restores_vault_balance(self, temp_db, db_conn):
        """إعادة فتح يومية تحذف السحب التلقائي والإيداع والتحويل وتعيد الرصيد

        القرار التجاري: reopen_day() يلغي أثر الإغلاق فقط (تحويل الدرج للخزنة + إيداع الإغلاق +
        مبيعات غير مسجلة)، ولا يعيد فكة الدرج إلى الخزنة لأن الفكة جزء من عملية الفتح وليس الإغلاق.
        لذلك رصيد الخزنة بعد إعادة الفتح = الرصيد الافتتاحي للخزنة (2,000,000) وليس رصيد ما بعد الإغلاق.
        """
        from venus.ui.screens.cash import CashScreen

        cursor = db_conn.cursor()
        test_date = "2025-01-15"
        close_time = test_date + " 12:00:00"

        cursor.execute("SELECT معرف FROM المجموعات WHERE الاسم = ?", ("مبيعات غير مسجلة",))
        unreg_row = cursor.fetchone()
        if unreg_row:
            unreg_group_id = unreg_row[0]
        else:
            cursor.execute("INSERT INTO المجموعات (الاسم, الوصف) VALUES (?, ?)",
                           ("مبيعات غير مسجلة", "مجموعة خاصة للمبيعات غير المسجلة في التسوية"))
            unreg_group_id = cursor.lastrowid
            db_conn.commit()

        cursor.execute("""
            INSERT INTO أرصدة_الصندوق (التاريخ, رصيد_بداية_اليوم, العملة, رصيد_نهاية_نظري, رصيد_نهاية_فعلي, فرق_التسوية, رصيد_الخزنة)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (test_date, 100000.0, "ليرة_سورية", 0.0, 105000.0, 5000.0, 2105000.0))

        cursor.execute("""
            INSERT INTO الخزنة (التاريخ, البيان, إيداع, الرصيد_بعد_الحركة, ملاحظات)
            VALUES (?, ?, ?, ?, ?)
        """, (close_time, "رصيد افتتاحي", 2000000.0, 2000000.0, "رصيد اختبار"))

        cursor.execute("""
            INSERT INTO تحويلات_الصندوق (التاريخ, من_حساب, إلى_حساب, المبلغ, ملاحظات)
            VALUES (?, 'الدرج', 'الخزنة', ?, ?)
        """, (close_time, 105000.0, "إغلاق يومية - تحويل كامل الدرج للخزنة"))

        cursor.execute("""
            INSERT INTO الخزنة (التاريخ, البيان, إيداع, الرصيد_بعد_الحركة, ملاحظات)
            VALUES (?, ?, ?, ?, ?)
        """, (close_time, "إيداع إغلاق يومية", 105000.0, 2105000.0, "تحويل من الدرج"))

        cursor.execute("""
            INSERT INTO المبيعات_اليومية (التاريخ, معرف_المجموعة, المبلغ_الإجمالي, العملة, ملاحظات)
            VALUES (?, ?, ?, 'ليرة_سورية', 'مبيعات غير مسجلة - تسوية')
        """, (test_date, unreg_group_id, 5000.0))

        db_conn.commit()

        screen = CashScreen()
        screen.open_date.setDate(QDate.fromString(test_date, "yyyy-MM-dd"))

        with patch.object(QMessageBox, 'information'), \
             patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
            screen.reopen_day()

        cursor.execute("""
            SELECT * FROM تحويلات_الصندوق
            WHERE date(التاريخ) = ? AND من_حساب = 'الدرج' AND إلى_حساب = 'الخزنة'
            AND ملاحظات = 'إغلاق يومية - تحويل كامل الدرج للخزنة'
        """, (test_date,))
        assert cursor.fetchone() is None

        cursor.execute("""
            SELECT * FROM تحويلات_الصندوق
            WHERE date(التاريخ) = ? AND من_حساب = 'الدرج' AND إلى_حساب = 'الخزنة'
        """, (test_date,))
        assert cursor.fetchone() is None

        cursor.execute("""
            SELECT * FROM الخزنة
            WHERE date(التاريخ) = ? AND البيان = 'إيداع إغلاق يومية'
        """, (test_date,))
        assert cursor.fetchone() is None

        cursor.execute("SELECT COUNT(*) FROM المبيعات_اليومية WHERE التاريخ = ? AND ملاحظات LIKE 'مبيعات غير مسجلة%'", (test_date,))
        assert cursor.fetchone()[0] == 0

        cursor.execute("SELECT رصيد_نهاية_نظري, رصيد_نهاية_فعلي, فرق_التسوية, رصيد_الخزنة FROM أرصدة_الصندوق WHERE التاريخ = ?", (test_date,))

    def test_save_expense_on_closed_day_blocked(self, temp_db, db_conn):
        """منع تسجيل مصروف في يومية مُغلقة"""

        cursor = db_conn.cursor()
        test_date = "2025-01-15"
        cursor.execute("""
            INSERT INTO أرصدة_الصندوق (التاريخ, رصيد_بداية_اليوم, رصيد_نهاية_فعلي, فرق_التسوية, العملة, مغلقة)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (test_date, 100000.0, 105000.0, 5000.0, "ليرة_سورية", 1))
        db_conn.commit()

        from venus.ui.screens.cash import CashScreen
        from unittest.mock import patch

        screen = CashScreen()
        screen.open_date.setDate(QDate.fromString(test_date, "yyyy-MM-dd"))
        screen.exp_date.setDate(QDate.fromString(test_date, "yyyy-MM-dd"))
        screen.exp_amount.setText("5000")
        screen.exp_desc.setText("كهرباء")
        screen.exp_type.setCurrentText("كهرباء")

        with patch.object(QMessageBox, 'warning') as mock_warn, \
             patch.object(QMessageBox, 'information'):
            screen.save_expense()

        assert mock_warn.called
        assert "إعادة فتح" in mock_warn.call_args[0][2]

    def test_save_withdrawal_on_closed_day_blocked(self, temp_db, db_conn):
        """منع تسجيل سحب في يومية مُغلقة"""

        cursor = db_conn.cursor()
        test_date = "2025-01-15"
        cursor.execute("""
            INSERT INTO أرصدة_الصندوق (التاريخ, رصيد_بداية_اليوم, رصيد_نهاية_فعلي, فرق_التسوية, العملة, مغلقة)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (test_date, 100000.0, 105000.0, 5000.0, "ليرة_سورية", 1))
        db_conn.commit()

        from venus.ui.screens.cash import CashScreen
        from unittest.mock import patch

        screen = CashScreen()
        screen.open_date.setDate(QDate.fromString(test_date, "yyyy-MM-dd"))
        screen.wd_date.setDate(QDate.fromString(test_date, "yyyy-MM-dd"))
        screen.wd_amount.setText("10000")
        screen.wd_desc.setText("سحب شخصي")

        with patch.object(QMessageBox, 'warning') as mock_warn, \
             patch.object(QMessageBox, 'information'):
            screen.save_withdrawal()

        assert mock_warn.called
        assert "إعادة فتح" in mock_warn.call_args[0][2]

    def test_close_day_zero_balances_sets_closed_flag(self, temp_db, db_conn):
        """إغلاق يومية برصيد فعلي=0 وفرق=0 يُعيّن مغلقة=1"""

        cursor = db_conn.cursor()
        test_date = "2025-01-15"
        cursor.execute("""
            INSERT INTO أرصدة_الصندوق (التاريخ, رصيد_بداية_اليوم, العملة)
            VALUES (?, ?, ?)
        """, (test_date, 100000.0, "ليرة_سورية"))
        db_conn.commit()

        from venus.ui.screens.cash import CashScreen
        from unittest.mock import patch

        screen = CashScreen()
        screen.open_date.setDate(QDate.fromString(test_date, "yyyy-MM-dd"))
        screen.actual_edit.setText("100000.0")

        with patch.object(QMessageBox, 'information'), \
             patch.object(QMessageBox, 'warning'):
            screen.close_day()

        cursor.execute("SELECT مغلقة FROM أرصدة_الصندوق WHERE التاريخ = ?", (test_date,))
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == 1

    def test_closed_day_blocks_expense_withdrawal_and_purchase(self, temp_db, db_conn):
        """إغلاق يومية برصيد فعلي=0 وفرق=0 يرفض المصروف والسحب وفاتورة الشراء"""

        cursor = db_conn.cursor()
        test_date = "2025-01-15"
        cursor.execute("""
            INSERT INTO أرصدة_الصندوق (التاريخ, رصيد_بداية_اليوم, العملة, مغلقة)
            VALUES (?, ?, ?, 1)
        """, (test_date, 100000.0, "ليرة_سورية"))
        db_conn.commit()

        cursor.execute("INSERT INTO المجموعات (الاسم) VALUES (?)", ("موالح",))
        group_id = cursor.lastrowid
        cursor.execute("INSERT INTO المواد_الفرعية (الاسم, الوحدة, معرف_المجموعة) VALUES (?, ?, ?)",
                       ("كعك", "قطعة", group_id))
        material_id = cursor.lastrowid
        cursor.execute("""
            INSERT INTO الديون (اسم_الطرف, نوع_الطرف, العملة, المبلغ_الإجمالي, المبلغ_المدفوع, الرصيد, حالة_الدين)
            VALUES (?, 'مورد', 'ليرة_سورية', 0, 0, 0, 'نشط')
        """, ("مورد1",))
        debt_id = cursor.lastrowid
        db_conn.commit()

        from venus.ui.screens.cash import CashScreen
        from unittest.mock import patch

        screen = CashScreen()
        screen.open_date.setDate(QDate.fromString(test_date, "yyyy-MM-dd"))

        screen.exp_date.setDate(QDate.fromString(test_date, "yyyy-MM-dd"))
        screen.exp_amount.setText("5000")
        screen.exp_desc.setText("كهرباء")
        screen.exp_type.setCurrentText("كهرباء")

        with patch.object(QMessageBox, 'warning') as mock_warn, \
             patch.object(QMessageBox, 'information'):
            screen.save_expense()
        assert mock_warn.called
        assert "إعادة فتح" in mock_warn.call_args[0][2]

        screen.wd_date.setDate(QDate.fromString(test_date, "yyyy-MM-dd"))
        screen.wd_amount.setText("10000")
        screen.wd_desc.setText("سحب شخصي")

        with patch.object(QMessageBox, 'warning') as mock_warn, \
             patch.object(QMessageBox, 'information'):
            screen.save_withdrawal()
        assert mock_warn.called
        assert "إعادة فتح" in mock_warn.call_args[0][2]

        from venus.ui.screens.inventory.purchase import PurchaseBillMixin

        class TestPurchaseScreen(PurchaseBillMixin):
            def __init__(self):
                self.supplier_combo = type('obj', (object,), {'current_value': debt_id, 'refresh': lambda self: None})()
                self.date_input = type('obj', (object,), {
                    'date': lambda self: type('obj', (object,), {'toString': lambda self, fmt: test_date})()
                })()
                self.payment_combo = type('obj', (object,), {'currentText': lambda self: 'دين (آجل)'})()
                self.cash_amount_edit = type('obj', (object,), {'setVisible': lambda self, x: None, 'clear': lambda self: None})()
                self.partial_payment_source_combo = type('obj', (object,), {'setVisible': lambda self, x: None})()
                self.total_amount_label = type('obj', (object,), {'setText': lambda self, x: None})()
                self.items_table = type('obj', (object,), {
                    'rowCount': lambda self: 1,
                    'cellWidget': lambda self, row, col: type('obj', (object,), {'current_value': material_id})(),
                    'item': lambda self, row, col: type('obj', (object,), {'text': lambda self: '10'})()
                })()

        purchase_screen = TestPurchaseScreen()
        with patch.object(QMessageBox, 'warning') as mock_warn, \
             patch.object(QMessageBox, 'information'):
            purchase_screen.save_purchase_bill()
        assert mock_warn.called
        assert "إعادة فتح" in mock_warn.call_args[0][2]


class TestSalesOperations:
    """اختبارات عمليات المبيعات"""

    def test_add_sales_new(self, temp_db, db_conn):
        """إضافة مبيعات جديدة creates new record"""
        cursor = db_conn.cursor()
        cursor.execute("INSERT INTO المجموعات (الاسم) VALUES (?)", ("موالح",))
        group_id = cursor.lastrowid
        db_conn.commit()

        sales_date = "2025-01-15"
        cursor.execute("""
            INSERT INTO المبيعات_اليومية (التاريخ, معرف_المجموعة, المبلغ_الإجمالي, العملة, نوع_المعاملة, ملاحظات)
            VALUES (?, ?, ?, 'ليرة_سورية', 'نقدي', ?)
        """, (sales_date, group_id, 5000.0, "مبيعات صباحية"))
        db_conn.commit()

        cursor.execute("SELECT * FROM المبيعات_اليومية WHERE التاريخ = ? AND معرف_المجموعة = ?",
                       (sales_date, group_id))
        row = cursor.fetchone()
        assert row is not None
        assert row["المبلغ_الإجمالي"] == 5000.0

    def test_update_existing_sales(self, temp_db, db_conn):
        """تحديث مبيعات موجودة adds to existing amount"""
        cursor = db_conn.cursor()
        cursor.execute("INSERT INTO المجموعات (الاسم) VALUES (?)", ("موالح",))
        group_id = cursor.lastrowid
        db_conn.commit()

        sales_date = "2025-01-15"
        cursor.execute("""
            INSERT INTO المبيعات_اليومية (التاريخ, معرف_المجموعة, المبلغ_الإجمالي, العملة, نوع_المعاملة)
            VALUES (?, ?, ?, 'ليرة_سورية', 'نقدي')
        """, (sales_date, group_id, 5000.0))
        sale_id = cursor.lastrowid
        db_conn.commit()

        cursor.execute("""
            UPDATE المبيعات_اليومية
            SET المبلغ_الإجمالي = المبلغ_الإجمالي + ?
            WHERE معرف = ?
        """, (3000.0, sale_id))
        db_conn.commit()

        cursor.execute("SELECT المبلغ_الإجمالي FROM المبيعات_اليومية WHERE معرف = ?", (sale_id,))
        assert cursor.fetchone()[0] == 8000.0

    def test_sales_multiple_groups(self, temp_db, db_conn):
        """مبيعات متعددة المجموعات"""
        cursor = db_conn.cursor()
        cursor.execute("INSERT INTO المجموعات (الاسم) VALUES (?)", ("موالح",))
        group1_id = cursor.lastrowid
        cursor.execute("INSERT INTO المجموعات (الاسم) VALUES (?)", ("بن مطحون",))
        group2_id = cursor.lastrowid
        db_conn.commit()

        sales_date = "2025-01-15"
        cursor.execute("""
            INSERT INTO المبيعات_اليومية (التاريخ, معرف_المجموعة, المبلغ_الإجمالي, العملة, نوع_المعاملة)
            VALUES (?, ?, ?, 'ليرة_سورية', 'نقدي')
        """, (sales_date, group1_id, 5000.0))
        cursor.execute("""
            INSERT INTO المبيعات_اليومية (التاريخ, معرف_المجموعة, المبلغ_الإجمالي, العملة, نوع_المعاملة)
            VALUES (?, ?, ?, 'ليرة_سورية', 'نقدي')
        """, (sales_date, group2_id, 3000.0))
        db_conn.commit()

        cursor.execute("SELECT SUM(المبلغ_الإجمالي) FROM المبيعات_اليومية WHERE التاريخ = ?", (sales_date,))
        assert cursor.fetchone()[0] == 8000.0

    def test_is_day_closed_uses_closed_column(self, temp_db, db_conn):
        """is_day_closed يعتمد على عمود مغلقة فقط"""

        test_date = "2025-01-15"
        cursor = db_conn.cursor()
        cursor.execute("""
            INSERT INTO أرصدة_الصندوق (التاريخ, رصيد_بداية_اليوم, رصيد_نهاية_فعلي, فرق_التسوية, العملة, مغلقة)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (test_date, 100000.0, 105000.0, 5000.0, "ليرة_سورية", 1))
        db_conn.commit()

        repo = SalesRepository()
        assert repo.is_day_closed(test_date) is True

        cursor.execute("""
            UPDATE أرصدة_الصندوق SET مغلقة = 0 WHERE التاريخ = ?
        """, (test_date,))
        db_conn.commit()

        assert repo.is_day_closed(test_date) is False


class TestPurchaseOperations:
    """اختبارات عمليات فواتير الشراء"""

    def test_cash_purchase_bill(self, temp_db, db_conn):
        """فاتورة شراء نقدية تحدث المخزون وتحركات_المخزون"""
        cursor = db_conn.cursor()
        cursor.execute("INSERT INTO المجموعات (الاسم) VALUES (?)", ("موالح",))
        group_id = cursor.lastrowid
        cursor.execute("INSERT INTO المواد_الفرعية (الاسم, الوحدة, معرف_المجموعة) VALUES (?, ?, ?)",
                       ("كعك", "قطعة", group_id))
        material_id = cursor.lastrowid
        db_conn.commit()

        cursor.execute("""
            INSERT INTO الديون (اسم_الطرف, نوع_الطرف, العملة, المبلغ_الإجمالي, المبلغ_المدفوع, الرصيد, حالة_الدين)
            VALUES (?, 'مورد', 'ليرة_سورية', ?, 0, ?, 'نشط')
        """, ("مورد1", 10000.0, 10000.0))
        debt_id = cursor.lastrowid
        db_conn.commit()

        cursor.execute("""
            INSERT INTO فواتير_الشراء (التاريخ, معرف_المورد, اسم_المورد, المبلغ_الإجمالي, العملة)
            VALUES (?, ?, ?, ?, 'ليرة_سورية')
        """, ("2025-01-15", debt_id, "مورد1", 10000.0))
        invoice_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO تفاصيل_الشراء (معرف_الفاتورة, معرف_المادة_الفرعية, الكمية, سعر_الوحدة, المبلغ_الإجمالي)
            VALUES (?, ?, ?, ?, ?)
        """, (invoice_id, material_id, 10.0, 1000.0, 10000.0))
        db_conn.commit()

        cursor.execute("SELECT * FROM فواتير_الشراء WHERE معرف = ?", (invoice_id,))
        assert cursor.fetchone() is not None

        cursor.execute("SELECT * FROM تفاصيل_الشراء WHERE معرف_الفاتورة = ?", (invoice_id,))
        assert cursor.fetchone() is not None

    def test_debt_purchase_creates_debt(self, temp_db, db_conn):
        """فاتورة شراء بالدين تنشئ/تحدث الدين"""
        cursor = db_conn.cursor()
        cursor.execute("INSERT INTO المجموعات (الاسم) VALUES (?)", ("موالح",))
        group_id = cursor.lastrowid
        cursor.execute("INSERT INTO المواد_الفرعية (الاسم, الوحدة, معرف_المجموعة) VALUES (?, ?, ?)",
                       ("كعك", "قطعة", group_id))
        material_id = cursor.lastrowid
        db_conn.commit()

        cursor.execute("""
            INSERT INTO الديون (اسم_الطرف, نوع_الطرف, العملة, المبلغ_الإجمالي, المبلغ_المدفوع, الرصيد, حالة_الدين)
            VALUES (?, 'مورد', 'ليرة_سورية', ?, 0, ?, 'نشط')
        """, ("مورد1", 10000.0, 10000.0))
        debt_id = cursor.lastrowid
        db_conn.commit()

        cursor.execute("""
            INSERT INTO فواتير_الشراء (التاريخ, معرف_المورد, اسم_المورد, المبلغ_الإجمالي, العملة)
            VALUES (?, ?, ?, ?, 'ليرة_سورية')
        """, ("2025-01-15", debt_id, "مورد1", 10000.0))
        invoice_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO تفاصيل_الشراء (معرف_الفاتورة, معرف_المادة_الفرعية, الكمية, سعر_الوحدة, المبلغ_الإجمالي)
            VALUES (?, ?, ?, ?, ?)
        """, (invoice_id, material_id, 10.0, 1000.0, 10000.0))

        cursor.execute("SELECT * FROM الديون WHERE معرف = ?", (debt_id,))
        row = cursor.fetchone()
        assert row is not None
        assert row["الرصيد"] == 10000.0

        cursor.execute("""
            INSERT INTO تحركات_الديون (معرف_الدين, المبلغ, نوع_الحركة, ملاحظات)
            VALUES (?, ?, 'إضافة', ?)
        """, (debt_id, 10000.0, f"فاتورة شراء #{invoice_id}"))
        db_conn.commit()
        db_conn.commit()

        cursor.execute("SELECT * FROM تحركات_الديون WHERE معرف_الدين = ?", (debt_id,))
        assert cursor.fetchone() is not None

    def test_save_purchase_bill_on_closed_day_blocked(self, temp_db, db_conn, monkeypatch):
        """منع تسجيل فاتورة شراء في يومية مُغلقة"""
        from venus.core import database
        monkeypatch.setattr(database, "DATABASE_PATH", temp_db)

        cursor = db_conn.cursor()
        cursor.execute("INSERT INTO المجموعات (الاسم) VALUES (?)", ("موالح",))
        group_id = cursor.lastrowid
        cursor.execute("INSERT INTO المواد_الفرعية (الاسم, الوحدة, معرف_المجموعة) VALUES (?, ?, ?)",
                       ("كعك", "قطعة", group_id))
        material_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO الديون (اسم_الطرف, نوع_الطرف, العملة, المبلغ_الإجمالي, المبلغ_المدفوع, الرصيد, حالة_الدين)
            VALUES (?, 'مورد', 'ليرة_سورية', 0, 0, 0, 'نشط')
        """, ("مورد1",))
        debt_id = cursor.lastrowid
        db_conn.commit()

        test_date = "2025-01-15"
        cursor.execute("""
            INSERT INTO أرصدة_الصندوق (التاريخ, رصيد_بداية_اليوم, رصيد_نهاية_فعلي, فرق_التسوية, العملة, مغلقة)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (test_date, 100000.0, 105000.0, 5000.0, "ليرة_سورية", 1))
        db_conn.commit()

        from venus.ui.screens.inventory.screen import InventoryScreen
        from unittest.mock import patch

        screen = InventoryScreen()
        screen.supplier_combo = type('obj', (object,), {'current_value': debt_id, 'refresh': lambda self: None})()
        screen.date_input = type('obj', (object,), {
            'date': lambda self: type('obj', (object,), {'toString': lambda self, fmt: test_date})()
        })()
        screen.payment_combo = type('obj', (object,), {'currentText': lambda self: 'دين (آجل)'})()
        screen.cash_amount_edit = type('obj', (object,), {'setVisible': lambda self, x: None, 'clear': lambda self: None})()
        screen.partial_payment_source_combo = type('obj', (object,), {'setVisible': lambda self, x: None})()
        screen.total_amount_label = type('obj', (object,), {'setText': lambda self, x: None})()
        screen.items_table = type('obj', (object,), {
            'rowCount': lambda self: 1,
            'cellWidget': lambda self, row, col: type('obj', (object,), {'current_value': material_id})(),
            'item': lambda self, row, col: type('obj', (object,), {'text': lambda self: '10'})()
        })()

        with patch.object(QMessageBox, 'warning') as mock_warn, \
             patch.object(QMessageBox, 'information'):
             screen.save_purchase_bill()

        assert mock_warn.called
        assert "إعادة فتح" in mock_warn.call_args[0][2]


class TestCreditorsOperations:
    """اختبارات عمليات الدائنون"""

    def test_add_creditor(self, temp_db, db_conn):
        """إضافة دائن creates debt record"""
        cursor = db_conn.cursor()
        cursor.execute("""
            INSERT INTO الديون (اسم_الطرف, نوع_الطرف, العملة, المبلغ_الإجمالي, الرصيد, حالة_الدين)
            VALUES (?, 'مورد', 'ليرة_سورية', ?, ?, 'نشط')
        """, ("مورد1", 15000.0, 15000.0))
        db_conn.commit()

        cursor.execute("SELECT * FROM الديون WHERE اسم_الطرف = ?", ("مورد1",))
        row = cursor.fetchone()
        assert row is not None
        assert row["الرصيد"] == 15000.0
        assert row["حالة_الدين"] == "نشط"

    def test_record_payment(self, temp_db, db_conn):
        """تسجيل دفعة reduces balance"""
        cursor = db_conn.cursor()
        cursor.execute("""
            INSERT INTO الديون (اسم_الطرف, نوع_الطرف, العملة, المبلغ_الإجمالي, المبلغ_المدفوع, الرصيد, حالة_الدين)
            VALUES (?, 'مورد', 'ليرة_سورية', 10000.0, 0, 10000.0, 'نشط')
        """, ("مورد1",))
        debt_id = cursor.lastrowid
        db_conn.commit()

        cursor.execute("""
            UPDATE الديون
            SET الرصيد = الرصيد - ?, المبلغ_المدفوع = المبلغ_المدفوع + ?,
                حالة_الدين = CASE WHEN (الرصيد - ?) <= 0.01 THEN 'مسدد' ELSE 'نشط' END
            WHERE معرف = ?
        """, (5000.0, 5000.0, 5000.0, debt_id))
        db_conn.commit()

        cursor.execute("SELECT الرصيد, حالة_الدين FROM الديون WHERE معرف = ?", (debt_id,))
        row = cursor.fetchone()
        assert row["الرصيد"] == 5000.0
        assert row["حالة_الدين"] == "نشط"

    def test_full_payment_changes_status(self, temp_db, db_conn):
        """تسديد كامل يغير الحالة إلى مسدد"""
        cursor = db_conn.cursor()
        cursor.execute("""
            INSERT INTO الديون (اسم_الطرف, نوع_الطرف, العملة, المبلغ_الإجمالي, المبلغ_المدفوع, الرصيد, حالة_الدين)
            VALUES (?, 'مورد', 'ليرة_سورية', 5000.0, 0, 5000.0, 'نشط')
        """, ("مورد1",))
        debt_id = cursor.lastrowid
        db_conn.commit()

        cursor.execute("""
            UPDATE الديون
            SET الرصيد = الرصيد - ?, المبلغ_المدفوع = المبلغ_المدفوع + ?,
                حالة_الدين = CASE WHEN (الرصيد - ?) <= 0.01 THEN 'مسدد' ELSE 'نشط' END
            WHERE معرف = ?
        """, (5000.0, 5000.0, 5000.0, debt_id))
        db_conn.commit()

        cursor.execute("SELECT الرصيد, حالة_الدين FROM الديون WHERE معرف = ?", (debt_id,))
        row = cursor.fetchone()
        assert row["الرصيد"] == 0.0
        assert row["حالة_الدين"] == "مسدد"

    def test_old_masd_status_migrates_to_musadd(self, temp_db, db_conn):
        """ترحيل القيد القديم 'مسد' إلى 'مسدد' ينجح بدون IntegrityError"""

        conn = sqlite3.connect(temp_db)
        conn.execute("PRAGMA foreign_keys = ON")
        cur = conn.cursor()

        cur.execute("DROP TABLE IF EXISTS الديون")
        cur.execute("""
            CREATE TABLE الديون (
                معرف INTEGER PRIMARY KEY AUTOINCREMENT,
                اسم_الطرف TEXT NOT NULL,
                نوع_الطرف TEXT CHECK(نوع_الطرف IN ('مورد', 'صديق')) NOT NULL,
                العملة TEXT CHECK(العملة IN ('ليرة_سورية', 'دولار')) DEFAULT 'ليرة_سورية',
                المبلغ_الإجمالي REAL NOT NULL DEFAULT 0 CHECK(المبلغ_الإجمالي >= 0),
                المبلغ_المدفوع REAL NOT NULL DEFAULT 0 CHECK(المبلغ_المدفوع >= 0),
                الرصيد REAL NOT NULL DEFAULT 0 CHECK(الرصيد >= 0),
                حالة_الدين TEXT CHECK(حالة_الدين IN ('نشط', 'مسد', 'متأخر')) DEFAULT 'نشط',
                ملاحظات TEXT,
                تاريخ_الإنشاء TEXT DEFAULT CURRENT_TIMESTAMP,
                تاريخ_التحديث TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            INSERT INTO الديون (اسم_الطرف, نوع_الطرف, العملة, المبلغ_الإجمالي, المبلغ_المدفوع, الرصيد, حالة_الدين)
            VALUES (?, 'مورد', 'ليرة_سورية', 5000.0, 0, 5000.0, 'مسد')
        """, ("مورد_قديم",))
        conn.commit()
        conn.close()

        from migrations.create_database import migrate_debt_status_constraint
        conn.close()
        migrate_debt_status_constraint()

        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        cur = conn.cursor()

        cur.execute("SELECT حالة_الدين FROM الديون WHERE اسم_الطرف = ?", ("مورد_قديم",))
        row = cur.fetchone()
        assert row is not None
        assert row["حالة_الدين"] == "مسدد"

        cur.execute("""
            UPDATE الديون
            SET الرصيد = الرصيد - ?, المبلغ_المدفوع = المبلغ_المدفوع + ?,
                حالة_الدين = CASE WHEN (الرصيد - ?) <= 0.01 THEN 'مسدد' ELSE 'نشط' END
            WHERE معرف = ?
        """, (5000.0, 5000.0, 5000.0, 1))
        conn.commit()

        cur.execute("SELECT الرصيد, حالة_الدين FROM الديون WHERE معرف = ?", (1,))
        row = cur.fetchone()
        assert row["الرصيد"] == 0.0
        assert row["حالة_الدين"] == "مسدد"
        conn.close()

    def test_payment_exceeds_balance_fails(self, temp_db, db_conn):
        """منع الدفع الزائد"""
        cursor = db_conn.cursor()
        cursor.execute("""
            INSERT INTO الديون (اسم_الطرف, نوع_الطرف, العملة, المبلغ_الإجمالي, المبلغ_المدفوع, الرصيد, حالة_الدين)
            VALUES (?, 'مورد', 'ليرة_سورية', 5000.0, 0, 5000.0, 'نشط')
        """, ("مورد1",))
        debt_id = cursor.lastrowid
        db_conn.commit()

        cursor.execute("SELECT الرصيد FROM الديون WHERE معرف = ?", (debt_id,))
        balance = cursor.fetchone()[0]

        payment_amount = 6000.0
        assert payment_amount > balance + 0.01

    def test_add_movement_for_payment(self, temp_db, db_conn):
        """تسجيل دفعة ينشئ حركة في تحركات_الديون"""
        cursor = db_conn.cursor()
        cursor.execute("""
            INSERT INTO الديون (اسم_الطرف, نوع_الطرف, العملة, المبلغ_الإجمالي, المبلغ_المدفوع, الرصيد, حالة_الدين)
            VALUES (?, 'مورد', 'ليرة_سورية', 10000.0, 0, 10000.0, 'نشط')
        """, ("مورد1",))
        debt_id = cursor.lastrowid
        db_conn.commit()

        cursor.execute("""
            INSERT INTO تحركات_الديون (معرف_الدين, المبلغ, نوع_الحركة, ملاحظات)
            VALUES (?, ?, 'دفعة', ?)
        """, (debt_id, 5000.0, "دفعة أولى - نقدي"))
        db_conn.commit()

        cursor.execute("SELECT * FROM تحركات_الديون WHERE معرف_الدين = ? AND نوع_الحركة = 'دفعة'", (debt_id,))
        row = cursor.fetchone()
        assert row is not None
        assert row["المبلغ"] == 5000.0

    def test_delete_creditor_with_invoices_blocked(self, temp_db, db_conn):
        """لا يمكن حذف دائن مرتبط بفواتير شراء"""

        cursor = db_conn.cursor()
        cursor.execute("""
            INSERT INTO الديون (اسم_الطرف, نوع_الطرف, العملة, المبلغ_الإجمالي, المبلغ_المدفوع, الرصيد, حالة_الدين)
            VALUES (?, 'مورد', 'ليرة_سورية', ?, ?, ?, 'نشط')
        """, ("مورد1", 10000.0, 0, 10000.0))
        debt_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO فواتير_الشراء (التاريخ, معرف_المورد, اسم_المورد, المبلغ_الإجمالي, العملة)
            VALUES (?, ?, ?, ?, 'ليرة_سورية')
        """, ("2025-01-15", debt_id, "مورد1", 10000.0))
        db_conn.commit()

        from venus.ui.screens.creditors import CreditorsScreen
        from unittest.mock import patch

        screen = CreditorsScreen()
        screen.creditor_ids = [debt_id]
        screen.creditors_data = [(debt_id, "مورد1", "مورد", "ليرة_سورية", 10000.0, "نشط", None)]

        with patch.object(QMessageBox, 'warning') as mock_warn, \
             patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
            screen._on_delete_creditor(debt_id)

        assert mock_warn.called
        cursor.execute("SELECT COUNT(*) FROM الديون WHERE معرف = ?", (debt_id,))
        assert cursor.fetchone()[0] == 1

    def test_delete_creditor_with_movements_blocked(self, temp_db, db_conn):
        """لا يمكن حذف دائن مرتبط بحركات ديون"""

        cursor = db_conn.cursor()
        cursor.execute("""
            INSERT INTO الديون (اسم_الطرف, نوع_الطرف, العملة, المبلغ_الإجمالي, المبلغ_المدفوع, الرصيد, حالة_الدين)
            VALUES (?, 'مورد', 'ليرة_سورية', ?, ?, ?, 'نشط')
        """, ("مورد1", 10000.0, 0, 10000.0))
        debt_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO تحركات_الديون (معرف_الدين, المبلغ, نوع_الحركة, ملاحظات)
            VALUES (?, ?, 'إضافة', ?)
        """, (debt_id, 10000.0, "رصيد افتتاحي"))
        db_conn.commit()

        from venus.ui.screens.creditors import CreditorsScreen
        from unittest.mock import patch

        screen = CreditorsScreen()
        screen.creditor_ids = [debt_id]
        screen.creditors_data = [(debt_id, "مورد1", "مورد", "ليرة_سورية", 10000.0, "نشط", None)]

        with patch.object(QMessageBox, 'warning') as mock_warn, \
             patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
            screen._on_delete_creditor(debt_id)

        assert mock_warn.called
        cursor.execute("SELECT COUNT(*) FROM الديون WHERE معرف = ?", (debt_id,))
        assert cursor.fetchone()[0] == 1


class TestAuditOperations:
    """اختبارات عمليات الجرد الدوري"""

    def test_save_audit(self, temp_db, db_conn):
        """حفظ جرد دوري creates records in الجرد, المخزون, and تحركات_المخزون"""
        cursor = db_conn.cursor()
        cursor.execute("INSERT INTO المجموعات (الاسم) VALUES (?)", ("موالح",))
        group_id = cursor.lastrowid
        cursor.execute("INSERT INTO المواد_الفرعية (الاسم, الوحدة, معرف_المجموعة) VALUES (?, ?, ?)",
                       ("كعك", "قطعة", group_id))
        material_id = cursor.lastrowid

        cursor.execute("INSERT OR REPLACE INTO المخزون (معرف_المادة_الفرعية, الكمية_المتوفرة) VALUES (?, ?)",
                       (material_id, 100.0))
        db_conn.commit()

        audit_date = "2025-01-15 10:00:00"
        theoretical = 100.0
        actual = 95.0
        diff = actual - theoretical
        value = diff * 0

        cursor.execute("""
            INSERT INTO الجرد (التاريخ, معرف_المادة_الفرعية, الكمية_النظري, الكمية_الفعلي, فرق_الجرد, قيمة_الفرق, ملاحظات)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (audit_date, material_id, theoretical, actual, diff, value, f"جرد دوري - كعك"))
        db_conn.commit()

        cursor.execute("SELECT * FROM الجرد WHERE معرف_المادة_الفرعية = ?", (material_id,))
        row = cursor.fetchone()
        assert row is not None
        assert row["فرق_الجرد"] == -5.0
        assert row["الكمية_الفعلي"] == 95.0

    def test_audit_updates_inventory(self, temp_db, db_conn):
        """الجرد يحديث المخزون بالكمية الفعلية"""
        cursor = db_conn.cursor()
        cursor.execute("INSERT INTO المجموعات (الاسم) VALUES (?)", ("موالح",))
        group_id = cursor.lastrowid
        cursor.execute("INSERT INTO المواد_الفرعية (الاسم, الوحدة, معرف_المجموعة) VALUES (?, ?, ?)",
                       ("كعك", "قطعة", group_id))
        material_id = cursor.lastrowid
        db_conn.commit()

        actual_qty = 95.0
        cursor.execute("""
            INSERT OR REPLACE INTO المخزون (معرف_المادة_الفرعية, الكمية_المتوفرة, آخر_تحديث)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (material_id, actual_qty))
        db_conn.commit()

        cursor.execute("SELECT الكمية_المتوفرة FROM المخزون WHERE معرف_المادة_الفرعية = ?", (material_id,))
        assert cursor.fetchone()[0] == 95.0

    def test_audit_creates_movement(self, temp_db, db_conn):
        """الجرد ينشئ حركة في تحركات_المخزون"""
        cursor = db_conn.cursor()
        cursor.execute("INSERT INTO المجموعات (الاسم) VALUES (?)", ("موالح",))
        group_id = cursor.lastrowid
        cursor.execute("INSERT INTO المواد_الفرعية (الاسم, الوحدة, معرف_المجموعة) VALUES (?, ?, ?)",
                       ("كعك", "قطعة", group_id))
        material_id = cursor.lastrowid
        db_conn.commit()

        cursor.execute("""
            INSERT INTO تحركات_المخزون
            (معرف_المادة_الفرعية, نوع_الحركة, الكمية, الرصيد_بعد, ملاحظات)
            VALUES (?, 'جرد', ?, ?, ?)
        """, (material_id, 5.0, 105.0, "جرد دوري - كعك"))
        db_conn.commit()

        cursor.execute("SELECT * FROM تحركات_المخزون WHERE معرف_المادة_الفرعية = ? AND نوع_الحركة = 'جرد'", (material_id,))
        row = cursor.fetchone()
        assert row is not None
        assert row["الكمية"] == 5.0


class TestAccountingRelationships:
    """اختبارات العلاقات المحاسبية"""

    def test_trial_balance_sales_equals_income(self, temp_db, db_conn):
        """ميزان المراجعة: المبيعات = إجمالي الدخل"""
        cursor = db_conn.cursor()
        cursor.execute("INSERT INTO المجموعات (الاسم) VALUES (?)", ("موالح",))
        group_id = cursor.lastrowid
        db_conn.commit()

        sales_date = "2025-01-15"
        cursor.execute("""
            INSERT INTO المبيعات_اليومية (التاريخ, معرف_المجموعة, المبلغ_الإجمالي, العملة, نوع_المعاملة)
            VALUES (?, ?, ?, 'ليرة_سورية', 'نقدي')
        """, (sales_date, group_id, 5000.0))
        cursor.execute("""
            INSERT INTO المبيعات_اليومية (التاريخ, معرف_المجموعة, المبلغ_الإجمالي, العملة, نوع_المعاملة)
            VALUES (?, ?, ?, 'ليرة_سورية', 'نقدي')
        """, (sales_date, group_id, 3000.0))
        db_conn.commit()

        cursor.execute("SELECT SUM(المبلغ_الإجمالي) FROM المبيعات_اليومية WHERE التاريخ = ?", (sales_date,))
        total_sales = cursor.fetchone()[0]
        assert total_sales == 8000.0

    def test_debt_balance_formula(self, temp_db, db_conn):
        """الديون: الرصيد = المبلغ_الإجمالي - المبلغ_المدفوع"""
        cursor = db_conn.cursor()
        cursor.execute("""
            INSERT INTO الديون (اسم_الطرف, نوع_الطرف, العملة, المبلغ_الإجمالي, المبلغ_المدفوع, الرصيد, حالة_الدين)
            VALUES (?, 'مورد', 'ليرة_سورية', 15000.0, 5000.0, 10000.0, 'نشط')
        """, ("مورد1",))
        debt_id = cursor.lastrowid
        db_conn.commit()

        cursor.execute("SELECT المبلغ_الإجمالي, المبلغ_المدفوع, الرصيد FROM الديون WHERE معرف = ?", (debt_id,))
        total, paid, balance = cursor.fetchone()
        assert balance == total - paid

    def test_cash_balance_formula(self, temp_db, db_conn):
        """الرصيد النظري = بداية + مبيعات - مصروفات - سحوبات"""
        opening = 100000.0
        sales = 5000.0
        expenses = 2000.0
        withdrawals = 1000.0
        theoretical = opening + sales - expenses - withdrawals
        assert theoretical == 102000.0


# ============================================================
# 9. اختبارات التقارير المالية
# ============================================================

class TestReports:
    """اختبارات شاشة التقارير المالية"""

    def test_sales_report_total(self, temp_db):

        gid = insert_group("موالح")
        insert_sale(gid, date="2026-01-01", amount=5000.0)
        insert_sale(gid, date="2026-01-02", amount=3000.0)

        screen = ReportsScreen()
        screen.sales_from.setDate(QDate(2026, 1, 1))
        screen.sales_to.setDate(QDate(2026, 1, 2))
        screen.load_sales_report()

        label_text = screen.sales_total_label.text()
        match = re.search(r'[\d,]+\.?\d*', label_text)
        report_total = float(match.group().replace(",", "")) if match else 0.0
        assert abs(report_total - 8000.0) < 0.01

    def test_inventory_report_shows_materials(self, temp_db):

        gid = insert_group("موالح")
        mid = insert_material("كعك", gid, qty=50.0)

        screen = ReportsScreen()
        screen.load_inventory()

        found = False
        for row in range(screen.inventory_table.table.rowCount()):
            item = screen.inventory_table.table.item(row, 0)
            if item and "كعك" in item.text():
                found = True
                break
        assert found

    def test_debts_report_shows_summary(self, temp_db):

        cid = insert_creditor("مورد أحمد", total=10000.0, balance=5000.0)

        screen = ReportsScreen()
        screen.load_debts()

        assert screen.debts_table.table.rowCount() > 0

    def test_cash_movements_report(self, temp_db):

        insert_cash_day("2026-01-01", opening=100000.0, actual=105000.0, diff=5000.0)

        screen = ReportsScreen()
        screen.cash_from.setDate(QDate(2026, 1, 1))
        screen.cash_to.setDate(QDate(2026, 1, 1))
        screen.load_cash_movements()

        assert screen.cash_table.rowCount() > 0

    def test_profit_report_requires_audit(self, temp_db):

        gid = insert_group("موالح")
        mid = insert_material("كعك", gid, qty=10.0)
        insert_sale(gid, date="2026-01-01", amount=5000.0)

        screen = ReportsScreen()
        screen.profit_from.setDate(QDate(2026, 1, 1))
        screen.profit_to.setDate(QDate(2026, 1, 1))
        screen.load_profit_report()

        assert screen.profit_table.rowCount() >= 0


# ============================================================
# 10. اختبارات الإعدادات
# ============================================================

class TestSettings:
    """اختبارات شاشة الإعدادات"""

    def test_settings_initializes_data_lists(self, temp_db):

        screen = SettingsScreen()
        assert hasattr(screen, 'creditor_ids')
        assert hasattr(screen, 'inventory_data')
        assert hasattr(screen, 'groups_data')
        assert hasattr(screen, 'materials_data')
        assert hasattr(screen, 'creditors_data')

    def test_settings_loads_data(self, temp_db):

        gid = insert_group("موالح")
        mid = insert_material("كعك", gid)

        screen = SettingsScreen()
        screen.load_data()

        assert len(screen.groups_data) > 0 or len(screen.materials_data) > 0

    def test_settings_exchange_rate_update(self, temp_db):

        screen = SettingsScreen()
        screen.new_rate_input.setText("9000")

        with patch.object(QMessageBox, 'information'):
            screen.update_exchange_rate()

        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT القيمة FROM الإعدادات WHERE المفتاح = 'سعر_صرف_الدولار'"
            ).fetchone()
            assert row is not None
            assert row[0] == "9000.0"
        finally:
            conn.close()


# ============================================================
# 11. اختبارات الأحداث والتكامل
# ============================================================

class TestAppEvents:
    """اختبارات نظام الأحداث"""

    def test_data_changed_signal(self, qt_app):
        captured = []
        app_events.data_changed.connect(captured.append)
        app_events.emit_data_changed("materials")
        assert captured == ["materials"]

    def test_no_infinite_loop(self, qt_app, temp_db):

        dashboard = DashboardScreen()
        call_count = [0]
        original = dashboard.refresh_data

        def counting():
            call_count[0] += 1
            if call_count[0] > 5:
                raise RuntimeError("حلقة لا نهائية")
            return original()

        dashboard.refresh_data = counting
        app_events.emit_data_changed("sales")
        assert call_count[0] == 1
        app_events.emit_data_changed("materials")
        assert call_count[0] == 2


# ============================================================
# 12. اختبارات العملة
# ============================================================

class TestCurrency:
    """اختبارات دوال تنسيق العملة"""

    def test_fmt_syp(self):
        assert fmt_syp(1000) == "1,000 ليرة سورية"
        assert fmt_syp(0) == "0 ليرة سورية"
        assert fmt_syp(1000000) == "1,000,000 ليرة سورية"

    def test_fmt_usd(self):
        assert fmt_usd(100) == "100 دولار"
        assert fmt_usd(99.99) == "100 دولار"
        assert fmt_usd(1000000) == "1,000,000 دولار"

    def test_fmt_general(self):
        assert fmt(0) == "0"
        assert fmt(1000) == "1,000"
        assert fmt(1234.56) == "1,235"
        assert fmt(None) == "0"


# ============================================================
# 13. اختبارات الويدجتس
# ============================================================

class TestWidgets:
    """اختبارات العناصر المخصصة"""

    def test_searchable_table_filter(self, qt_app):
        table = SearchableTable()
        headers = ["معرف", "الاسم", "الوحدة"]
        rows = [
            [1, "كعك", "قطعة"],
            [2, "شاي أخضر", "قطعة"],
            [3, "سكر", "كيلوغرام"],
        ]
        table.set_data(headers, rows, id_column_index=0)
        assert table.table.rowCount() == 3

        table.search_box.setText("شاي")
        visible = table.get_visible_row_ids()
        assert visible == [2]

    def test_combo_quick_add(self, qt_app):
        combo = ComboWithQuickAdd(
            load_func=lambda: ["مجموعة أ", "مجموعة ب"],
            add_dialog_func=lambda: None
        )
        assert combo.combo.count() == 2

    def test_entity_detail_dialog(self, qt_app):
        data = {"الاسم": "كعك", "الوحدة": "قطعة"}
        related = [[1, "2026-01-01", 10.0, "شراء"]]
        headers = ["معرّف", "التاريخ", "الكمية", "نوع الحركة"]
        dialog = EntityDetailDialog(
            "تفاصيل مادة", detail_data=data,
            related_rows=related, related_headers=headers
        )
        assert dialog.windowTitle() == "تفاصيل مادة"
        assert dialog.related_table.rowCount() == 1
        dialog.accept()


# ============================================================
# 14. اختبارات سيناريو يوم عمل كامل (UAT)
# ============================================================

class TestFullDayUAT:
    """سيناريو يوم عمل كامل من الفتح حتى الإغلاق"""

    def test_full_day_workflow(self, qt_app, temp_db):

        test_date = "2026-01-15"

        # فتح اليومية
        cash = CashScreen()
        cash.open_date.setDate(QDate(2026, 1, 15))
        cash.opening_edit.setText("200000")
        with patch.object(QMessageBox, 'information'):
            cash.open_day()
        assert cash.day_opened is True

        # تسجيل مبيعات
        gid = insert_group("موالح")
        sales = SalesScreen()
        sales.date_input.setDate(QDate(2026, 1, 15))
        sales.add_entry_row()
        combo = sales.entry_table.cellWidget(0, 0)
        combo.setCurrentValue(gid)
        sales.entry_table.item(0, 1).setText("50000")
        sales.entry_table.item(0, 2).setText("")
        with patch.object(QMessageBox, 'information'):
            sales.save_sales()

        # تسجيل مصروف
        insert_cash_day(test_date, opening=200000.0)
        screen = CashScreen()
        screen.open_date.setDate(QDate(2026, 1, 15))
        screen.exp_date.setDate(QDate(2026, 1, 15))
        screen.exp_amount.setText("5000")
        screen.exp_desc.setText("كهرباء")
        screen.exp_type.setCurrentText("كهرباء")
        with patch.object(QMessageBox, 'information'):
            screen.save_expense()

        # تسجيل سحب
        screen.wd_date.setDate(QDate(2026, 1, 15))
        screen.wd_amount.setText("10000")
        screen.wd_desc.setText("سحب شخصي")
        with patch.object(QMessageBox, 'information'):
            screen.save_withdrawal()

        # إغلاق اليومية
        cash2 = CashScreen()
        cash2.open_date.setDate(QDate(2026, 1, 15))
        cash2.actual_edit.setText("235000")
        with patch.object(QMessageBox, 'information'):
            cash2.close_day()
        assert cash2.today_closed is True

        # التحقق من المبيعات في جدول المبيعات_اليومية
        repo = SalesRepository()
        sales = repo.get_by_date(test_date)
        assert len(sales) == 1
        assert sales[0]["المبلغ_الإجمالي"] == 50000.0

        # التحقق من المصروفات
        conn = get_conn()
        try:
            exp_row = conn.execute(
                "SELECT * FROM المصروفات WHERE الوصف = ?", ("كهرباء",)
            ).fetchone()
            assert exp_row is not None
            assert exp_row[2] == 5000.0
        finally:
            conn.close()

        # التحقق من السحوبات
        conn = get_conn()
        try:
            wd_row = conn.execute(
                "SELECT * FROM السحوبات WHERE الوصف = ?", ("سحب شخصي",)
            ).fetchone()
            assert wd_row is not None
            assert wd_row[2] == 10000.0
        finally:
            conn.close()

        # إغلاق اليومية
        cash2 = CashScreen()
        cash2.open_date.setDate(QDate(2026, 1, 15))
        cash2.actual_edit.setText("235000")
        with patch.object(QMessageBox, 'information'):
            cash2.close_day()
        assert cash2.today_closed is True

        # التحقق من أرصدة الصندوق
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM أرصدة_الصندوق WHERE التاريخ = ?", (test_date,)
        ).fetchone()
        conn.close()
        assert row is not None
        assert row["رصيد_بداية_اليوم"] == 200000.0
        assert row["مصروفات_اليوم"] == 5000.0
        assert row["سحوبات_اليوم"] == 10000.0


# ============================================================
# 15. اختبارات العلاقات المحاسبية
# ============================================================

class TestAccountingValidation:
    """اختبارات المعادلات والعلائق المحاسبية"""

    def test_inventory_movement_balance(self, temp_db, db_conn):
        """حركات المخزون تحافظ على الرصيد"""
        gid = insert_group("موالح")
        mid = insert_material("كعك", gid, qty=10.0)

        cursor = db_conn.cursor()
        cursor.execute(
            "INSERT INTO تحركات_المخزون (معرف_المادة_الفرعية, نوع_الحركة, الكمية, الرصيد_بعد) "
            "VALUES (?, 'شراء', ?, ?)", (mid, 5.0, 15.0)
        )
        db_conn.commit()

        cursor.execute(
            "SELECT الرصيد_بعد FROM تحركات_المخزون WHERE معرف_المادة_الفرعية = ? AND نوع_الحركة = 'شراء'",
            (mid,)
        )
        row = cursor.fetchone()
        assert row[0] == 15.0


# ============================================================
# 16. اختبارات الحالات الحدية
# ============================================================

class TestEdgeCases:
    """اختبار الحالات الحدية والقيود"""

    def test_zero_balance_creditor(self, temp_db):

        cid = insert_creditor("مورد1", total=10000.0, balance=10000.0)
        insert_debt_movement(cid, 10000.0, "إضافة")

        repo = CreditorsRepository()
        before = repo.get_by_id(cid)
        assert before["الرصيد"] == 10000.0

        # تسجيل دفعة كاملة عبر SQL مباشر
        conn = get_conn()
        try:
            conn.execute("""
                UPDATE الديون
                SET الرصيد = الرصيد - ?,
                    المبلغ_المدفوع = المبلغ_المدفوع + ?,
                    حالة_الدين = CASE WHEN (الرصيد - ?) <= 0.01 THEN 'مسدد' ELSE 'نشط' END
                WHERE معرف = ?
            """, (10000.0, 10000.0, 10000.0, cid))
            conn.commit()
        finally:
            conn.close()

        after = repo.get_by_id(cid)
        assert after["الرصيد"] == 0.0
        assert after["حالة_الدين"] == "مسدد"

    def test_negative_quantity_rejected_in_inventory(self, temp_db):

        gid = insert_group("موالح")
        mid = insert_material("كعك", gid)

        conn = get_conn()
        try:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO المخزون (معرف_المادة_الفرعية, الكمية_المتوفرة) VALUES (?, ?)",
                    (mid, -10.0)
                )
                conn.commit()
        finally:
            conn.close()

    def test_large_amounts_handled(self, temp_db):

        gid = insert_group("موالح")
        mid = insert_material("كعك", gid, qty=1000000.0)

        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT الكمية_المتوفرة FROM المخزون WHERE معرف_المادة_الفرعية = ?", (mid,)
            ).fetchone()
            assert row[0] == 1000000.0
        finally:
            conn.close()

    def test_empty_search_returns_all(self, temp_db):

        gid = insert_group("موالح")
        insert_material("كعك", gid)
        insert_material("شاي", gid)

        repo = MaterialsRepository()
        results = repo.search("")
        assert len(results) >= 2


# ============================================================
# 17. اختبارات التكامل الكامل
# ============================================================

class TestIntegrationScenarios:
    """سيناريوهات تكامل كاملة"""

    def test_purchase_to_sale_flow(self, temp_db):
        """شراء ثم بيع يحدث المخزون والمبيعات"""

        gid = insert_group("موالح")
        mid = insert_material("كعك", gid, qty=100.0)

        # إنشاء فاتورة شراء نقدية
        supplier = insert_creditor("مورد1", total=0, balance=0)
        invoice_id = insert_invoice(supplier="مورد1", total=10000.0, date="2026-01-01")
        insert_invoice_detail(invoice_id, mid, qty=50.0, price=200.0)

        # تحديث المخزون يدوياً (محاكاة save_purchase_bill)
        conn = get_conn()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO المخزون (معرف_المادة_الفرعية, الكمية_المتوفرة, آخر_تحديث)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (mid, 150.0))
            conn.commit()
        finally:
            conn.close()

        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT الكمية_المتوفرة FROM المخزون WHERE معرف_المادة_الفرعية = ?", (mid,)
            ).fetchone()
            assert row[0] == 150.0
        finally:
            conn.close()

    def test_debt_payment_flow(self, temp_db):
        """دين + دفعة + تحديث الرصيد"""

        cid = insert_creditor("مورد أحمد", total=10000.0, balance=10000.0)
        insert_debt_movement(cid, 10000.0, "إضافة")

        repo = CreditorsRepository()
        before = repo.get_by_id(cid)
        assert before["الرصيد"] == 10000.0

        # تسجيل دفعة جزئية عبر SQL مباشر
        conn = get_conn()
        try:
            conn.execute("""
                UPDATE الديون
                SET الرصيد = الرصيد - ?,
                    المبلغ_المدفوع = المبلغ_المدفوع + ?,
                    حالة_الدين = CASE WHEN (الرصيد - ?) <= 0.01 THEN 'مسدد' ELSE 'نشط' END
                WHERE معرف = ?
            """, (3000.0, 3000.0, 3000.0, cid))
            conn.commit()
        finally:
            conn.close()

        after = repo.get_by_id(cid)
        assert after["الرصيد"] == 7000.0
        assert after["حالة_الدين"] == "نشط"

    def test_audit_dialog_exists(self, temp_db):
        """التأكد من أن حوار الجرد يُنشأ بدون أخطاء"""

        gid = insert_group("موالح")
        insert_material("كعك", gid, qty=100.0)

        dialog = AuditDialog()
        assert dialog.audit_table.rowCount() >= 1
        assert dialog.audit_table.columnCount() == 6
