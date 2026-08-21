# -*- coding: utf-8 -*-
"""
اختبارات أساسية لقاعدة البيانات
"""

import pytest
import sqlite3

from venus.core.database import get_conn, create_views


class TestDatabaseCore:
    """اختبارات وظائف قاعدة البيانات الأساسية"""

    def test_get_conn_returns_row_factory(self, temp_db):
        """get_conn يعيد اتصال مع row_factory"""
        conn = get_conn()
        assert conn.row_factory == sqlite3.Row
        conn.close()

    def test_foreign_keys_enabled(self, temp_db):
        """Foreign keys مفعّلة"""
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys")
        result = cursor.fetchone()
        assert result[0] == 1
        conn.close()

    def test_today_str_format(self):
        """today_str يعيد تاريخ بتنسيق YYYY-MM-DD"""
        from venus.core.database import today_str
        result = today_str()
        assert len(result) == 10
        assert result[4] == '-'
        assert result[7] == '-'

    def test_now_str_format(self):
        """now_str يعيد تاريخ ووقت بتنسيق YYYY-MM-DD HH:MM:SS"""
        from venus.core.database import now_str
        result = now_str()
        assert len(result) == 19
        assert result[4] == '-'
        assert result[10] == ' '
        assert result[13] == ':'
        assert result[16] == ':'

    def test_all_tables_exist(self, temp_db):
        """جميع الجداول موجودة في قاعدة البيانات المؤقتة"""
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        expected = [
            'المجموعات', 'المواد_الفرعية', 'فواتير_الشراء', 'تفاصيل_الشراء',
            'المبيعات_اليومية', 'المصروفات', 'السحوبات', 'الديون',
            'تحركات_الديون', 'أرصدة_الصندوق', 'الجرد', 'المخزون',
            'تحركات_المخزون', 'الإعدادات', 'أسعار_الصرف',
            'الخزنة', 'تحويلات_الصندوق'
        ]
        for table in expected:
            assert table in tables

    def test_create_views_creates_views(self, temp_db):
        """create_views ينشئ العروض المطلوبة"""
        create_views()
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='view'")
        views = [row[0] for row in cursor.fetchall()]
        conn.close()

        expected_views = [
            'view_المبيعات_المفصلة',
            'view_المخزون_المفصل',
            'view_ملخص_الديون'
        ]
        for view in expected_views:
            assert view in views
