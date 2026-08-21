# -*- coding: utf-8 -*-
"""Tests for purchase invoice operations via InventoryScreen UI"""

import pytest
from unittest.mock import patch, MagicMock
from PyQt5.QtWidgets import QDialog, QMessageBox
from PyQt5.QtCore import QDate

from venus.ui.screens.inventory.screen import InventoryScreen
from venus.core.database import get_conn
from tests.fixtures.helpers import insert_group, insert_material, insert_creditor, insert_vault_balance


class TestPurchaseInvoices:
    def test_full_cash_purchase_from_drawer(self, qt_app, temp_db):
        group_id = insert_group('cash_purchase_group')
        material_id = insert_material('cash_purchase_mat', group_id=group_id, qty=0.0)
        supplier_id = insert_creditor(name='cash_supplier', ctype='مورد', currency='ليرة_سورية')

        screen = InventoryScreen()
        screen.supplier_combo.setCurrentValue(supplier_id)
        screen.date_input.setDate(QDate(2026, 1, 1))
        screen.payment_combo.setCurrentText("نقدي من الدرج")

        screen.add_bill_row()
        combo = screen.items_table.cellWidget(0, 0)
        idx = combo.findData(material_id)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        screen.items_table.item(0, 1).setText('5')
        screen.items_table.item(0, 2).setText('1000')
        screen.calculate_row_total(0, 1)

        with patch.object(QMessageBox, 'information'):
            screen.save_purchase_bill()

        from venus.core.database import get_conn
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM فواتير_الشراء WHERE اسم_المورد = 'cash_supplier'")
            assert cursor.fetchone()[0] > 0
            cursor.execute("SELECT المبلغ FROM السحوبات WHERE الوصف LIKE 'شراء - cash_supplier%'")
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == 5000.0
        finally:
            conn.close()

    def test_full_cash_purchase_from_vault(self, qt_app, temp_db):
        group_id = insert_group('vault_purchase_group')
        material_id = insert_material('vault_purchase_mat', group_id=group_id, qty=0.0)
        supplier_id = insert_creditor(name='vault_supplier', ctype='مورد', currency='ليرة_سورية')

        screen = InventoryScreen()
        screen.supplier_combo.setCurrentValue(supplier_id)
        screen.date_input.setDate(QDate(2026, 1, 1))
        screen.payment_combo.setCurrentText("نقدي من الخزنة")

        screen.add_bill_row()
        combo = screen.items_table.cellWidget(0, 0)
        idx = combo.findData(material_id)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        screen.items_table.item(0, 1).setText('3')
        screen.items_table.item(0, 2).setText('2000')
        screen.calculate_row_total(0, 1)

        with patch.object(QMessageBox, 'information'):
            screen.save_purchase_bill()

        from venus.core.database import get_conn
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM فواتير_الشراء WHERE اسم_المورد = 'vault_supplier'")
            assert cursor.fetchone()[0] > 0
            cursor.execute("SELECT COUNT(*) FROM تحويلات_الصندوق WHERE من_حساب = 'الخزنة' AND إلى_حساب = 'الخارجي'")
            assert cursor.fetchone()[0] > 0
        finally:
            conn.close()

    def test_full_debt_purchase(self, qt_app, temp_db):
        group_id = insert_group('debt_purchase_group')
        material_id = insert_material('debt_purchase_mat', group_id=group_id, qty=0.0)
        supplier_id = insert_creditor(name='debt_supplier', ctype='مورد', currency='ليرة_سورية')

        screen = InventoryScreen()
        screen.supplier_combo.setCurrentValue(supplier_id)
        screen.date_input.setDate(QDate(2026, 1, 1))
        screen.payment_combo.setCurrentText("دين (آجل)")

        screen.add_bill_row()
        combo = screen.items_table.cellWidget(0, 0)
        idx = combo.findData(material_id)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        screen.items_table.item(0, 1).setText('10')
        screen.items_table.item(0, 2).setText('500')
        screen.calculate_row_total(0, 1)

        with patch.object(QMessageBox, 'information'):
            screen.save_purchase_bill()

        from venus.core.database import get_conn
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT المبلغ_الإجمالي, الرصيد FROM الديون WHERE معرف = ?", (supplier_id,))
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == 5000.0
            assert row[1] == 5000.0
            cursor.execute("SELECT COUNT(*) FROM تحركات_الديون WHERE معرف_الدين = ? AND نوع_الحركة = 'إضافة'", (supplier_id,))
            assert cursor.fetchone()[0] > 0
        finally:
            conn.close()

    def test_multiple_items_in_invoice(self, qt_app, temp_db):
        group_id = insert_group('multi_item_group')
        mat1_id = insert_material('multi_mat_1', group_id=group_id, qty=0.0)
        mat2_id = insert_material('multi_mat_2', group_id=group_id, qty=0.0)
        supplier_id = insert_creditor(name='multi_supplier', ctype='مورد', currency='ليرة_سورية')

        screen = InventoryScreen()
        screen.supplier_combo.setCurrentValue(supplier_id)
        screen.date_input.setDate(QDate(2026, 1, 1))
        screen.payment_combo.setCurrentText("نقدي من الدرج")

        screen.add_bill_row()

        combo = screen.items_table.cellWidget(0, 0)
        idx = combo.findData(mat1_id)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        screen.items_table.item(0, 1).setText('5')
        screen.items_table.item(0, 2).setText('1000')
        screen.calculate_row_total(0, 1)

        screen.add_bill_row()

        combo2 = screen.items_table.cellWidget(1, 0)
        idx2 = combo2.findData(mat2_id)
        if idx2 >= 0:
            combo2.setCurrentIndex(idx2)
        screen.items_table.item(1, 1).setText('3')
        screen.items_table.item(1, 2).setText('2000')
        screen.calculate_row_total(1, 1)

        assert screen.total_amount_label.text() == '11000.0'

        with patch.object(QMessageBox, 'information'):
            screen.save_purchase_bill()

        from venus.core.database import get_conn
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM تفاصيل_الشراء WHERE معرف_المادة_الفرعية IN (?, ?)", (mat1_id, mat2_id))
            assert cursor.fetchone()[0] == 2
        finally:
            conn.close()

    def test_auto_total_calculation(self, qt_app, temp_db):
        group_id = insert_group('total_calc_group')
        material_id = insert_material('total_calc_mat', group_id=group_id, qty=0.0)

        screen = InventoryScreen()
        screen.add_bill_row()
        combo = screen.items_table.cellWidget(0, 0)
        idx = combo.findData(material_id)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        screen.items_table.item(0, 1).setText('4')
        screen.items_table.item(0, 2).setText('2500')

        screen.calculate_row_total(0, 1)

        total_item = screen.items_table.item(0, 3)
        assert float(total_item.text()) == 10000.0
        assert screen.total_amount_label.text() == '10000.0'

    def test_save_invoice_updates_inventory_and_creates_debt_movement(self, qt_app, temp_db):
        group_id = insert_group('inv_update_group')
        material_id = insert_material('inv_update_mat', group_id=group_id, qty=0.0)
        supplier_id = insert_creditor(name='inv_update_supplier', ctype='مورد', currency='ليرة_سورية')

        screen = InventoryScreen()
        screen.supplier_combo.setCurrentValue(supplier_id)
        screen.date_input.setDate(QDate(2026, 1, 1))
        screen.payment_combo.setCurrentText("دين (آجل)")

        screen.add_bill_row()
        combo = screen.items_table.cellWidget(0, 0)
        idx = combo.findData(material_id)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        screen.items_table.item(0, 1).setText('8')
        screen.items_table.item(0, 2).setText('1500')
        screen.calculate_row_total(0, 1)

        with patch.object(QMessageBox, 'information'):
            screen.save_purchase_bill()

        from venus.core.database import get_conn
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT الكمية_المتوفرة FROM المخزون WHERE معرف_المادة_الفرعية = ?", (material_id,))
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == 8.0
            cursor.execute("SELECT COUNT(*) FROM تحركات_المخزون WHERE معرف_المادة_الفرعية = ? AND نوع_الحركة = 'شراء'", (material_id,))
            assert cursor.fetchone()[0] > 0
            cursor.execute("SELECT COUNT(*) FROM تحركات_الديون WHERE معرف_الدين = ? AND نوع_الحركة = 'إضافة'", (supplier_id,))
            assert cursor.fetchone()[0] > 0
            cursor.execute("SELECT سعر_الشراء_الأخير FROM المواد_الفرعية WHERE معرف = ?", (material_id,))
            row = cursor.fetchone()
            assert row[0] == 1500.0
        finally:
            conn.close()
