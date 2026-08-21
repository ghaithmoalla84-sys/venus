# -*- coding: utf-8 -*-
"""
سيناريو 3: يوم عمل كامل بالعملة المزدوجة
"""
import pytest
from unittest.mock import patch
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QDate

from venus.ui.screens.cash import CashScreen
from venus.core.database import get_conn

from tests.fixtures.helpers import insert_group, insert_material, insert_sale, insert_expense, insert_withdrawal, insert_vault_balance
from tests.fixtures.constants import TEST_DATE


class TestFullDayWorkflowScenario:
    """يوم عمل كامل بالعملة المزدوجة"""

    def test_open_day_and_sales_syp(self, qt_app, temp_db):
        insert_vault_balance(3000000.0)

        with patch.object(QMessageBox, 'information'):
            screen = CashScreen()
            screen.open_date.setDate(QDate(2026, 3, 1))
            screen.opening_edit.setText('200000')
            screen.currency_combo.setCurrentText('ليرة_سورية')
            screen.open_day()

        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM أرصدة_الصندوق WHERE التاريخ = ?", ('2026-03-01',))
            row = cursor.fetchone()
            assert row is not None
            assert row['رصيد_بداية_اليوم'] == 200000.0
            assert row['العملة'] == 'ليرة_سورية'
        finally:
            conn.close()

    def test_multi_currency_sales_in_day(self, qt_app, temp_db):
        group_id = insert_group('scenario3_multi_group')
        insert_vault_balance(3000000.0)

        with patch.object(QMessageBox, 'information'):
            screen = CashScreen()
            screen.open_date.setDate(QDate(2026, 3, 1))
            screen.opening_edit.setText('200000')
            screen.currency_combo.setCurrentText('ليرة_سورية')
            screen.open_day()

        insert_sale(group_id, date='2026-03-01', amount=150000.0, currency='ليرة_سورية', notes='مبيعات ليرة')
        insert_sale(group_id, date='2026-03-01', amount=500.0, currency='دولار', notes='مبيعات دولار')

        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(المبلغ_الإجمالي) FROM المبيعات_اليومية WHERE التاريخ = ?", ('2026-03-01',))
            total = cursor.fetchone()[0] or 0
            assert total == 150500.0
        finally:
            conn.close()

    def test_expenses_and_withdrawals_in_day(self, qt_app, temp_db):
        group_id = insert_group('scenario3_exp_group')
        insert_vault_balance(3000000.0)

        with patch.object(QMessageBox, 'information'):
            screen = CashScreen()
            screen.open_date.setDate(QDate(2026, 3, 1))
            screen.opening_edit.setText('200000')
            screen.currency_combo.setCurrentText('ليرة_سورية')
            screen.open_day()

        insert_expense('2026-03-01 10:00:00', 25000.0, 'إيجار', etype='إيجار', currency='ليرة_سورية')
        insert_withdrawal('2026-03-01 14:00:00', 10000.0, 'سحب شخصي', currency='ليرة_سورية')

        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(المبلغ) FROM المصروفات WHERE date(التاريخ) = ?", ('2026-03-01',))
            expenses = cursor.fetchone()[0] or 0
            assert expenses == 25000.0

            cursor.execute("SELECT SUM(المبلغ) FROM السحوبات WHERE date(التاريخ) = ?", ('2026-03-01',))
            withdrawals = cursor.fetchone()[0] or 0
            assert withdrawals == 10000.0
        finally:
            conn.close()

    def test_close_day_with_transfer_and_settlement(self, qt_app, temp_db):
        group_id = insert_group('scenario3_close_group')
        insert_vault_balance(3000000.0)

        with patch.object(QMessageBox, 'information'):
            screen = CashScreen()
            screen.open_date.setDate(QDate(2026, 3, 1))
            screen.opening_edit.setText('200000')
            screen.currency_combo.setCurrentText('ليرة_سورية')
            screen.open_day()

        insert_sale(group_id, date='2026-03-01', amount=100000.0, currency='ليرة_سورية')
        insert_expense('2026-03-01 10:00:00', 20000.0, 'مصروف', etype='أخرى', currency='ليرة_سورية')
        insert_withdrawal('2026-03-01 14:00:00', 5000.0, 'سحب', currency='ليرة_سورية')

        with patch.object(QMessageBox, 'information'), patch.object(QMessageBox, 'warning'):
            screen = CashScreen()
            screen.open_date.setDate(QDate(2026, 3, 1))
            screen.actual_edit.setText('275000.0')
            screen.close_day()

        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT مغلقة FROM أرصدة_الصندوق WHERE التاريخ = ?", ('2026-03-01',))
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == 1

            cursor.execute("""
                SELECT COUNT(*) FROM تحويلات_الصندوق
                WHERE date(التاريخ) = ? AND من_حساب = 'الدرج' AND إلى_حساب = 'الخزنة'
            """, ('2026-03-01',))
            assert cursor.fetchone()[0] > 0
        finally:
            conn.close()
