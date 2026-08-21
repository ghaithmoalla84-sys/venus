# -*- coding: utf-8 -*-
"""Tests for MainWindow closeEvent - Venus Coffee"""

import pytest
from unittest.mock import patch, MagicMock
from PyQt5.QtWidgets import QMessageBox
from datetime import datetime
import sqlite3

from venus.ui.main_window import MainWindow


class TestMainWindowCloseEvent:
    def test_close_with_open_day_user_cancels(self, qt_app, temp_db):
        today = datetime.now().strftime("%Y-%m-%d")
        conn = sqlite3.connect(temp_db)
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO أرصدة_الصندوق (التاريخ, مغلقة) VALUES (?, 0)",
            (today,)
        )
        conn.commit()
        conn.close()

        window = MainWindow()
        event = MagicMock()

        buttons = []

        def mock_add_button(text, role):
            btn = MagicMock()
            buttons.append(btn)
            return btn

        mock_msg = MagicMock()
        mock_msg.addButton.side_effect = mock_add_button
        mock_msg.clickedButton.side_effect = lambda: buttons[-1] if len(buttons) >= 2 else MagicMock()

        with patch('venus.ui.main_window.QMessageBox', return_value=mock_msg):
            window.closeEvent(event)

        event.ignore.assert_called_once()
        event.accept.assert_not_called()

    def test_close_with_no_open_day_accepts_directly(self, qt_app, temp_db):
        today = datetime.now().strftime("%Y-%m-%d")
        conn = sqlite3.connect(temp_db)
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO أرصدة_الصندوق (التاريخ, مغلقة) VALUES (?, 1)",
            (today,)
        )
        conn.commit()
        conn.close()

        window = MainWindow()
        event = MagicMock()

        with patch('venus.ui.main_window.QMessageBox') as mock_qmessagebox:
            window.closeEvent(event)

        event.accept.assert_called_once()
        event.ignore.assert_not_called()
        mock_qmessagebox.assert_not_called()
