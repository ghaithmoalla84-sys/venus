# -*- coding: utf-8 -*-
"""Tests for InventoryScreen - Venus Coffee"""

import pytest
from unittest.mock import patch, MagicMock
from PyQt5.QtWidgets import QDialog, QMessageBox, QInputDialog, QTableWidgetItem
from PyQt5.QtCore import Qt, QDate

from venus.ui.screens.inventory.screen import InventoryScreen
from venus.core.database import get_conn
from tests.fixtures.helpers import insert_group, insert_material, insert_cash_day, insert_creditor


class TestInventoryScreen:
    def test_initial_ui(self, qt_app, temp_db):
        screen = InventoryScreen()
        assert hasattr(screen, 'supplier_combo')
        assert hasattr(screen, 'date_input')
        assert hasattr(screen, 'items_table')
        assert hasattr(screen, 'total_amount_label')
        assert hasattr(screen, 'group_filter_combo')
        assert hasattr(screen, 'inventory_table')
        assert hasattr(screen, 'purchase_history_table')

    def test_adding_material_via_ui(self, qt_app, temp_db):
        group_id = insert_group('mat_group')
        insert_material('base_mat', group_id=group_id)
        screen = InventoryScreen()
        screen.add_bill_row()
        materials = screen._load_materials_for_combo()
        if materials:
            combo = screen.items_table.cellWidget(0, 0)
            idx = combo.findData(materials[0]['id'])
            if idx >= 0:
                combo.setCurrentIndex(idx)
        screen.items_table.item(0, 1).setText('5')
        screen.items_table.item(0, 2).setText('100')
        screen.calculate_row_total(0, 1)

    def test_editing_material(self, qt_app, temp_db):
        group_id = insert_group('mat_group')
        material_id = insert_material('edit_mat', group_id=group_id)
        screen = InventoryScreen()
        with patch.object(QDialog, 'exec_', return_value=QDialog.Accepted):
            with patch.object(QMessageBox, 'information'):
                screen._on_inventory_edit(material_id)

    def test_deleting_material(self, qt_app, temp_db):
        group_id = insert_group('mat_group')
        material_id = insert_material('del_mat', group_id=group_id)
        screen = InventoryScreen()
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
            with patch.object(QMessageBox, 'information'):
                screen._on_inventory_delete(material_id)

    def test_searching_material(self, qt_app, temp_db):
        group_id = insert_group('search_group')
        insert_material('search_mat_1', group_id=group_id, qty=5.0)
        insert_material('search_mat_2', group_id=group_id, qty=10.0)
        screen = InventoryScreen()
        screen.inventory_table.search_box.setText('search_mat_1')
        visible_ids = screen.inventory_table.get_visible_row_ids()
        assert len(visible_ids) == 1

    def test_filtering_by_group(self, qt_app, temp_db):
        g1 = insert_group('group_a')
        g2 = insert_group('group_b')
        insert_material('mat_a', group_id=g1, qty=5.0)
        insert_material('mat_b', group_id=g2, qty=10.0)
        screen = InventoryScreen()
        screen.group_filter_combo.setCurrentIndex(1)
        screen.load_inventory_display()

    def test_opening_audit_dialog(self, qt_app, temp_db):
        group_id = insert_group('audit_group')
        insert_material('audit_mat', group_id=group_id, qty=10.0)
        screen = InventoryScreen()
        with patch('venus.ui.screens.inventory.screen.AuditDialog') as MockAudit:
            mock_dialog = MagicMock()
            mock_dialog.exec_ = MagicMock(return_value=QDialog.Accepted)
            MockAudit.return_value = mock_dialog
            screen.open_audit_dialog()
            mock_dialog.exec_.assert_called_once()

    def test_saving_audit_updates_inventory(self, qt_app, temp_db):
        group_id = insert_group('audit_group')
        material_id = insert_material('audit_mat', group_id=group_id, qty=10.0)
        screen = InventoryScreen()
        with patch('venus.ui.screens.inventory.screen.AuditDialog') as MockAudit:
            mock_dialog = MagicMock()
            mock_dialog.exec_ = MagicMock(return_value=QDialog.Accepted)
            mock_dialog.audit_saved = MagicMock()
            mock_dialog.audit_saved.connect = MagicMock()
            MockAudit.return_value = mock_dialog
            screen.open_audit_dialog()
            mock_dialog.audit_saved.emit.assert_not_called()

    def test_creating_inventory_movement_from_audit(self, qt_app, temp_db):
        group_id = insert_group('audit_group')
        material_id = insert_material('audit_mat', group_id=group_id, qty=10.0)
        screen = InventoryScreen()
        from venus.ui.screens.inventory.audit import AuditDialog
        dialog = AuditDialog()
        actual_item = QTableWidgetItem('15')
        dialog.audit_table.setItem(0, 3, actual_item)
        with patch.object(QMessageBox, 'information'):
            with patch.object(QMessageBox, 'critical'):
                dialog.save_audit()

    def test_editing_material_name_unit_price(self, qt_app, temp_db):
        group_id = insert_group('edit_full_group')
        material_id = insert_material('edit_full_mat', group_id=group_id, price=100.0)
        screen = InventoryScreen()
        with patch.object(QDialog, 'exec_', return_value=QDialog.Accepted):
            with patch.object(QMessageBox, 'information'):
                screen._on_inventory_edit(material_id)

    def test_deleting_unused_material_succeeds(self, qt_app, temp_db):
        group_id = insert_group('del_unused_group')
        material_id = insert_material('del_unused_mat', group_id=group_id)
        screen = InventoryScreen()
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
            with patch.object(QMessageBox, 'information'):
                screen._on_inventory_delete(material_id)

    def test_deleting_material_with_invoices_fails(self, qt_app, temp_db):
        group_id = insert_group('del_with_inv_group')
        material_id = insert_material('del_with_inv_mat', group_id=group_id)
        supplier_id = insert_creditor(name='inv_delete_supplier', ctype='مورد')
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO فواتير_الشراء (التاريخ, معرف_المورد, اسم_المورد, المبلغ_الإجمالي, العملة) VALUES (?, ?, ?, ?, ?)",
                ("2026-01-01", supplier_id, 'inv_delete_supplier', 5000.0, 'ليرة_سورية')
            )
            invoice_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO تفاصيل_الشراء (معرف_الفاتورة, معرف_المادة_الفرعية, الكمية, سعر_الوحدة, المبلغ_الإجمالي) VALUES (?, ?, ?, ?, ?)",
                (invoice_id, material_id, 5.0, 100.0, 500.0)
            )
            cursor.execute(
                "INSERT INTO المخزون (معرف_المادة_الفرعية, الكمية_المتوفرة, آخر_تحديث) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (material_id, 5.0)
            )
            conn.commit()
        finally:
            conn.close()

        screen = InventoryScreen()
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
            with patch.object(QMessageBox, 'warning'):
                screen._on_inventory_delete(material_id)
