# -*- coding: utf-8 -*-
"""Tests for ReportsScreen - Venus Coffee"""

import pytest
from unittest.mock import patch, MagicMock
from PyQt5.QtWidgets import QDialog, QMessageBox, QFileDialog
from PyQt5.QtCore import Qt, QDate
from datetime import datetime, timedelta

from venus.ui.screens.reports import ReportsScreen
from tests.fixtures.helpers import insert_group, insert_material, insert_sale, insert_cash_day, insert_expense, insert_withdrawal, insert_creditor, insert_invoice, insert_invoice_detail


class TestReportsScreen:
    def test_initial_ui(self, qt_app, temp_db):
        screen = ReportsScreen()
        assert hasattr(screen, 'tabs')
        assert hasattr(screen, 'sales_tab')
        assert hasattr(screen, 'profit_tab')
        assert hasattr(screen, 'inventory_tab')
        assert hasattr(screen, 'debts_tab')
        assert hasattr(screen, 'cash_tab')
        assert hasattr(screen, 'suppliers_tab')
        assert hasattr(screen, 'overdue_tab')
        assert hasattr(screen, 'comparison_tab')

    def test_generating_sales_report_with_date_filters(self, qt_app, temp_db):
        group_id = insert_group('report_group')
        insert_sale(group_id, date='2026-08-10', amount=5000.0)
        insert_sale(group_id, date='2026-08-15', amount=3000.0)
        screen = ReportsScreen()
        screen.sales_from.setDate(QDate(2026, 8, 1))
        screen.sales_to.setDate(QDate(2026, 8, 31))
        screen.load_sales_report()

    def test_generating_inventory_report(self, qt_app, temp_db):
        group_id = insert_group('inv_group')
        insert_material('inv_mat', group_id=group_id, qty=10.0)
        screen = ReportsScreen()
        screen.tabs.setCurrentWidget(screen.inventory_tab)
        screen.load_inventory()

    def test_generating_debts_report(self, qt_app, temp_db):
        insert_creditor(name='report_debtor', balance=5000.0)
        screen = ReportsScreen()
        screen.tabs.setCurrentWidget(screen.debts_tab)
        screen.load_debts()

    def test_generating_cash_movements_report(self, qt_app, temp_db):
        insert_expense('2026-08-15', 2000.0, 'report expense')
        insert_withdrawal('2026-08-15', 1000.0, 'report withdrawal')
        screen = ReportsScreen()
        screen.tabs.setCurrentWidget(screen.cash_tab)

    def test_generating_profit_report(self, qt_app, temp_db):
        group_id = insert_group('profit_group')
        insert_material('profit_mat', group_id=group_id, qty=10.0)
        insert_sale(group_id, date='2026-08-15', amount=5000.0)
        screen = ReportsScreen()
        screen.tabs.setCurrentWidget(screen.profit_tab)
        screen.profit_from.setDate(QDate(2026, 8, 1))
        screen.profit_to.setDate(QDate(2026, 8, 31))
        screen.load_profit_report()

    def test_exporting_report_to_file(self, qt_app, temp_db):
        screen = ReportsScreen()
        with patch.object(QFileDialog, 'getSaveFileName', return_value=('test_report.xlsx', 'Excel Files (*.xlsx)')):
            with patch.object(QMessageBox, 'information'):
                screen.export_table_to_excel(screen.sales_table, 'test.xlsx', 'Test', ['A', 'B'])

    def test_exporting_cash_table_to_excel_legacy_widget(self, qt_app, temp_db):
        insert_cash_day('2026-08-15', opening=100000.0, actual=105000.0, diff=5000.0)
        screen = ReportsScreen()
        screen.cash_from.setDate(QDate(2026, 8, 15))
        screen.cash_to.setDate(QDate(2026, 8, 15))
        screen.load_cash_movements()
        with patch.object(QFileDialog, 'getSaveFileName', return_value=('test_cash.xlsx', 'Excel Files (*.xlsx)')):
            with patch.object(QMessageBox, 'information'):
                screen.export_table_to_excel(screen.cash_table, 'test_cash.xlsx', 'cash', ['A', 'B', 'C'])

    def test_exporting_sales_table_to_pdf_new_widget(self, qt_app, temp_db):
        group_id = insert_group('export_group')
        insert_sale(group_id, date='2026-08-15', amount=5000.0)
        screen = ReportsScreen()
        screen.sales_from.setDate(QDate(2026, 8, 1))
        screen.sales_to.setDate(QDate(2026, 8, 31))
        screen.load_sales_report()
        with patch.object(QFileDialog, 'getSaveFileName', return_value=('test_sales.pdf', 'PDF Files (*.pdf)')):
            with patch.object(QMessageBox, 'information'):
                screen.export_table_to_pdf(screen.sales_table, 'test_sales.pdf', 'sales', ['A', 'B'])

    def test_overdue_report_ordering_and_days(self, qt_app, temp_db):
        today = datetime.now().date()
        due_45 = (today - timedelta(days=45)).strftime('%Y-%m-%d')
        due_10 = (today - timedelta(days=10)).strftime('%Y-%m-%d')

        insert_creditor(name='most_overdue', balance=5000.0, تاريخ_استحقاق=due_45)
        insert_creditor(name='less_overdue', balance=3000.0, تاريخ_استحقاق=due_10)

        screen = ReportsScreen()
        screen.tabs.setCurrentWidget(screen.overdue_tab)
        screen.load_overdue_report()

        table = screen.overdue_table.table
        row_count = table.rowCount()
        assert row_count == 2

        first_name = table.item(0, 0).text()
        first_days = table.item(0, 5).text()
        second_name = table.item(1, 0).text()
        second_days = table.item(1, 5).text()

        assert first_name == 'most_overdue'
        assert int(first_days) >= 45
        assert second_name == 'less_overdue'
        assert int(second_days) >= 10

    def test_tax_report_mixed_currencies_excludes_unregistered(self, qt_app, temp_db):
        real_group_id = insert_group('tax_real_group')
        unregistered_group_id = insert_group('مبيعات غير مسجلة')

        insert_sale(real_group_id, date='2026-08-15', amount=10000.0,
                    currency='ليرة_سورية', notes='registered sale LBP')
        insert_sale(real_group_id, date='2026-08-16', amount=500.0,
                    currency='دولار', notes='registered sale USD')

        insert_sale(unregistered_group_id, date='2026-08-15', amount=99999.0,
                    currency='ليرة_سورية', notes='مبيعات غير مسجلة - تسوية')

        insert_invoice(supplier='tax_supplier', total=8000.0,
                       date='2026-08-15', currency='ليرة_سورية')
        insert_invoice(supplier='tax_supplier_usd', total=300.0,
                       date='2026-08-16', currency='دولار')

        screen = ReportsScreen()
        screen.tax_from.setDate(QDate(2026, 8, 1))
        screen.tax_to.setDate(QDate(2026, 8, 31))
        screen.load_tax_report()

        table = screen.tax_table
        assert table.rowCount() == 3

        assert table.item(0, 0).text() == 'إجمالي المبيعات'
        assert table.item(0, 1).text() == '10,000'
        assert table.item(0, 2).text() == '500'

        assert table.item(1, 0).text() == 'إجمالي المشتريات'
        assert table.item(1, 1).text() == '8,000'
        assert table.item(1, 2).text() == '300'

        assert table.item(2, 0).text() == 'الفرق (مبيعات − مشتريات)'
        assert table.item(2, 1).text() == '2,000'
        assert table.item(2, 2).text() == '200'

        summary = screen.tax_summary_label.text()
        assert 'ليرة: مبيعات' in summary
        assert 'دولار: مبيعات' in summary
        assert 'ربحاً صافياً حقيقياً' in summary

    def test_tax_report_empty_period_no_data(self, qt_app, temp_db):
        screen = ReportsScreen()
        screen.tax_from.setDate(QDate(2026, 8, 1))
        screen.tax_to.setDate(QDate(2026, 8, 31))
        screen.load_tax_report()

        table = screen.tax_table
        assert table.rowCount() == 3

        assert table.item(0, 0).text() == 'إجمالي المبيعات'
        assert table.item(0, 1).text() == '0'
        assert table.item(0, 2).text() == '0'

        assert table.item(1, 0).text() == 'إجمالي المشتريات'
        assert table.item(1, 1).text() == '0'
        assert table.item(1, 2).text() == '0'

        assert table.item(2, 0).text() == 'الفرق (مبيعات − مشتريات)'
        assert table.item(2, 1).text() == '0'
        assert table.item(2, 2).text() == '0'

        summary = screen.tax_summary_label.text()
        assert 'ليرة: 0' in summary
        assert 'ربحاً صافياً حقيقياً' in summary

    def test_best_suppliers_two_suppliers_sorted_by_price(self, qt_app, temp_db):
        group_id = insert_group('best_supplier_group')
        material_id = insert_material('mat_two_suppliers', group_id=group_id)

        invoice_a_id = insert_invoice(
            supplier='supplier_A', total=500.0,
            date='2026-08-01', currency='ليرة_سورية'
        )
        insert_invoice_detail(invoice_a_id, material_id, qty=5.0, price=100.0)

        invoice_b_id = insert_invoice(
            supplier='supplier_B', total=200.0,
            date='2026-08-02', currency='ليرة_سورية'
        )
        insert_invoice_detail(invoice_b_id, material_id, qty=2.0, price=50.0)

        screen = ReportsScreen()
        screen.load_best_suppliers_report()

        table = screen.best_suppliers_table.table
        assert table.rowCount() == 2

        assert table.item(0, 0).text() == 'mat_two_suppliers'
        assert table.item(0, 1).text() == 'supplier_B'
        assert table.item(0, 2).text() == '50'

        assert table.item(1, 0).text() == 'mat_two_suppliers'
        assert table.item(1, 1).text() == 'supplier_A'
        assert table.item(1, 2).text() == '100'

    def test_best_suppliers_single_supplier_excluded(self, qt_app, temp_db):
        group_id = insert_group('best_supplier_single_group')
        material_id = insert_material('mat_one_supplier', group_id=group_id)

        invoice_id = insert_invoice(
            supplier='supplier_C', total=300.0,
            date='2026-08-01', currency='ليرة_سورية'
        )
        insert_invoice_detail(invoice_id, material_id, qty=3.0, price=80.0)

        screen = ReportsScreen()
        screen.load_best_suppliers_report()

        table = screen.best_suppliers_table.table
        assert table.rowCount() == 0

    def test_sales_chart_by_category_shows_correct_values(self, qt_app, temp_db):
        g1 = insert_group('chart_cat_a')
        g2 = insert_group('chart_cat_b')
        g3 = insert_group('chart_cat_c')
        insert_sale(g1, date='2026-08-10', amount=1000.0)
        insert_sale(g2, date='2026-08-15', amount=3000.0)
        insert_sale(g3, date='2026-08-20', amount=2000.0)

        screen = ReportsScreen()
        screen.sales_from.setDate(QDate(2026, 8, 1))
        screen.sales_to.setDate(QDate(2026, 8, 31))
        screen.load_sales_report()

        chart = screen.sales_chart_widget
        assert chart.empty_label.isHidden()

        data = chart._data
        assert len(data) == 3

        data_map = {label: value for label, value in data}
        assert data_map['chart_cat_a'] == 1000.0
        assert data_map['chart_cat_b'] == 3000.0
        assert data_map['chart_cat_c'] == 2000.0
        assert not screen.sales_chart_note.isVisible()

    def test_sales_chart_empty_period_shows_empty_message(self, qt_app, temp_db):
        screen = ReportsScreen()
        screen.sales_from.setDate(QDate(2026, 8, 1))
        screen.sales_to.setDate(QDate(2026, 8, 31))
        screen.load_sales_report()

        chart = screen.sales_chart_widget
        assert not chart.empty_label.isHidden()
        assert "لا توجد بيانات مبيعات كافية لعرض الرسم البياني" in chart.empty_label.text()
        assert chart._data == []
        assert not screen.sales_chart_note.isVisible()
