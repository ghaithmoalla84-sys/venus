# -*- coding: utf-8 -*-
"""Tests for Widgets - Venus Coffee"""

import pytest
from unittest.mock import patch, MagicMock
from PyQt5.QtWidgets import QDialog, QMessageBox, QApplication, QStyle
from PyQt5.QtCore import Qt, QDate

from venus.ui.widgets.searchable_table import SearchableTable
from venus.ui.widgets.combo_quick_add import ComboWithQuickAdd
from venus.ui.widgets.entity_detail_dialog import EntityDetailDialog
from venus.ui.widgets.delegates import NumericDelegate
from PyQt5.QtGui import QDoubleValidator


class TestSearchableTable:
    def test_search_and_filter(self, qt_app, temp_db):
        table = SearchableTable()
        headers = ['Name', 'Value']
        rows = [['Apple', 10], ['Banana', 20], ['Cherry', 30]]
        table.set_data(headers, rows)
        table.search_box.setText('Banana')
        visible_ids = table.get_visible_row_ids()
        assert len(visible_ids) == 1

    def test_edit_button_works(self, qt_app, temp_db):
        table = SearchableTable()
        headers = ['Name', 'Value']
        rows = [['Apple', 10]]
        table.set_data(headers, rows, id_column_index=-1)
        table._on_edit(0)

    def test_delete_button_works(self, qt_app, temp_db):
        table = SearchableTable()
        headers = ['Name', 'Value']
        rows = [['Apple', 10]]
        table.set_data(headers, rows, id_column_index=-1)
        table._on_delete(0)

    def test_double_click_opens_details(self, qt_app, temp_db):
        table = SearchableTable()
        headers = ['Name', 'Value']
        rows = [['Apple', 10]]
        table.set_data(headers, rows, id_column_index=-1)
        table._on_cell_double_clicked(0, 0)


class TestComboWithQuickAdd:
    def test_load_list(self, qt_app, temp_db):
        items = [('A', 1), ('B', 2)]
        combo = ComboWithQuickAdd(load_func=lambda: items, add_dialog_func=None)
        assert combo.combo.count() == 2

    def test_add_new_item(self, qt_app, temp_db):
        items = [('A', 1)]
        def add_item():
            items.append(('B', 2))
            return 'B'
        combo = ComboWithQuickAdd(
            load_func=lambda: items,
            add_dialog_func=add_item
        )
        with patch.object(QMessageBox, 'information'):
            combo._on_add_clicked()
        assert combo.combo.count() == 2

    def test_select_item(self, qt_app, temp_db):
        combo = ComboWithQuickAdd(load_func=lambda: [('A', 1), ('B', 2)], add_dialog_func=None)
        combo.setCurrentValue(2)
        assert combo.current_value == 2


class TestEntityDetailDialog:
    def test_display_basic_data(self, qt_app, temp_db):
        dialog = EntityDetailDialog(
            title='Test',
            detail_data={'Name': 'Alice', 'Age': 30},
            parent=None
        )
        assert dialog.windowTitle() == 'Test'

    def test_display_related_records(self, qt_app, temp_db):
        dialog = EntityDetailDialog(
            title='Test',
            detail_data={'Name': 'Alice'},
            related_rows=[['2024-01-01', 'Buy', 100]],
            related_headers=['Date', 'Type', 'Amount'],
            parent=None
        )
        assert hasattr(dialog, 'related_table')
        assert dialog.related_table.rowCount() == 1


class TestNumericDelegate:
    def test_block_text_input(self, qt_app, temp_db):
        delegate = NumericDelegate()
        editor = delegate.createEditor(None, None, None)
        assert isinstance(editor.validator(), QDoubleValidator)

    def test_accept_only_numbers(self, qt_app, temp_db):
        delegate = NumericDelegate()
        editor = delegate.createEditor(None, None, None)
        editor.setText('abc')
        assert editor.validator().validate('abc', 0)[0] == 0
