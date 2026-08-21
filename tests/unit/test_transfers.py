# -*- coding: utf-8 -*-
"""Tests for cash transfers between drawer (drawer) and vault (vault)"""

import pytest
from unittest.mock import patch
from PyQt5.QtWidgets import QMessageBox, QDialog
from PyQt5.QtCore import QDate

from venus.ui.screens.cash import CashScreen
from tests.fixtures.helpers import insert_vault_balance, insert_cash_day


class TestCashTransfers:
    def test_open_day_creates_vault_to_drawer_transfer(self, qt_app, temp_db):
        screen = CashScreen()
        initial_vault = screen.get_vault_balance()
        screen.open_date.setDate(QDate(2026, 1, 1))
        screen.opening_edit.setText("100000")
        screen.currency_combo.setCurrentText("ليرة_سورية")
        with patch.object(QMessageBox, 'information'):
            screen.open_day()
        screen.loading_overlay.stop()

        from venus.core.database import get_conn
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM تحويلات_الصندوق WHERE من_حساب = 'الخزنة' AND إلى_حساب = 'الدرج'")
            row = cursor.fetchone()
            assert row is not None
            assert row["المبلغ"] > 0
            assert "فتح يومية" in (row["ملاحظات"] or "")
        finally:
            conn.close()

    def test_close_day_creates_drawer_to_vault_transfer(self, qt_app, temp_db):
        screen = CashScreen()
        screen.open_date.setDate(QDate(2026, 1, 1))
        screen.opening_edit.setText("100000")
        screen.currency_combo.setCurrentText("ليرة_سورية")
        with patch.object(QMessageBox, 'information'):
            screen.open_day()
        screen.loading_overlay.stop()
        screen.actual_edit.setText("100000")
        with patch.object(QMessageBox, 'information'):
            screen.close_day()

        from venus.core.database import get_conn
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM تحويلات_الصندوق WHERE من_حساب = 'الدرج' AND إلى_حساب = 'الخزنة'")
            row = cursor.fetchone()
            assert row is not None
            assert row["المبلغ"] == 100000
            assert "إغلاق يومية" in (row["ملاحظات"] or "")
        finally:
            conn.close()

    def test_transfer_updates_vault_balance(self, qt_app, temp_db):
        screen = CashScreen()
        initial_vault = screen.get_vault_balance()
        float_amount = screen.get_float_amount()

        screen.open_date.setDate(QDate(2026, 1, 1))
        screen.opening_edit.setText("100000")
        screen.currency_combo.setCurrentText("ليرة_سورية")
        with patch.object(QMessageBox, 'information'):
            screen.open_day()
        screen.loading_overlay.stop()

        vault_after_open = screen.get_vault_balance()
        assert vault_after_open == initial_vault - float_amount

        screen.actual_edit.setText("100000")
        with patch.object(QMessageBox, 'information'):
            screen.close_day()

        vault_after_close = screen.get_vault_balance()
        assert vault_after_close == vault_after_open + 100000

    def test_open_day_insufficient_vault_balance_fails(self, qt_app, temp_db):
        screen = CashScreen()
        from venus.core.database import get_conn
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE الإعدادات SET القيمة = ? WHERE المفتاح = 'مبلغ_الفكة'", (str(999999999),))
            conn.commit()
        finally:
            conn.close()

        screen.open_date.setDate(QDate(2026, 1, 1))
        screen.opening_edit.setText("100000")
        with patch.object(QMessageBox, 'warning'):
            screen.open_day()

    def test_transfer_recorded_with_notes(self, qt_app, temp_db):
        screen = CashScreen()
        screen.open_date.setDate(QDate(2026, 1, 1))
        screen.opening_edit.setText("100000")
        screen.currency_combo.setCurrentText("ليرة_سورية")
        with patch.object(QMessageBox, 'information'):
            screen.open_day()
        screen.loading_overlay.stop()

        from venus.core.database import get_conn
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT ملاحظات FROM تحويلات_الصندوق WHERE من_حساب = 'الخزنة' AND إلى_حساب = 'الدرج'")
            row = cursor.fetchone()
            assert row is not None
            notes = row["ملاحظات"]
            assert notes is not None
            assert len(notes) > 0
        finally:
            conn.close()
