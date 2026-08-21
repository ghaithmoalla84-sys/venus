# -*- coding: utf-8 -*-
"""Tests for DashboardScreen - Venus Coffee"""

import pytest
from unittest.mock import patch, MagicMock
from PyQt5.QtWidgets import QDialog, QMessageBox
from PyQt5.QtCore import Qt, QDate

from venus.ui.screens.dashboard import DashboardScreen
from tests.fixtures.helpers import insert_group, insert_material, insert_sale, insert_cash_day, insert_expense
from venus.core.database import get_conn


class TestDashboardScreen:
    def test_initial_ui(self, qt_app, temp_db):
        with patch.object(QMessageBox, 'warning'):
            screen = DashboardScreen()
        assert hasattr(screen, 'card_cash')
        assert hasattr(screen, 'card_sales')
        assert hasattr(screen, 'card_expenses')
        assert hasattr(screen, 'card_inventory')
        assert hasattr(screen, 'card_debts')
        assert hasattr(screen, 'sales_group')
        assert hasattr(screen, 'debts_group')
        assert hasattr(screen, 'low_stock_group')
        assert hasattr(screen, 'refresh_btn')
        assert hasattr(screen, 'journal_alert')
        assert hasattr(screen, 'top_sellers_group')
        assert hasattr(screen, 'top_sellers_msg')

    def test_loading_data_on_open(self, qt_app, temp_db):
        with patch.object(QMessageBox, 'warning'):
            screen = DashboardScreen()
            screen.refresh_data()

    def test_displaying_total_sales(self, qt_app, temp_db):
        group_id = insert_group('dash_sales')
        insert_sale(group_id, amount=5000.0)
        with patch.object(QMessageBox, 'warning'):
            screen = DashboardScreen()
            screen.refresh_data()

    def test_displaying_total_expenses(self, qt_app, temp_db):
        insert_expense('2026-08-15', 3000.0, 'test expense')
        with patch.object(QMessageBox, 'warning'):
            screen = DashboardScreen()
            screen.refresh_data()

    def test_displaying_cash_balance(self, qt_app, temp_db):
        insert_cash_day('2026-08-15', opening=100000, actual=100000, diff=0, closed=True)
        with patch.object(QMessageBox, 'warning'):
            screen = DashboardScreen()
            screen.refresh_data()

    def test_displaying_material_count(self, qt_app, temp_db):
        group_id = insert_group('dash_mat')
        insert_material('dash_mat_1', group_id=group_id, qty=5.0)
        insert_material('dash_mat_2', group_id=group_id, qty=10.0)
        with patch.object(QMessageBox, 'warning'):
            screen = DashboardScreen()
            screen.refresh_data()

    def test_updating_after_data_changed_signal(self, qt_app, temp_db):
        from venus.core.events import app_events
        with patch.object(QMessageBox, 'warning'):
            screen = DashboardScreen()
        with patch.object(screen, 'refresh_data') as mock_refresh:
            screen._on_app_data_changed('sales')
            mock_refresh.assert_called_once()

    def test_journal_alert_shown_when_no_cash_day(self, qt_app, temp_db):
        with patch.object(QMessageBox, 'warning'):
            screen = DashboardScreen()
            screen.refresh_data()
        assert not screen.journal_alert.isHidden()
        assert "لم تُفتح اليومية" in screen.journal_alert.text()

    def test_journal_alert_hidden_when_cash_day_open(self, qt_app, temp_db):
        with patch('venus.ui.screens.dashboard.today_str', return_value="2026-08-15"):
            insert_cash_day('2026-08-15', opening=100000, actual=0, diff=0, closed=False)
            with patch.object(QMessageBox, 'warning'):
                screen = DashboardScreen()
                screen.refresh_data()
            assert screen.journal_alert.isHidden()

    def test_journal_alert_hidden_when_cash_day_closed(self, qt_app, temp_db):
        with patch('venus.ui.screens.dashboard.today_str', return_value="2026-08-15"):
            insert_cash_day('2026-08-15', opening=100000, actual=100000, diff=0, closed=True)
            with patch.object(QMessageBox, 'warning'):
                screen = DashboardScreen()
                screen.refresh_data()
            assert screen.journal_alert.isHidden()

    def test_low_stock_distinguishes_out_of_stock(self, qt_app, temp_db):
        group_id = insert_group('dash_low')
        mid_zero = insert_material('dash_zero', group_id=group_id, qty=0.0)
        mid_low = insert_material('dash_low1', group_id=group_id, qty=3.0)
        conn = get_conn()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO المخزون (معرف_المادة_الفرعية, الكمية_المتوفرة, آخر_تحديث) "
                "VALUES (?, ?, CURRENT_TIMESTAMP)", (mid_zero, 0.0)
            )
            conn.execute(
                "UPDATE المواد_الفرعية SET الحد_الأدنى = 5 WHERE معرف IN (?, ?)",
                (mid_zero, mid_low)
            )
            conn.commit()
        finally:
            conn.close()
        with patch.object(QMessageBox, 'warning'):
            screen = DashboardScreen()
            screen.refresh_data()
        table = screen.low_stock_group.table
        assert table.rowCount() == 2
        zero_item = table.item(0, 2)
        low_item = table.item(1, 2)
        assert zero_item.text() == "نفذت الكمية"
        assert zero_item.font().bold()
        assert low_item.text() == "3.00"

    def test_top_sellers_more_than_3_groups_unregistered_excluded(self, qt_app, temp_db):
        with patch('venus.core.database.today_str', return_value="2026-08-15"):
            unreg_id = insert_group('مبيعات غير مسجلة')
            insert_sale(unreg_id, date='2026-08-10', amount=5000.0)

            g1 = insert_group('group_a')
            g2 = insert_group('group_b')
            g3 = insert_group('group_c')
            g4 = insert_group('group_d')
            insert_sale(g1, date='2026-08-05', amount=1000.0)
            insert_sale(g2, date='2026-08-06', amount=2000.0)
            insert_sale(g3, date='2026-08-07', amount=3000.0)
            insert_sale(g4, date='2026-08-08', amount=4000.0)

            with patch.object(QMessageBox, 'warning'):
                screen = DashboardScreen()
                screen.refresh_data()

            table = screen.top_sellers_group.table
            assert not table.isHidden()
            assert not screen.top_sellers_msg.isVisible()
            assert table.rowCount() == 3

            rows = {table.item(r, 0).text(): table.item(r, 1).text() for r in range(table.rowCount())}
            assert rows['group_d'] == '4,000'
            assert rows['group_c'] == '3,000'
            assert rows['group_b'] == '2,000'

    def test_top_sellers_fewer_than_3_groups(self, qt_app, temp_db):
        with patch('venus.core.database.today_str', return_value="2026-08-15"):
            g1 = insert_group('group_a')
            g2 = insert_group('group_b')
            insert_sale(g1, date='2026-08-05', amount=1000.0)
            insert_sale(g2, date='2026-08-06', amount=2000.0)

            with patch.object(QMessageBox, 'warning'):
                screen = DashboardScreen()
                screen.refresh_data()

            table = screen.top_sellers_group.table
            assert not table.isHidden()
            assert not screen.top_sellers_msg.isVisible()
            assert table.rowCount() == 2
            assert table.item(0, 0).text() == 'group_b'
            assert table.item(0, 1).text() == '2,000'
            assert table.item(1, 0).text() == 'group_a'
            assert table.item(1, 1).text() == '1,000'

    def test_top_sellers_no_sales_shows_message(self, qt_app, temp_db):
        with patch('venus.core.database.today_str', return_value="2026-08-15"):
            with patch.object(QMessageBox, 'warning'):
                screen = DashboardScreen()
                screen.refresh_data()

            assert screen.top_sellers_group.table.isHidden()
            assert not screen.top_sellers_msg.isHidden()
            assert "لا توجد مبيعات مسجلة هذا الشهر بعد" in screen.top_sellers_msg.text()

    def test_sales_chart_distributed_days_with_zeros(self, qt_app, temp_db):
        with patch('venus.core.database.today_str', return_value="2026-08-15"):
            unreg_id = insert_group('مبيعات غير مسجلة')
            insert_sale(unreg_id, date='2026-08-12', amount=5000.0)

            g1 = insert_group('chart_group_a')
            insert_sale(g1, date='2026-08-15', amount=3000.0)
            insert_sale(g1, date='2026-08-13', amount=2000.0)

            with patch.object(QMessageBox, 'warning'):
                screen = DashboardScreen()
                screen.refresh_data()

            chart = screen.sales_chart_widget
            assert chart.empty_label.isHidden()

            data = chart._data
            assert len(data) == 7

            day_map = {label: value for label, value in data}
            assert day_map["15/08"] == 3000.0
            assert day_map["13/08"] == 2000.0
            assert day_map["14/08"] == 0
            assert day_map["12/08"] == 0

    def test_sales_chart_all_zeros_shows_empty_message(self, qt_app, temp_db):
        with patch('venus.core.database.today_str', return_value="2026-08-15"):
            with patch.object(QMessageBox, 'warning'):
                screen = DashboardScreen()
                screen.refresh_data()

            chart = screen.sales_chart_widget
            assert not chart.empty_label.isHidden()
            assert "لا توجد بيانات مبيعات كافية لعرض الرسم البياني" in chart.empty_label.text()
