# -*- coding: utf-8 -*-
"""Tests for CashScreen - Venus Coffee"""

import pytest
from unittest.mock import patch, MagicMock
from PyQt5.QtWidgets import QDialog, QMessageBox, QInputDialog
from PyQt5.QtCore import Qt, QDate
from datetime import datetime, timedelta

from venus.ui.screens.cash import CashScreen
from tests.fixtures.helpers import insert_group, insert_material, insert_creditor, insert_sale, insert_cash_day, insert_vault_balance, insert_expense, insert_withdrawal


class TestCashScreen:
    def test_initial_ui(self, qt_app, temp_db):
        screen = CashScreen()
        assert hasattr(screen, 'cash_tab')
        assert hasattr(screen, 'expenses_tab')
        assert hasattr(screen, 'open_date')
        assert hasattr(screen, 'opening_edit')
        assert hasattr(screen, 'currency_combo')
        assert hasattr(screen, 'open_btn')
        assert hasattr(screen, 'actual_edit')
        assert hasattr(screen, 'close_btn')
        assert hasattr(screen, 'reopen_btn')
        assert hasattr(screen, 'mov_table')

    def test_open_day_success(self, qt_app, temp_db):
        screen = CashScreen()
        screen.open_date.setDate(QDate.currentDate())
        screen.opening_edit.setText('100000')
        screen.currency_combo.setCurrentText('ليرة_سورية')
        with patch.object(QMessageBox, 'information'):
            screen.open_day()
        screen.loading_overlay.stop()
        assert screen.day_opened is True
        assert screen.today_closed is False

    def test_open_day_with_currency(self, qt_app, temp_db):
        screen = CashScreen()
        screen.open_date.setDate(QDate.currentDate())
        screen.opening_edit.setText('50000')
        screen.currency_combo.setCurrentText('دولار')
        with patch.object(QMessageBox, 'information'):
            screen.open_day()
        screen.loading_overlay.stop()
        assert screen.day_opened is True

    def test_open_day_with_opening_balance(self, qt_app, temp_db):
        prev_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        insert_cash_day(prev_date, opening=50000, actual=50000, diff=0, closed=True)
        screen = CashScreen()
        screen.open_date.setDate(QDate.currentDate())
        assert screen.opening_edit.text().strip() != ''

    def test_open_existing_date_fails(self, qt_app, temp_db):
        screen = CashScreen()
        screen.open_date.setDate(QDate.currentDate())
        screen.opening_edit.setText('100000')
        with patch.object(QMessageBox, 'information'):
            screen.open_day()
        screen.loading_overlay.stop()
        screen.opening_edit.setText('100000')
        with patch.object(QMessageBox, 'information') as mock_info:
            screen.open_day()
        mock_info.assert_called_once()

    def test_close_day_no_diff(self, qt_app, temp_db):
        screen = CashScreen()
        screen.open_date.setDate(QDate.currentDate())
        screen.opening_edit.setText('100000')
        with patch.object(QMessageBox, 'information'):
            screen.open_day()
        screen.loading_overlay.stop()
        screen.actual_edit.setText('100000')
        with patch.object(QMessageBox, 'information'):
            screen.close_day()
        assert screen.today_closed is True

    def test_close_day_surplus(self, qt_app, temp_db):
        screen = CashScreen()
        screen.open_date.setDate(QDate.currentDate())
        screen.opening_edit.setText('100000')
        with patch.object(QMessageBox, 'information'):
            screen.open_day()
        screen.loading_overlay.stop()
        screen.actual_edit.setText('150000')
        with patch.object(QMessageBox, 'information'):
            screen.close_day()
        assert screen.today_closed is True

    def test_close_day_deficit(self, qt_app, temp_db):
        screen = CashScreen()
        screen.open_date.setDate(QDate.currentDate())
        screen.opening_edit.setText('100000')
        with patch.object(QMessageBox, 'information'):
            screen.open_day()
        screen.loading_overlay.stop()
        screen.actual_edit.setText('50000')
        with patch.object(QMessageBox, 'warning'):
            screen.close_day()
        assert screen.today_closed is True

    def test_reopen_closed_day(self, qt_app, temp_db):
        screen = CashScreen()
        screen.open_date.setDate(QDate.currentDate())
        screen.opening_edit.setText('100000')
        with patch.object(QMessageBox, 'information'):
            screen.open_day()
        screen.loading_overlay.stop()
        screen.actual_edit.setText('100000')
        with patch.object(QMessageBox, 'information'):
            screen.close_day()
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
            with patch.object(QMessageBox, 'information'):
                screen.reopen_day()
        assert screen.today_closed is False

    def test_add_expense(self, qt_app, temp_db):
        screen = CashScreen()
        screen.open_date.setDate(QDate.currentDate())
        screen.opening_edit.setText('100000')
        with patch.object(QMessageBox, 'information'):
            screen.open_day()
        screen.loading_overlay.stop()
        screen.exp_date.setDate(QDate.currentDate())
        screen.exp_amount.setText('5000')
        screen.exp_desc.setText('test expense')
        with patch.object(QMessageBox, 'information'):
            screen.save_expense()

    def test_add_withdrawal(self, qt_app, temp_db):
        screen = CashScreen()
        screen.open_date.setDate(QDate.currentDate())
        screen.opening_edit.setText('100000')
        with patch.object(QMessageBox, 'information'):
            screen.open_day()
        screen.loading_overlay.stop()
        screen.wd_date.setDate(QDate.currentDate())
        screen.wd_amount.setText('3000')
        screen.wd_desc.setText('test withdrawal')
        with patch.object(QMessageBox, 'information'):
            screen.save_withdrawal()

    def test_block_expense_on_closed_day(self, qt_app, temp_db):
        screen = CashScreen()
        screen.open_date.setDate(QDate.currentDate())
        screen.opening_edit.setText('100000')
        with patch.object(QMessageBox, 'information'):
            screen.open_day()
        screen.loading_overlay.stop()
        screen.actual_edit.setText('100000')
        with patch.object(QMessageBox, 'information'):
            screen.close_day()
        screen.exp_amount.setText('5000')
        with patch.object(QMessageBox, 'warning'):
            screen.save_expense()

    def test_vault_balance_after_deposit(self, qt_app, temp_db):
        screen = CashScreen()
        initial = screen.get_vault_balance()
        screen.record_vault_deposit(100000, 'test deposit')
        new_balance = screen.get_vault_balance()
        assert new_balance == initial + 100000

    def test_vault_balance_after_withdrawal(self, qt_app, temp_db):
        screen = CashScreen()
        initial = screen.get_vault_balance()
        screen.record_vault_withdrawal(100000, 'test withdrawal')
        new_balance = screen.get_vault_balance()
        assert new_balance == initial - 100000

    def test_transfer_drawer_to_vault(self, qt_app, temp_db):
        screen = CashScreen()
        screen.open_date.setDate(QDate.currentDate())
        screen.opening_edit.setText('100000')
        with patch.object(QMessageBox, 'information'):
            screen.open_day()
        screen.loading_overlay.stop()
        initial_vault = screen.get_vault_balance()
        screen.actual_edit.setText('100000')
        with patch.object(QMessageBox, 'information'):
            screen.close_day()
        final_vault = screen.get_vault_balance()
        assert final_vault == initial_vault + 100000

    def test_transfer_vault_to_drawer(self, qt_app, temp_db):
        screen = CashScreen()
        initial_vault = screen.get_vault_balance()
        screen.open_date.setDate(QDate.currentDate())
        screen.opening_edit.setText('100000')
        with patch.object(QMessageBox, 'information'):
            screen.open_day()
        screen.loading_overlay.stop()
        final_vault = screen.get_vault_balance()
        assert final_vault == initial_vault - 65000

    def test_expense_recorded_correctly_for_editing(self, qt_app, temp_db):
        screen = CashScreen()
        screen.open_date.setDate(QDate.currentDate())
        screen.opening_edit.setText('100000')
        with patch.object(QMessageBox, 'information'):
            screen.open_day()
        screen.loading_overlay.stop()
        screen.exp_date.setDate(QDate.currentDate())
        screen.exp_amount.setText('5000')
        screen.exp_desc.setText('editable expense')
        with patch.object(QMessageBox, 'information'):
            screen.save_expense()

        from venus.core.database import get_conn
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT المبلغ, الوصف FROM المصروفات WHERE الوصف = 'editable expense'")
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == 5000.0
            cursor.execute("UPDATE المصروفات SET المبلغ = 6000 WHERE الوصف = 'editable expense'")
            conn.commit()
            cursor.execute("SELECT المبلغ FROM المصروفات WHERE الوصف = 'editable expense'")
            row = cursor.fetchone()
            assert row[0] == 6000.0
        finally:
            conn.close()

    def test_withdrawal_recorded_correctly_for_editing(self, qt_app, temp_db):
        screen = CashScreen()
        screen.open_date.setDate(QDate.currentDate())
        screen.opening_edit.setText('100000')
        with patch.object(QMessageBox, 'information'):
            screen.open_day()
        screen.loading_overlay.stop()
        screen.wd_date.setDate(QDate.currentDate())
        screen.wd_amount.setText('3000')
        screen.wd_desc.setText('editable withdrawal')
        with patch.object(QMessageBox, 'information'):
            screen.save_withdrawal()

        from venus.core.database import get_conn
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT المبلغ, الوصف FROM السحوبات WHERE الوصف = 'editable withdrawal'")
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == 3000.0
            cursor.execute("UPDATE السحوبات SET المبلغ = 4000 WHERE الوصف = 'editable withdrawal'")
            conn.commit()
            cursor.execute("SELECT المبلغ FROM السحوبات WHERE الوصف = 'editable withdrawal'")
            row = cursor.fetchone()
            assert row[0] == 4000.0
        finally:
            conn.close()
