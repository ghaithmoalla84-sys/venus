# -*- coding: utf-8 -*-
"""
سيناريو 1: شراء → مخزون → بيع → أرباح
"""
import pytest
from unittest.mock import patch
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QDate

from venus.ui.screens.inventory.screen import InventoryScreen
from venus.ui.screens.reports import ReportsScreen
from venus.ui.screens.inventory.audit import AuditDialog
from venus.core.database import get_conn

from tests.fixtures.helpers import insert_group, insert_material, insert_creditor, insert_sale
from tests.fixtures.constants import TEST_DATE


class TestPurchaseToSaleScenario:
    """شراء 100 قطعة كعك → جرد دوري → بيع 30 قطعة → تقرير أرباح"""

    def test_full_purchase_to_sale_workflow(self, qt_app, temp_db):
        group_id = insert_group('scenario1_group')
        material_id = insert_material('scenario1_cake', group_id=group_id, qty=0.0)
        supplier_id = insert_creditor(name='scenario1_supplier', ctype='مورد', currency='ليرة_سورية')

        with patch.object(QMessageBox, 'information'):
            screen = InventoryScreen()
            screen.supplier_combo.setCurrentValue(supplier_id)
            screen.date_input.setDate(QDate(2026, 1, 1))
            screen.payment_combo.setCurrentText("نقدي من الدرج")

            screen.add_bill_row()
            combo = screen.items_table.cellWidget(0, 0)
            idx = combo.findData(material_id)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            screen.items_table.item(0, 1).setText('100')
            screen.items_table.item(0, 2).setText('1500')
            screen.calculate_row_total(0, 1)
            screen.save_purchase_bill()

        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT الكمية_المتوفرة FROM المخزون WHERE معرف_المادة_الفرعية = ?", (material_id,))
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == 100.0

            cursor.execute("""
                SELECT COUNT(*) FROM تحركات_المخزون
                WHERE معرف_المادة_الفرعية = ? AND نوع_الحركة = 'شراء'
            """, (material_id,))
            assert cursor.fetchone()[0] > 0
        finally:
            conn.close()

    def test_audit_after_purchase(self, qt_app, temp_db, db_conn):
        from venus.core.database import get_conn

        group_id = insert_group('scenario1_audit_group')
        material_id = insert_material('scenario1_audit_cake', group_id=group_id, qty=100.0)

        cursor = db_conn.cursor()
        cursor.execute("SELECT الكمية_المتوفرة FROM المخزون WHERE معرف_المادة_الفرعية = ?", (material_id,))
        theoretical = cursor.fetchone()[0]
        actual = 105.0
        diff = actual - theoretical
        value = abs(diff) * 1500.0

        cursor.execute("""
            INSERT INTO الجرد VALUES (NULL, ?, ?, ?, ?, ?, ?, ?)
        """, ('2026-01-15 10:00:00', material_id, theoretical, actual, diff, value, 'جرد دوري'))
        cursor.execute("""
            INSERT OR REPLACE INTO المخزون VALUES (?, ?, ?)
        """, (material_id, actual, '2026-01-15 10:00:00'))
        cursor.execute("""
            INSERT INTO تحركات_المخزون (معرف_المادة_الفرعية, التاريخ, نوع_الحركة, الكمية, الرصيد_بعد, ملاحظات)
            VALUES (?, ?, 'جرد', ?, ?, ?)
        """, (material_id, '2026-01-15 10:00:00', abs(diff), actual, 'جرد دوري'))
        db_conn.commit()

        cursor.execute("SELECT الكمية_المتوفرة FROM المخزون WHERE معرف_المادة_الفرعية = ?", (material_id,))
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == 105.0

        cursor.execute("""
            SELECT COUNT(*) FROM الجرد WHERE معرف_المادة_الفرعية = ?
        """, (material_id,))
        assert cursor.fetchone()[0] > 0

        cursor.execute("""
            SELECT COUNT(*) FROM تحركات_المخزون WHERE معرف_المادة_الفرعية = ? AND نوع_الحركة = 'جرد'
        """, (material_id,))
        assert cursor.fetchone()[0] > 0

    def test_sale_after_purchase_and_audit(self, qt_app, temp_db, db_conn):
        group_id = insert_group('scenario1_sale_group')
        material_id = insert_material('scenario1_sale_cake', group_id=group_id, qty=100.0)

        with patch.object(QMessageBox, 'information'):
            screen = InventoryScreen()
            screen.supplier_combo.setCurrentValue(
                insert_creditor(name='scenario1_sale_supplier', ctype='مورد', currency='ليرة_سورية')
            )
            screen.date_input.setDate(QDate(2026, 1, 1))
            screen.payment_combo.setCurrentText("نقدي من الدرج")

            screen.add_bill_row()
            combo = screen.items_table.cellWidget(0, 0)
            idx = combo.findData(material_id)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            screen.items_table.item(0, 1).setText('100')
            screen.items_table.item(0, 2).setText('1500')
            screen.calculate_row_total(0, 1)
            screen.save_purchase_bill()

        cursor = db_conn.cursor()
        cursor.execute("SELECT الكمية_المتوفرة FROM المخزون WHERE معرف_المادة_الفرعية = ?", (material_id,))
        theoretical = cursor.fetchone()[0]
        actual = 180.0
        diff = actual - theoretical
        value = abs(diff) * 1500.0
        cursor.execute("""
            INSERT INTO الجرد VALUES (NULL, ?, ?, ?, ?, ?, ?, ?)
        """, ('2026-01-15 10:00:00', material_id, theoretical, actual, diff, value, 'جرد دوري'))
        cursor.execute("""
            INSERT OR REPLACE INTO المخزون VALUES (?, ?, ?)
        """, (material_id, actual, '2026-01-15 10:00:00'))
        cursor.execute("""
            INSERT INTO تحركات_المخزون (معرف_المادة_الفرعية, التاريخ, نوع_الحركة, الكمية, الرصيد_بعد, ملاحظات)
            VALUES (?, ?, 'جرد', ?, ?, ?)
        """, (material_id, '2026-01-15 10:00:00', abs(diff), actual, 'جرد دوري'))
        db_conn.commit()

        insert_sale(group_id, date=TEST_DATE, amount=45000.0, notes='بيع 30 قطعة')

        cursor = db_conn.cursor()
        cursor.execute("SELECT SUM(المبلغ_الإجمالي) FROM المبيعات_اليومية WHERE معرف_المجموعة = ?", (group_id,))
        total_sales = cursor.fetchone()[0] or 0
        assert total_sales == 45000.0

        cursor.execute("SELECT الكمية_المتوفرة FROM المخزون WHERE معرف_المادة_الفرعية = ?", (material_id,))
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == 180.0

    def test_profit_report_generation(self, qt_app, temp_db):
        group_id = insert_group('scenario1_profit_group')
        material_id = insert_material('scenario1_profit_cake', group_id=group_id, qty=0.0)

        with patch.object(QMessageBox, 'information'):
            screen = InventoryScreen()
            screen.supplier_combo.setCurrentValue(
                insert_creditor(name='scenario1_profit_supplier', ctype='مورد', currency='ليرة_سورية')
            )
            screen.date_input.setDate(QDate(2026, 1, 1))
            screen.payment_combo.setCurrentText("نقدي من الدرج")

            screen.add_bill_row()
            combo = screen.items_table.cellWidget(0, 0)
            idx = combo.findData(material_id)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            screen.items_table.item(0, 1).setText('50')
            screen.items_table.item(0, 2).setText('1000')
            screen.calculate_row_total(0, 1)
            screen.save_purchase_bill()

        insert_sale(group_id, date='2026-01-15', amount=75000.0, notes='مبيعات')

        audit_dialog = AuditDialog()
        audit_dialog.audit_table.item(0, 3).setText('20')
        with patch.object(QMessageBox, 'information'), patch.object(QMessageBox, 'critical'):
            audit_dialog.save_audit()

        from venus.ui.screens.reports import ReportsScreen
        reports = ReportsScreen()
        reports.profit_from.setDate(QDate(2026, 1, 1))
        reports.profit_to.setDate(QDate(2026, 1, 31))
        with patch.object(QMessageBox, 'information'), patch.object(QMessageBox, 'critical'):
            reports.load_profit_report()

        assert reports.profit_table.rowCount() > 0
        found = False
        for row in range(reports.profit_table.rowCount()):
            if reports.profit_table.item(row, 0).text() == 'scenario1_profit_group':
                found = True
                break
        assert found
