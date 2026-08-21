# -*- coding: utf-8 -*-
"""Tests for SalesScreen - Venus Coffee"""

import pytest
from unittest.mock import patch, MagicMock
from PyQt5.QtWidgets import QDialog, QMessageBox, QInputDialog
from PyQt5.QtCore import Qt, QDate

from venus.ui.screens.sales import SalesScreen
from venus.ui.screens.cash import CashScreen
from tests.fixtures.helpers import insert_group, insert_sale, insert_cash_day


class TestSalesScreen:
    def test_initial_ui(self, qt_app, temp_db):
        screen = SalesScreen()
        assert hasattr(screen, 'date_input')
        assert hasattr(screen, 'entry_table')
        assert hasattr(screen, 'display_table')
        assert hasattr(screen, 'total_label')

    def test_adding_new_sales(self, qt_app, temp_db):
        group_id = insert_group('test_sales_group')
        screen = SalesScreen()
        screen.add_entry_row()
        screen.entry_table.cellWidget(0, 0).setCurrentValue(group_id)
        screen.entry_table.item(0, 1).setText('5000')
        with patch.object(QMessageBox, 'information'):
            screen.save_sales()

    def test_editing_existing_sales(self, qt_app, temp_db):
        group_id = insert_group('test_sales_group')
        sale_id = insert_sale(group_id, amount=5000.0)
        screen = SalesScreen()
        screen._current_sales = [{'معرف': sale_id, 'التاريخ': '2026-08-15', 'المبلغ_الإجمالي': 5000.0, 'ملاحظات': '', 'اسم_المجموعة': 'test_sales_group'}]
        with patch('venus.ui.screens.sales.EditSaleDialog') as MockDialog:
            mock_dialog = MagicMock()
            mock_dialog.exec_ = MagicMock(return_value=QDialog.Accepted)
            mock_dialog.get_data = MagicMock(return_value={'amount': 6000.0, 'notes': 'updated'})
            MockDialog.return_value = mock_dialog
            with patch.object(QMessageBox, 'information'):
                screen._on_edit_requested(0)

    def test_deleting_sales(self, qt_app, temp_db):
        group_id = insert_group('test_sales_group')
        sale_id = insert_sale(group_id, amount=5000.0)
        screen = SalesScreen()
        screen._current_sales = [{'معرف': sale_id, 'التاريخ': '2026-08-15', 'المبلغ_الإجمالي': 5000.0, 'ملاحظات': '', 'اسم_المجموعة': 'test_sales_group'}]
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
            with patch.object(QMessageBox, 'information'):
                screen._on_delete_requested(0)

    def test_adding_multiple_rows(self, qt_app, temp_db):
        group_id = insert_group('test_sales_group')
        screen = SalesScreen()
        screen.add_entry_row()
        screen.add_entry_row()
        screen.add_entry_row()
        screen.entry_table.cellWidget(0, 0).setCurrentValue(group_id)
        screen.entry_table.item(0, 1).setText('1000')
        screen.entry_table.cellWidget(1, 0).setCurrentValue(group_id)
        screen.entry_table.item(1, 1).setText('2000')
        screen.entry_table.cellWidget(2, 0).setCurrentValue(group_id)
        screen.entry_table.item(2, 1).setText('3000')
        with patch.object(QMessageBox, 'information'):
            screen.save_sales()

    def test_selecting_different_groups(self, qt_app, temp_db):
        gid1 = insert_group('group_a')
        gid2 = insert_group('group_b')
        screen = SalesScreen()
        screen.add_entry_row()
        screen.entry_table.cellWidget(0, 0).setCurrentValue(gid1)
        screen.entry_table.item(0, 1).setText('1000')
        screen.add_entry_row()
        screen.entry_table.cellWidget(1, 0).setCurrentValue(gid2)
        screen.entry_table.item(1, 1).setText('2000')
        with patch.object(QMessageBox, 'information'):
            screen.save_sales()

    def test_entering_usd_sales(self, qt_app, temp_db):
        group_id = insert_group('usd_group')
        cash_screen = CashScreen()
        cash_screen.open_date.setDate(QDate(2026, 8, 15))
        cash_screen.opening_edit.setText('1000')
        cash_screen.currency_combo.setCurrentText('دولار')
        with patch.object(QMessageBox, 'information'):
            cash_screen.open_day()
        screen = SalesScreen()
        screen.add_entry_row()
        screen.entry_table.cellWidget(0, 0).setCurrentValue(group_id)
        screen.entry_table.item(0, 1).setText('100')
        with patch.object(QMessageBox, 'information'):
            screen.save_sales()

    def test_editing_sale_amount_and_notes(self, qt_app, temp_db):
        group_id = insert_group('edit_sale_group')
        sale_id = insert_sale(group_id, amount=5000.0, notes='original')
        screen = SalesScreen()
        screen._current_sales = [{'معرف': sale_id, 'التاريخ': '2026-08-15', 'المبلغ_الإجمالي': 5000.0, 'ملاحظات': 'original', 'اسم_المجموعة': 'edit_sale_group'}]
        with patch('venus.ui.screens.sales.EditSaleDialog') as MockDialog:
            mock_dialog = MagicMock()
            mock_dialog.exec_ = MagicMock(return_value=QDialog.Accepted)
            mock_dialog.get_data = MagicMock(return_value={'amount': 7500.0, 'notes': 'updated notes'})
            MockDialog.return_value = mock_dialog
            with patch.object(QMessageBox, 'information'):
                screen._on_edit_requested(0)

        from venus.core.database import get_conn
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT المبلغ_الإجمالي, ملاحظات FROM المبيعات_اليومية WHERE معرف = ?", (sale_id,))
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == 7500.0
            assert row[1] == 'updated notes'
        finally:
            conn.close()
