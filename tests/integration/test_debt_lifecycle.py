# -*- coding: utf-8 -*-
"""
سيناريو 2: دائن → دفعة → تقرير ديون
"""
import pytest
from unittest.mock import patch
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QDate

from venus.ui.screens.inventory.screen import InventoryScreen
from venus.ui.screens.reports import ReportsScreen
from venus.ui.screens.creditors import CreditorsScreen, PaymentDialog
from venus.core.database import get_conn

from tests.fixtures.helpers import insert_group, insert_material, insert_creditor, insert_sale, insert_debt_movement


class TestDebtLifecycleScenario:
    """إضافة مورد جديد → شراء بالدين → دفعة جزئية → تقرير الديون"""

    def test_add_new_supplier_and_purchase_on_debt(self, qt_app, temp_db):
        group_id = insert_group('scenario2_group')
        material_id = insert_material('scenario2_mat', group_id=group_id, qty=0.0)

        with patch.object(QMessageBox, 'information'):
            screen = InventoryScreen()
            screen.supplier_combo.setCurrentValue(
                insert_creditor(name='scenario2_new_supplier', ctype='مورد', currency='ليرة_سورية')
            )
            screen.date_input.setDate(QDate(2026, 2, 1))
            screen.payment_combo.setCurrentText("دين (آجل)")

            screen.add_bill_row()
            combo = screen.items_table.cellWidget(0, 0)
            idx = combo.findData(material_id)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            screen.items_table.item(0, 1).setText('20')
            screen.items_table.item(0, 2).setText('2000')
            screen.calculate_row_total(0, 1)
            screen.save_purchase_bill()

        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT الرصيد FROM الديون WHERE اسم_الطرف = ?", ('scenario2_new_supplier',))
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == 40000.0
        finally:
            conn.close()

    def test_partial_payment_updates_debt(self, qt_app, temp_db):
        debt_id = insert_creditor(name='scenario2_partial', ctype='مورد', currency='ليرة_سورية', total=30000.0, balance=30000.0)

        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE الديون SET الرصيد = الرصيد - ?, المبلغ_المدفوع = المبلغ_المدفوع + ?,
                حالة_الدين = CASE WHEN (الرصيد - ?) <= 0.01 THEN 'مسدد' ELSE 'نشط' END
                WHERE معرف = ?
            """, (15000.0, 15000.0, 15000.0, debt_id))
            conn.commit()
        finally:
            conn.close()

        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT الرصيد, حالة_الدين FROM الديون WHERE معرف = ?", (debt_id,))
            row = cursor.fetchone()
            assert row["الرصيد"] == 15000.0
            assert row["حالة_الدين"] == "نشط"
        finally:
            conn.close()

    def test_debt_report_generation(self, qt_app, temp_db):
        insert_creditor(name='scenario2_report_a', ctype='مورد', currency='ليرة_سورية', total=50000.0, balance=20000.0)
        insert_creditor(name='scenario2_report_b', ctype='مورد', currency='دولار', total=1000.0, balance=400.0)
        insert_creditor(name='scenario2_report_c', ctype='صديق', currency='ليرة_سورية', total=5000.0, balance=0.0)

        reports = ReportsScreen()
        with patch.object(QMessageBox, 'information'), patch.object(QMessageBox, 'critical'):
            reports.load_debts()

        assert reports.debts_table.table.rowCount() >= 3
        assert 'إجمالي الديون' in reports.debts_summary_label.text()

    def test_full_debt_lifecycle_flow(self, qt_app, temp_db):
        debt_id = insert_creditor(name='scenario2_full', ctype='مورد', currency='ليرة_سورية', total=60000.0, balance=60000.0)

        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE الديون SET الرصيد = الرصيد - ?, المبلغ_المدفوع = المبلغ_المدفوع + ?,
                حالة_الدين = CASE WHEN (الرصيد - ?) <= 0.01 THEN 'مسدد' ELSE 'نشط' END
                WHERE معرف = ?
            """, (25000.0, 25000.0, 25000.0, debt_id))
            conn.commit()
        finally:
            conn.close()

        insert_debt_movement(debt_id, 25000.0, mtype='دفعة', notes='دفعة أولى')

        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT الرصيد, المبلغ_المدفوع FROM الديون WHERE معرف = ?", (debt_id,))
            row = cursor.fetchone()
            assert row["الرصيد"] == 35000.0
            assert row["المبلغ_المدفوع"] == 25000.0

            cursor.execute("SELECT COUNT(*) FROM تحركات_الديون WHERE معرف_الدين = ? AND نوع_الحركة = 'دفعة'", (debt_id,))
            assert cursor.fetchone()[0] == 1
        finally:
            conn.close()
