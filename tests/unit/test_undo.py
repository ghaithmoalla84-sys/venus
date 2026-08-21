# -*- coding: utf-8 -*-
"""Tests for undo functionality - Venus Coffee"""

import pytest
from unittest.mock import patch
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QDate
from datetime import datetime, timedelta

from venus.ui.screens.sales import SalesScreen
from venus.ui.screens.cash import CashScreen
from venus.core.database import get_conn
from tests.fixtures.helpers import (
    insert_group, insert_sale, insert_cash_day,
    insert_expense, insert_withdrawal, insert_operation_log
)


class TestUndoExpense:
    def test_undo_last_expense_reverses_balance(self, qt_app, temp_db):
        screen = CashScreen()
        screen.open_date.setDate(QDate(2026, 8, 15))
        screen.opening_edit.setText('100000')
        with patch.object(QMessageBox, 'information'):
            screen.open_day()
        screen.loading_overlay.stop()

        screen.exp_date.setDate(QDate(2026, 8, 15))
        screen.exp_amount.setText('5000')
        screen.exp_desc.setText('undo test expense')
        with patch.object(QMessageBox, 'information'):
            screen.save_expense()

        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT مصروفات_اليوم FROM أرصدة_الصندوق WHERE التاريخ = '2026-08-15'")
            row = cur.fetchone()
            assert row is not None
            assert row[0] == 5000.0
        finally:
            conn.close()

        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
            with patch.object(QMessageBox, 'information'):
                screen.undo_last_expense()

        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT مصروفات_اليوم FROM أرصدة_الصندوق WHERE التاريخ = '2026-08-15'")
            row = cur.fetchone()
            assert row is not None
            assert row[0] == 0.0

            cur.execute("SELECT COUNT(*) FROM المصروفات WHERE الوصف = 'undo test expense'")
            assert cur.fetchone()[0] == 0

            cur.execute("SELECT تم_التراجع FROM سجل_العمليات_الأخيرة WHERE نوع_العملية = 'مصروف'")
            rows = cur.fetchall()
            assert len(rows) == 1
            assert rows[0][0] == 1
        finally:
            conn.close()

    def test_undo_last_withdrawal_reverses_balance(self, qt_app, temp_db):
        screen = CashScreen()
        screen.open_date.setDate(QDate(2026, 8, 15))
        screen.opening_edit.setText('100000')
        with patch.object(QMessageBox, 'information'):
            screen.open_day()
        screen.loading_overlay.stop()

        screen.wd_date.setDate(QDate(2026, 8, 15))
        screen.wd_amount.setText('3000')
        screen.wd_desc.setText('undo test withdrawal')
        with patch.object(QMessageBox, 'information'):
            screen.save_withdrawal()

        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT سحوبات_اليوم FROM أرصدة_الصندوق WHERE التاريخ = '2026-08-15'")
            row = cur.fetchone()
            assert row is not None
            assert row[0] == 3000.0
        finally:
            conn.close()

        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
            with patch.object(QMessageBox, 'information'):
                screen.undo_last_withdrawal()

        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT سحوبات_اليوم FROM أرصدة_الصندوق WHERE التاريخ = '2026-08-15'")
            row = cur.fetchone()
            assert row is not None
            assert row[0] == 0.0

            cur.execute("SELECT COUNT(*) FROM السحوبات WHERE الوصف = 'undo test withdrawal'")
            assert cur.fetchone()[0] == 0

            cur.execute("SELECT تم_التراجع FROM سجل_العمليات_الأخيرة WHERE نوع_العملية = 'سحب'")
            rows = cur.fetchall()
            assert len(rows) == 1
            assert rows[0][0] == 1
        finally:
            conn.close()

    def test_undo_expense_on_closed_day_fails(self, qt_app, temp_db):
        screen = CashScreen()
        screen.open_date.setDate(QDate(2026, 8, 15))
        screen.opening_edit.setText('100000')
        with patch.object(QMessageBox, 'information'):
            screen.open_day()
        screen.loading_overlay.stop()

        screen.exp_date.setDate(QDate(2026, 8, 15))
        screen.exp_amount.setText('5000')
        screen.exp_desc.setText('closed day expense')
        with patch.object(QMessageBox, 'information'):
            screen.save_expense()

        screen.actual_edit.setText('100000')
        with patch.object(QMessageBox, 'information'):
            screen.close_day()

        with patch.object(QMessageBox, 'warning') as mock_warning:
            screen.undo_last_expense()
        mock_warning.assert_called_once()

    def test_undo_withdrawal_on_closed_day_fails(self, qt_app, temp_db):
        screen = CashScreen()
        screen.open_date.setDate(QDate(2026, 8, 15))
        screen.opening_edit.setText('100000')
        with patch.object(QMessageBox, 'information'):
            screen.open_day()
        screen.loading_overlay.stop()

        screen.wd_date.setDate(QDate(2026, 8, 15))
        screen.wd_amount.setText('3000')
        screen.wd_desc.setText('closed day withdrawal')
        with patch.object(QMessageBox, 'information'):
            screen.save_withdrawal()

        screen.actual_edit.setText('100000')
        with patch.object(QMessageBox, 'information'):
            screen.close_day()

        with patch.object(QMessageBox, 'warning') as mock_warning:
            screen.undo_last_withdrawal()
        mock_warning.assert_called_once()

    def test_undo_twice_fails_gracefully(self, qt_app, temp_db):
        screen = CashScreen()
        screen.open_date.setDate(QDate(2026, 8, 15))
        screen.opening_edit.setText('100000')
        with patch.object(QMessageBox, 'information'):
            screen.open_day()
        screen.loading_overlay.stop()

        screen.exp_date.setDate(QDate(2026, 8, 15))
        screen.exp_amount.setText('5000')
        screen.exp_desc.setText('double undo expense')
        with patch.object(QMessageBox, 'information'):
            screen.save_expense()

        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
            with patch.object(QMessageBox, 'information'):
                screen.undo_last_expense()

        with patch.object(QMessageBox, 'information') as mock_info:
            screen.undo_last_expense()
        mock_info.assert_called_once()


class TestUndoSale:
    def test_undo_last_sale_deletes_only_new_sale(self, qt_app, temp_db):
        group_id = insert_group('undo_sale_group')
        screen = SalesScreen()
        screen.date_input.setDate(QDate(2026, 8, 15))

        screen.add_entry_row()
        screen.entry_table.cellWidget(0, 0).setCurrentValue(group_id)
        screen.entry_table.item(0, 1).setText('5000')
        with patch.object(QMessageBox, 'information'):
            screen.save_sales()

        screen.add_entry_row()
        screen.entry_table.cellWidget(0, 0).setCurrentValue(group_id)
        screen.entry_table.item(0, 1).setText('3000')
        with patch.object(QMessageBox, 'information'):
            screen.save_sales()

        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM المبيعات_اليومية WHERE التاريخ = '2026-08-15' AND معرف_المجموعة = ?", (group_id,))
            count_before = cur.fetchone()[0]
            assert count_before == 1

            cur.execute("SELECT COUNT(*) FROM سجل_العمليات_الأخيرة WHERE نوع_العملية = 'بيع'")
            log_count = cur.fetchone()[0]
            assert log_count == 1
        finally:
            conn.close()

        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
            with patch.object(QMessageBox, 'information'):
                screen.undo_last_sale()

        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM المبيعات_اليومية WHERE التاريخ = '2026-08-15' AND معرف_المجموعة = ?", (group_id,))
            count_after = cur.fetchone()[0]
            assert count_after == 0

            cur.execute("SELECT تم_التراجع FROM سجل_العمليات_الأخيرة WHERE نوع_العملية = 'بيع'")
            rows = cur.fetchall()
            assert len(rows) == 1
            assert rows[0][0] == 1
        finally:
            conn.close()

    def test_undo_sale_on_closed_day_fails(self, qt_app, temp_db):
        group_id = insert_group('undo_sale_closed_group')
        screen = SalesScreen()
        screen.date_input.setDate(QDate(2026, 8, 15))

        screen.add_entry_row()
        screen.entry_table.cellWidget(0, 0).setCurrentValue(group_id)
        screen.entry_table.item(0, 1).setText('5000')
        with patch.object(QMessageBox, 'information'):
            screen.save_sales()

        insert_cash_day('2026-08-15', opening=100000, actual=100000, diff=0, closed=True)

        with patch.object(QMessageBox, 'warning') as mock_warning:
            screen.undo_last_sale()
        mock_warning.assert_called_once()

    def test_undo_sale_twice_fails_gracefully(self, qt_app, temp_db):
        group_id = insert_group('undo_sale_double_group')
        screen = SalesScreen()
        screen.date_input.setDate(QDate(2026, 8, 15))

        screen.add_entry_row()
        screen.entry_table.cellWidget(0, 0).setCurrentValue(group_id)
        screen.entry_table.item(0, 1).setText('5000')
        with patch.object(QMessageBox, 'information'):
            screen.save_sales()

        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
            with patch.object(QMessageBox, 'information'):
                screen.undo_last_sale()

        with patch.object(QMessageBox, 'information') as mock_info:
            screen.undo_last_sale()
        mock_info.assert_called_once()
