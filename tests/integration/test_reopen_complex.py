# -*- coding: utf-8 -*-
"""
سيناريو 4: إعادة فتح يومية معقدة
"""
import pytest
from unittest.mock import patch
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QDate

from venus.ui.screens.cash import CashScreen
from venus.core.database import get_conn

from tests.fixtures.helpers import insert_group, insert_material, insert_sale, insert_vault_balance


class TestReopenComplexScenario:
    """إغلاق يومية مع مبيعات غير مسجلة → تحويل للخزنة → إيداع إضافي → إعادة الفتح"""

    def test_close_day_with_unregistered_sales(self, qt_app, temp_db):
        group_id = insert_group('scenario4_unreg_group')
        material_id = insert_material('scenario4_unreg_cake', group_id=group_id, qty=100.0)
        insert_vault_balance(3000000.0)

        with patch.object(QMessageBox, 'information'):
            screen = CashScreen()
            screen.open_date.setDate(QDate(2026, 4, 1))
            screen.opening_edit.setText('100000')
            screen.currency_combo.setCurrentText('ليرة_سورية')
            screen.open_day()

        insert_sale(group_id, date='2026-04-01', amount=50000.0, currency='ليرة_سورية')

        with patch.object(QMessageBox, 'information'), patch.object(QMessageBox, 'warning'):
            screen = CashScreen()
            screen.open_date.setDate(QDate(2026, 4, 1))
            screen.actual_edit.setText('180000.0')
            screen.close_day()

        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT فرق_التسوية FROM أرصدة_الصندوق WHERE التاريخ = ?", ('2026-04-01',))
            diff = cursor.fetchone()[0]
            assert diff == 30000.0

            cursor.execute("""
                SELECT COUNT(*) FROM المبيعات_اليومية
                WHERE التاريخ = ? AND ملاحظات LIKE 'مبيعات غير مسجلة%'
            """, ('2026-04-01',))
            assert cursor.fetchone()[0] > 0
        finally:
            conn.close()

    def test_reopen_day_reverses_all_operations(self, qt_app, temp_db):
        group_id = insert_group('scenario4_reopen_group')
        material_id = insert_material('scenario4_reopen_cake', group_id=group_id, qty=100.0)
        insert_vault_balance(3000000.0)

        with patch.object(QMessageBox, 'information'):
            screen = CashScreen()
            screen.open_date.setDate(QDate(2026, 4, 2))
            screen.opening_edit.setText('100000')
            screen.currency_combo.setCurrentText('ليرة_سورية')
            screen.open_day()

        insert_sale(group_id, date='2026-04-02', amount=80000.0, currency='ليرة_سورية')

        with patch.object(QMessageBox, 'information'), patch.object(QMessageBox, 'warning'):
            screen = CashScreen()
            screen.open_date.setDate(QDate(2026, 4, 2))
            screen.actual_edit.setText('110000.0')
            screen.close_day()

        with patch.object(QMessageBox, 'information'), patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
            screen = CashScreen()
            screen.open_date.setDate(QDate(2026, 4, 2))
            screen.reopen_day()

        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT مغلقة, فرق_التسوية FROM أرصدة_الصندوق WHERE التاريخ = ?", ('2026-04-02',))
            row = cursor.fetchone()
            assert row is not None
            assert row['مغلقة'] == 0
            assert row['فرق_التسوية'] == 0

            cursor.execute("""
                SELECT COUNT(*) FROM المبيعات_اليومية
                WHERE التاريخ = ? AND ملاحظات LIKE 'مبيعات غير مسجلة%'
            """, ('2026-04-02',))
            assert cursor.fetchone()[0] == 0

            cursor.execute("""
                SELECT COUNT(*) FROM تحويلات_الصندوق
                WHERE date(التاريخ) = ? AND من_حساب = 'الدرج' AND إلى_حساب = 'الخزنة'
            """, ('2026-04-02',))
            assert cursor.fetchone()[0] == 0

            cursor.execute("""
                SELECT COUNT(*) FROM الخزنة
                WHERE date(التاريخ) = ? AND البيان = 'إيداع إغلاق يومية'
            """, ('2026-04-02',))
            assert cursor.fetchone()[0] == 0
        finally:
            conn.close()

    def test_complex_reopen_with_multiple_closes(self, qt_app, temp_db):
        insert_vault_balance(3000000.0)

        with patch.object(QMessageBox, 'information'):
            screen = CashScreen()
            screen.open_date.setDate(QDate(2026, 4, 3))
            screen.opening_edit.setText('100000')
            screen.currency_combo.setCurrentText('ليرة_سورية')
            screen.open_day()

        with patch.object(QMessageBox, 'information'), patch.object(QMessageBox, 'warning'):
            screen = CashScreen()
            screen.open_date.setDate(QDate(2026, 4, 3))
            screen.actual_edit.setText('100000.0')
            screen.close_day()

        with patch.object(QMessageBox, 'information'), patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
            screen = CashScreen()
            screen.open_date.setDate(QDate(2026, 4, 3))
            screen.reopen_day()

        with patch.object(QMessageBox, 'information'), patch.object(QMessageBox, 'warning'):
            screen = CashScreen()
            screen.open_date.setDate(QDate(2026, 4, 3))
            screen.actual_edit.setText('100000.0')
            screen.close_day()

        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT مغلقة FROM أرصدة_الصندوق WHERE التاريخ = ?", ('2026-04-03',))
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == 1

            cursor.execute("""
                SELECT COUNT(*) FROM تحويلات_الصندوق
                WHERE date(التاريخ) = ? AND من_حساب = 'الدرج' AND إلى_حساب = 'الخزنة'
            """, ('2026-04-03',))
            assert cursor.fetchone()[0] == 1
        finally:
            conn.close()
