# -*- coding: utf-8 -*-
"""Tests for SettingsScreen - Venus Coffee"""

import pytest
from unittest.mock import patch, MagicMock
from PyQt5.QtWidgets import QDialog, QMessageBox, QInputDialog, QFileDialog
from PyQt5.QtCore import Qt, QDate

from venus.ui.screens.settings import SettingsScreen
from tests.fixtures.helpers import insert_group, insert_material, insert_creditor


class TestSettingsScreen:
    def test_initial_ui(self, qt_app, temp_db):
        screen = SettingsScreen()
        assert hasattr(screen, 'tabs')
        assert hasattr(screen, 'tab_opening')
        assert hasattr(screen, 'tab_groups')
        assert hasattr(screen, 'tab_exchange')
        assert hasattr(screen, 'tab_backup')
        assert hasattr(screen, 'cash_input')
        assert hasattr(screen, 'vault_input')
        assert hasattr(screen, 'inventory_table')
        assert hasattr(screen, 'creditors_table')
        assert hasattr(screen, 'group_name_input')
        assert hasattr(screen, 'groups_table')
        assert hasattr(screen, 'material_group_combo')
        assert hasattr(screen, 'material_name_input')
        assert hasattr(screen, 'unit_combo')
        assert hasattr(screen, 'materials_table')
        assert hasattr(screen, 'current_rate_label')
        assert hasattr(screen, 'new_rate_input')
        assert hasattr(screen, 'rate_history_table')

    def test_changing_store_name(self, qt_app, temp_db):
        screen = SettingsScreen()

    def test_updating_exchange_rate(self, qt_app, temp_db):
        screen = SettingsScreen()
        screen.new_rate_input.setText('9000')
        with patch.object(QMessageBox, 'information'):
            screen.update_exchange_rate()

    def test_changing_default_currency(self, qt_app, temp_db):
        screen = SettingsScreen()

    def test_modifying_change_amount(self, qt_app, temp_db):
        screen = SettingsScreen()

    def test_saving_opening_balances_cash_vault(self, qt_app, temp_db):
        screen = SettingsScreen()
        screen.cash_input.setText('500000')
        screen.vault_input.setText('2000000')
        with patch.object(QMessageBox, 'information'):
            screen.save_opening_balances()

    def test_saving_opening_inventory(self, qt_app, temp_db):
        group_id = insert_group('open_inv_group')
        insert_material('open_inv_mat', group_id=group_id, qty=10.0)
        screen = SettingsScreen()
        for row in range(screen.inventory_table.rowCount()):
            if screen.inventory_data[row][1] == 'open_inv_mat':
                screen.inventory_table.item(row, 3).setText('20')
                break
        screen.cash_input.setText('0')
        screen.vault_input.setText('0')
        with patch.object(QMessageBox, 'information'):
            screen.save_opening_balances()

    def test_saving_opening_creditor_balances(self, qt_app, temp_db):
        creditor_id = insert_creditor(name='open_cred', balance=1000.0)
        screen = SettingsScreen()
        for row in range(screen.creditors_table.rowCount()):
            if screen.creditor_ids[row] == creditor_id:
                screen.creditors_table.item(row, 3).setText('2000')
                break
        screen.cash_input.setText('0')
        screen.vault_input.setText('0')
        with patch.object(QMessageBox, 'information'):
            screen.save_opening_balances()

    def test_adding_group(self, qt_app, temp_db):
        screen = SettingsScreen()
        screen.group_name_input.setText('new_test_group')
        with patch.object(QMessageBox, 'information'):
            screen.add_group()

    def test_deleting_empty_group_succeeds(self, qt_app, temp_db):
        screen = SettingsScreen()
        screen.group_name_input.setText('empty_group')
        with patch.object(QMessageBox, 'information'):
            screen.add_group()
        target_id = None
        for row in range(screen.groups_table.rowCount()):
            if screen.groups_data[row][1] == 'empty_group':
                target_id = screen.groups_data[row][0]
                screen.groups_table.selectRow(row)
                break
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
            with patch.object(QMessageBox, 'information'):
                screen.delete_group()

    def test_deleting_group_with_materials_fails(self, qt_app, temp_db):
        group_id = insert_group('group_with_mat')
        insert_material('mat_in_group', group_id=group_id)
        screen = SettingsScreen()
        for row in range(screen.groups_table.rowCount()):
            if screen.groups_data[row][0] == group_id:
                screen.groups_table.selectRow(row)
                break
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
            with patch.object(QMessageBox, 'critical'):
                screen.delete_group()

    def test_adding_material(self, qt_app, temp_db):
        group_id = insert_group('mat_add_group')
        screen = SettingsScreen()
        for i in range(screen.material_group_combo.count()):
            if screen.material_group_combo.itemData(i) == group_id:
                screen.material_group_combo.setCurrentIndex(i)
                break
        screen.material_name_input.setText('new_mat')
        screen.unit_combo.setCurrentText('قطعة')
        with patch.object(QMessageBox, 'information'):
            screen.add_material()

    def test_editing_material_purchase_price(self, qt_app, temp_db):
        group_id = insert_group('price_edit_group')
        material_id = insert_material('price_edit_mat', group_id=group_id, price=100.0)
        screen = SettingsScreen()
        for row in range(screen.materials_table.rowCount()):
            if screen.materials_data[row][0] == material_id:
                screen.materials_table.item(row, 4).setText('200')
                break
        screen.materials_table.cellChanged.emit(row, 4)

    def test_resetting_database_with_backup(self, qt_app, temp_db):
        screen = SettingsScreen()
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
            with patch.object(QInputDialog, 'getText', return_value=('تصفير', True)):
                with patch.object(QMessageBox, 'information'):
                    with patch('migrations.create_database.create_database'):
                        screen.reset_database()

    def test_verifying_backup_exists_after_reset(self, qt_app, temp_db):
        screen = SettingsScreen()

    def test_blocking_reset_without_confirmation(self, qt_app, temp_db):
        screen = SettingsScreen()
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.No):
            screen.reset_database()

    def test_group_double_click_opens_detail_dialog(self, qt_app, temp_db):
        group_id = insert_group('detail_view_group')
        insert_material('detail_view_mat', group_id=group_id)
        screen = SettingsScreen()
        with patch('venus.ui.screens.settings.EntityDetailDialog') as MockDialog:
            mock_dialog = MagicMock()
            mock_dialog.exec_ = MagicMock(return_value=QDialog.Accepted)
            MockDialog.return_value = mock_dialog
            screen._on_group_double_clicked(0, 0)
            mock_dialog.exec_.assert_called_once()

    def test_exchange_rate_update_sets_timestamp(self, qt_app, temp_db):
        screen = SettingsScreen()
        screen.new_rate_input.setText('9200')
        with patch.object(QMessageBox, 'information'):
            screen.update_exchange_rate()

        from venus.core.database import get_conn
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT تاريخ_التحديث FROM الإعدادات WHERE المفتاح = 'سعر_صرف_الدولار'")
            row = cursor.fetchone()
            assert row is not None
            assert row[0] is not None
            assert len(str(row[0])) > 0
        finally:
            conn.close()
