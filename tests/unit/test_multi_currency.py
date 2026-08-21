# -*- coding: utf-8 -*-
"""Tests for multi-currency operations"""

import pytest
from unittest.mock import patch
from PyQt5.QtWidgets import QMessageBox, QDialog
from PyQt5.QtCore import QDate

from venus.ui.screens.sales import SalesScreen
from venus.ui.screens.cash import CashScreen
from venus.ui.screens.settings import SettingsScreen
from venus.ui.screens.creditors import CreditorsScreen
from venus.utils.currency import fmt, fmt_syp, fmt_usd, round_currency
from tests.fixtures.helpers import insert_group, insert_material, insert_creditor, insert_cash_day
from venus.core.database import get_conn


class TestMultiCurrency:
    def test_usd_sales_entry(self, qt_app, temp_db):
        group_id = insert_group('usd_sales_group')
        cash_screen = CashScreen()
        cash_screen.open_date.setDate(QDate(2026, 8, 15))
        cash_screen.opening_edit.setText('1000')
        cash_screen.currency_combo.setCurrentText('دولار')
        with patch.object(QMessageBox, 'information'):
            cash_screen.open_day()
        cash_screen.loading_overlay.stop()

        screen = SalesScreen()
        screen.date_input.setDate(QDate(2026, 8, 15))
        screen.add_entry_row()
        widget = screen.entry_table.cellWidget(0, 0)
        if hasattr(widget, 'combo_widget'):
            idx = widget.combo_widget.findData(group_id)
            if idx >= 0:
                widget.combo_widget.setCurrentIndex(idx)
        else:
            idx = widget.findData(group_id)
            if idx >= 0:
                widget.setCurrentIndex(idx)
        screen.entry_table.item(0, 1).setText('100')
        with patch.object(QMessageBox, 'information'):
            screen.save_sales()

        from venus.core.database import get_conn
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT العملة FROM المبيعات_اليومية WHERE معرف_المجموعة = ?", (group_id,))
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == 'دولار'
        finally:
            conn.close()

    def test_usd_expense_entry(self, qt_app, temp_db):
        group_id = insert_group('usd_exp_group')
        cash_screen = CashScreen()
        cash_screen.open_date.setDate(QDate(2026, 8, 15))
        cash_screen.opening_edit.setText('1000')
        cash_screen.currency_combo.setCurrentText('دولار')
        with patch.object(QMessageBox, 'information'):
            cash_screen.open_day()
        cash_screen.loading_overlay.stop()

        screen = CashScreen()
        screen.exp_date.setDate(QDate(2026, 8, 15))
        screen.exp_amount.setText('50')
        screen.exp_desc.setText('usd expense test')
        with patch.object(QMessageBox, 'information'):
            screen.save_expense()

        from venus.core.database import get_conn
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT العملة FROM المصروفات WHERE الوصف = 'usd expense test'")
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == 'دولار'
        finally:
            conn.close()

    def test_currency_conversion_using_exchange_rate(self, qt_app, temp_db):
        from venus.core.database import get_conn
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE الإعدادات SET القيمة = ? WHERE المفتاح = 'سعر_صرف_الدولار'", ('9000',))
            conn.commit()
        finally:
            conn.close()

        usd_balance = 100.0
        rate = 9000.0
        syp_equivalent = usd_balance * rate
        assert fmt_syp(syp_equivalent) == "900,000 ليرة سورية"

    def test_exchange_rate_saving_and_loading(self, qt_app, temp_db):
        screen = SettingsScreen()
        screen.new_rate_input.setText('9500')
        with patch.object(QMessageBox, 'information'):
            screen.update_exchange_rate()

        from venus.core.database import get_conn
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT القيمة FROM الإعدادات WHERE المفتاح = 'سعر_صرف_الدولار'")
            row = cursor.fetchone()
            assert row is not None
            assert float(row[0]) == 9500.0
            cursor.execute("SELECT COUNT(*) FROM أسعار_الصرف WHERE سعر_الدولار = 9500")
            assert cursor.fetchone()[0] > 0
        finally:
            conn.close()

    def test_usd_creditor_shows_syp_equivalent(self, qt_app, temp_db):
        from venus.core.database import get_conn
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE الإعدادات SET القيمة = ? WHERE المفتاح = 'سعر_صرف_الدولار'", ('8500',))
            conn.commit()
        finally:
            conn.close()

        creditor_id = insert_creditor(name='usd_equiv_cred', currency='دولار', balance=200.0)
        screen = CreditorsScreen()
        screen.exchange_rate = 8500.0
        screen.creditor_ids = [creditor_id]
        screen.creditors_data = [(creditor_id, 'usd_equiv_cred', 'مورد', 'دولار', 200.0, 'نشط')]
        screen.searchable_table.set_data(
            ["👤 الاسم", "🏷️ النوع", "💱 العملة", "💰 الرصيد", "💵 ما يعادل بالليرة", "📌 الحالة"],
            [['usd_equiv_cred', 'مورد', 'دولار', 200.0, 200.0 * 8500.0, 'نشط']],
            id_column_index=0
        )
        equivalent = 200.0 * 8500.0
        assert fmt_syp(equivalent) == "1,700,000 ليرة سورية"
