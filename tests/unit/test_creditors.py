# -*- coding: utf-8 -*-
"""Tests for CreditorsScreen - Venus Coffee"""

import pytest
from unittest.mock import patch, MagicMock
from PyQt5.QtWidgets import QDialog, QMessageBox, QInputDialog
from PyQt5.QtCore import Qt, QDate
from datetime import datetime, date

from venus.ui.screens.creditors import CreditorsScreen
from venus.core.database import get_conn
from tests.fixtures.helpers import insert_group, insert_material, insert_creditor, insert_invoice, insert_invoice_detail, insert_debt_movement


class TestCreditorsScreen:
    def test_initial_ui(self, qt_app, temp_db):
        screen = CreditorsScreen()
        assert hasattr(screen, 'rate_label')
        assert hasattr(screen, 'total_label')
        assert hasattr(screen, 'add_btn')
        assert hasattr(screen, 'payment_btn')
        assert hasattr(screen, 'history_btn')
        assert hasattr(screen, 'searchable_table')

    def test_adding_creditor(self, qt_app, temp_db):
        screen = CreditorsScreen()
        with patch('venus.ui.screens.creditors.AddCreditorDialog') as MockDialog:
            mock_dialog = MagicMock()
            mock_dialog.exec_ = MagicMock(return_value=QDialog.Accepted)
            mock_dialog.get_data = MagicMock(return_value={
                'name': 'test_cred', 'type': 'مورد', 'currency': 'ليرة_سورية', 'amount': 0.0
            })
            MockDialog.return_value = mock_dialog
            with patch.object(QMessageBox, 'information'):
                screen.add_creditor()

    def test_opening_payment_dialog(self, qt_app, temp_db):
        creditor_id = insert_creditor(name='test_pay', balance=5000.0)
        screen = CreditorsScreen()
        screen.creditor_ids = [creditor_id]
        screen.creditors_data = [(creditor_id, 'test_pay', 'مورد', 'ليرة_سورية', 5000.0, 'نشط', None)]
        screen.searchable_table.set_data(
            ["👤 الاسم", "🏷️ النوع", "💱 العملة", "💰 الرصيد", "💵 ما يعادل بالليرة", "📌 الحالة", "📅 تاريخ الاستحقاق"],
            [['test_pay', 'مورد', 'ليرة_سورية', 5000.0, 5000.0, 'نشط', '—']],
            id_column_index=0
        )
        with patch.object(screen.searchable_table.table, 'currentRow', return_value=0):
            with patch('venus.ui.screens.creditors.PaymentDialog') as MockDialog:
                mock_dialog = MagicMock()
                mock_dialog.exec_ = MagicMock(return_value=QDialog.Accepted)
                mock_dialog.get_data = MagicMock(return_value={
                    'date': '2026-08-15 10:00:00', 'amount': 1000.0, 'notes': 'partial', 'source': 'من درج المحل'
                })
                MockDialog.return_value = mock_dialog
                with patch.object(QMessageBox, 'information'):
                    screen.record_payment()

    def test_full_payment(self, qt_app, temp_db):
        creditor_id = insert_creditor(name='full_pay', balance=5000.0)
        screen = CreditorsScreen()
        screen.creditor_ids = [creditor_id]
        screen.creditors_data = [(creditor_id, 'full_pay', 'مورد', 'ليرة_سورية', 5000.0, 'نشط', None)]
        screen.searchable_table.set_data(
            ["👤 الاسم", "🏷️ النوع", "💱 العملة", "💰 الرصيد", "💵 ما يعادل بالليرة", "📌 الحالة", "📅 تاريخ الاستحقاق"],
            [['full_pay', 'مورد', 'ليرة_سورية', 5000.0, 5000.0, 'نشط', '—']],
            id_column_index=0
        )
        with patch.object(screen.searchable_table.table, 'currentRow', return_value=0):
            with patch('venus.ui.screens.creditors.PaymentDialog') as MockDialog:
                mock_dialog = MagicMock()
                mock_dialog.exec_ = MagicMock(return_value=QDialog.Accepted)
                mock_dialog.get_data = MagicMock(return_value={
                    'date': '2026-08-15 10:00:00', 'amount': 5000.0, 'notes': 'full', 'source': 'من درج المحل'
                })
                MockDialog.return_value = mock_dialog
                with patch.object(QMessageBox, 'information'):
                    screen.record_payment()

    def test_partial_payment(self, qt_app, temp_db):
        creditor_id = insert_creditor(name='partial_pay', balance=5000.0)
        screen = CreditorsScreen()
        screen.creditor_ids = [creditor_id]
        screen.creditors_data = [(creditor_id, 'partial_pay', 'مورد', 'ليرة_سورية', 5000.0, 'نشط', None)]
        screen.searchable_table.set_data(
            ["👤 الاسم", "🏷️ النوع", "💱 العملة", "💰 الرصيد", "💵 ما يعادل بالليرة", "📌 الحالة", "📅 تاريخ الاستحقاق"],
            [['partial_pay', 'مورد', 'ليرة_سورية', 5000.0, 5000.0, 'نشط', '—']],
            id_column_index=0
        )
        with patch.object(screen.searchable_table.table, 'currentRow', return_value=0):
            with patch('venus.ui.screens.creditors.PaymentDialog') as MockDialog:
                mock_dialog = MagicMock()
                mock_dialog.exec_ = MagicMock(return_value=QDialog.Accepted)
                mock_dialog.get_data = MagicMock(return_value={
                    'date': '2026-08-15 10:00:00', 'amount': 2000.0, 'notes': 'partial', 'source': 'من درج المحل'
                })
                MockDialog.return_value = mock_dialog
                with patch.object(QMessageBox, 'information'):
                    screen.record_payment()

    def test_blocking_over_payment(self, qt_app, temp_db):
        creditor_id = insert_creditor(name='over_pay', balance=5000.0)
        screen = CreditorsScreen()
        screen.creditor_ids = [creditor_id]
        screen.creditors_data = [(creditor_id, 'over_pay', 'مورد', 'ليرة_سورية', 5000.0, 'نشط', None)]
        screen.searchable_table.set_data(
            ["👤 الاسم", "🏷️ النوع", "💱 العملة", "💰 الرصيد", "💵 ما يعادل بالليرة", "📌 الحالة", "📅 تاريخ الاستحقاق"],
            [['over_pay', 'مورد', 'ليرة_سورية', 5000.0, 5000.0, 'نشط', '—']],
            id_column_index=0
        )
        with patch.object(screen.searchable_table.table, 'currentRow', return_value=0):
            with patch('venus.ui.screens.creditors.PaymentDialog') as MockDialog:
                mock_dialog = MagicMock()
                mock_dialog.exec_ = MagicMock(return_value=QDialog.Accepted)
                mock_dialog.get_data = MagicMock(return_value='exceeded')
                MockDialog.return_value = mock_dialog
                with patch.object(QMessageBox, 'warning'):
                    screen.record_payment()

    def test_deleting_creditor_without_invoices_succeeds(self, qt_app, temp_db):
        creditor_id = insert_creditor(name='del_no_inv', balance=0.0)
        screen = CreditorsScreen()
        screen.creditor_ids = [creditor_id]
        screen.creditors_data = [(creditor_id, 'del_no_inv', 'مورد', 'ليرة_سورية', 0.0, 'نشط', None)]
        screen.searchable_table.set_data(
            ["👤 الاسم", "🏷️ النوع", "💱 العملة", "💰 الرصيد", "💵 ما يعادل بالليرة", "📌 الحالة", "📅 تاريخ الاستحقاق"],
            [['del_no_inv', 'مورد', 'ليرة_سورية', 0.0, 0.0, 'نشط', '—']],
            id_column_index=0
        )
        with patch.object(screen.searchable_table.table, 'currentRow', return_value=0):
            with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
                with patch.object(QMessageBox, 'information'):
                    screen._on_delete_creditor(creditor_id)

    def test_deleting_creditor_with_invoices_fails(self, qt_app, temp_db):
        creditor_id = insert_creditor(name='del_with_inv', balance=0.0)
        conn = get_conn()
        try:
            conn.execute(
                "INSERT INTO فواتير_الشراء (التاريخ, معرف_المورد, اسم_المورد, المبلغ_الإجمالي, العملة) VALUES (?, ?, ?, ?, ?)",
                ("2025-01-01", creditor_id, 'del_with_inv', 5000.0, 'ليرة_سورية')
            )
            conn.commit()
        finally:
            conn.close()
        screen = CreditorsScreen()
        screen.creditor_ids = [creditor_id]
        screen.creditors_data = [(creditor_id, 'del_with_inv', 'مورد', 'ليرة_سورية', 0.0, 'نشط', None)]
        screen.searchable_table.set_data(
            ["👤 الاسم", "🏷️ النوع", "💱 العملة", "💰 الرصيد", "💵 ما يعادل بالليرة", "📌 الحالة", "📅 تاريخ الاستحقاق"],
            [['del_with_inv', 'مورد', 'ليرة_سورية', 0.0, 0.0, 'نشط', '—']],
            id_column_index=0
        )
        with patch.object(screen.searchable_table.table, 'currentRow', return_value=0):
            with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
                with patch.object(QMessageBox, 'warning'):
                    screen._on_delete_creditor(creditor_id)

    def test_deleting_creditor_with_movements_fails(self, qt_app, temp_db):
        creditor_id = insert_creditor(name='del_with_mov', balance=5000.0)
        insert_debt_movement(creditor_id, 5000.0, mtype='إضافة', notes='initial')
        screen = CreditorsScreen()
        screen.creditor_ids = [creditor_id]
        screen.creditors_data = [(creditor_id, 'del_with_mov', 'مورد', 'ليرة_سورية', 5000.0, 'نشط', None)]
        screen.searchable_table.set_data(
            ["👤 الاسم", "🏷️ النوع", "💱 العملة", "💰 الرصيد", "💵 ما يعادل بالليرة", "📌 الحالة", "📅 تاريخ الاستحقاق"],
            [['del_with_mov', 'مورد', 'ليرة_سورية', 5000.0, 5000.0, 'نشط', '—']],
            id_column_index=0
        )
        with patch.object(screen.searchable_table.table, 'currentRow', return_value=0):
            with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
                with patch.object(QMessageBox, 'warning'):
                    screen._on_delete_creditor(creditor_id)

    def test_editing_creditor_currency(self, qt_app, temp_db):
        creditor_id = insert_creditor(name='edit_currency_cred', currency='ليرة_سورية')
        screen = CreditorsScreen()
        screen.creditor_ids = [creditor_id]
        screen.creditors_data = [(creditor_id, 'edit_currency_cred', 'مورد', 'ليرة_سورية', 0.0, 'نشط', None)]
        screen.searchable_table.set_data(
            ["👤 الاسم", "🏷️ النوع", "💱 العملة", "💰 الرصيد", "💵 ما يعادل بالليرة", "📌 الحالة", "📅 تاريخ الاستحقاق"],
            [['edit_currency_cred', 'مورد', 'ليرة_سورية', 0.0, 0.0, 'نشط', '—']],
            id_column_index=0
        )
        with patch.object(screen.searchable_table.table, 'currentRow', return_value=0):
            with patch('venus.ui.screens.creditors.EditCreditorDialog') as MockDialog:
                mock_dialog = MagicMock()
                mock_dialog.exec_ = MagicMock(return_value=QDialog.Accepted)
                mock_dialog.get_data = MagicMock(return_value={
                    'name': 'edit_currency_cred', 'type': 'مورد', 'currency': 'دولار', 'due_date': None
                })
                MockDialog.return_value = mock_dialog
                with patch.object(QMessageBox, 'information'):
                    screen._on_edit_creditor(creditor_id)

        from venus.core.database import get_conn
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT العملة FROM الديون WHERE معرف = ?", (creditor_id,))
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == 'دولار'
        finally:
            conn.close()

    def test_due_date_save_and_read(self, qt_app, temp_db):
        creditor_id = insert_creditor(name='due_date_test', تاريخ_استحقاق='2026-12-31')
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT تاريخ_استحقاق FROM الديون WHERE معرف = ?", (creditor_id,))
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == '2026-12-31'
        finally:
            conn.close()

        screen = CreditorsScreen()
        screen.creditor_ids = [creditor_id]
        screen.creditors_data = [(creditor_id, 'due_date_test', 'مورد', 'ليرة_سورية', 0.0, 'نشط', '2026-12-31')]
        screen.searchable_table.set_data(
            ["👤 الاسم", "🏷️ النوع", "💱 العملة", "💰 الرصيد", "💵 ما يعادل بالليرة", "📌 الحالة", "📅 تاريخ الاستحقاق"],
            [['due_date_test', 'مورد', 'ليرة_سورية', 0.0, 0.0, 'نشط', '2026-12-31']],
            id_column_index=0
        )
        with patch.object(screen.searchable_table.table, 'currentRow', return_value=0):
            with patch('venus.ui.screens.creditors.EditCreditorDialog') as MockDialog:
                mock_dialog = MagicMock()
                mock_dialog.exec_ = MagicMock(return_value=QDialog.Accepted)
                mock_dialog.get_data = MagicMock(return_value={
                    'name': 'due_date_test', 'type': 'مورد', 'currency': 'ليرة_سورية', 'due_date': None
                })
                MockDialog.return_value = mock_dialog
                with patch.object(QMessageBox, 'information'):
                    screen._on_edit_creditor(creditor_id)

        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT تاريخ_استحقاق FROM الديون WHERE معرف = ?", (creditor_id,))
            row = cursor.fetchone()
            assert row is not None
            assert row[0] is None
        finally:
            conn.close()

    def test_overdue_due_date_past(self, qt_app, temp_db):
        creditor_id = insert_creditor(name='overdue_due', balance=5000.0, تاريخ_استحقاق='2020-01-01')
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as cnt FROM الديون
                WHERE الرصيد > 0.01 AND حالة_الدين != 'مسدد'
                AND (تاريخ_استحقاق IS NOT NULL AND تاريخ_استحقاق < date('now'))
            """)
            row = cursor.fetchone()
            assert row is not None
            assert row[0] >= 1
        finally:
            conn.close()

    def test_overdue_no_due_date_old_debt(self, qt_app, temp_db):
        old_date = (datetime.now() - __import__('datetime').timedelta(days=40)).strftime('%Y-%m-%d')
        creditor_id = insert_creditor(name='old_debt', balance=3000.0, تاريخ_الإنشاء=old_date)
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as cnt FROM الديون
                WHERE الرصيد > 0.01 AND حالة_الدين != 'مسدد'
                AND (تاريخ_استحقاق IS NULL AND date('now', '-30 days') > date(تاريخ_الإنشاء))
            """)
            row = cursor.fetchone()
            assert row is not None
            assert row[0] >= 1
        finally:
            conn.close()

    def test_supplier_price_comparison(self, qt_app, temp_db):
        group_id = insert_group(name='price_test_group')
        material_id = insert_material(name='price_test_mat', group_id=group_id, price=100.0)
        creditor_id = insert_creditor(name='price_supplier')

        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO فواتير_الشراء (التاريخ, معرف_المورد, اسم_المورد, المبلغ_الإجمالي, العملة) VALUES (?, ?, ?, ?, ?)",
                ('2026-01-01', creditor_id, 'price_supplier', 200.0, 'ليرة_سورية')
            )
            invoice1_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO تفاصيل_الشراء (معرف_الفاتورة, معرف_المادة_الفرعية, الكمية, سعر_الوحدة, المبلغ_الإجمالي) VALUES (?, ?, ?, ?, ?)",
                (invoice1_id, material_id, 1.0, 100.0, 100.0)
            )

            cursor.execute(
                "INSERT INTO فواتير_الشراء (التاريخ, معرف_المورد, اسم_المورد, المبلغ_الإجمالي, العملة) VALUES (?, ?, ?, ?, ?)",
                ('2026-06-01', creditor_id, 'price_supplier', 300.0, 'ليرة_سورية')
            )
            invoice2_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO تفاصيل_الشراء (معرف_الفاتورة, معرف_المادة_الفرعية, الكمية, سعر_الوحدة, المبلغ_الإجمالي) VALUES (?, ?, ?, ?, ?)",
                (invoice2_id, material_id, 1.0, 150.0, 150.0)
            )
            conn.commit()
        finally:
            conn.close()

        screen = CreditorsScreen()
        screen.creditor_ids = [creditor_id]
        screen.creditors_data = [(creditor_id, 'price_supplier', 'مورد', 'ليرة_سورية', 500.0, 'نشط', None)]
        screen.searchable_table.set_data(
            ["👤 الاسم", "🏷️ النوع", "💱 العملة", "💰 الرصيد", "💵 ما يعادل بالليرة", "📌 الحالة", "📅 تاريخ الاستحقاق"],
            [['price_supplier', 'مورد', 'ليرة_سورية', 500.0, 500.0, 'نشط', '—']],
            id_column_index=0
        )

        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT d.معرف_المادة_الفرعية, m.الاسم, d.سعر_الوحدة
                FROM تفاصيل_الشراء d
                JOIN فواتير_الشراء f ON d.معرف_الفاتورة = f.معرف
                JOIN المواد_الفرعية m ON d.معرف_المادة_الفرعية = m.معرف
                WHERE f.معرف_المورد = ?
                ORDER BY d.معرف DESC
            """, (creditor_id,))
            price_rows = cursor.fetchall()

            material_prices = {}
            for row in price_rows:
                mid, mname, price = row
                if mid not in material_prices:
                    material_prices[mid] = []
                material_prices[mid].append((mname, float(price or 0)))

            found = False
            for mid, prices in material_prices.items():
                unique_prices = []
                seen = set()
                for mname, price in prices:
                    if price not in seen:
                        seen.add(price)
                        unique_prices.append((mname, price))
                    if len(unique_prices) >= 2:
                        break
                if len(unique_prices) >= 2:
                    mname, last_price = unique_prices[0]
                    _, prev_price = unique_prices[1]
                    assert last_price == 150.0
                    assert prev_price == 100.0
                    change_pct = ((last_price - prev_price) / prev_price) * 100
                    assert change_pct == 50.0
                    found = True
                    break
            assert found
        finally:
            conn.close()
