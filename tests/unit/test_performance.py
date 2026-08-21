# -*- coding: utf-8 -*-
"""
اختبارات الأداء والحواف
"""
import pytest
import time
import sqlite3
import os
import shutil
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor, as_completed

from venus.core.database import get_conn, DATABASE_PATH
from venus.core.repositories import GroupsRepository

from tests.fixtures.helpers import insert_group, insert_vault_balance


@pytest.mark.slow
class TestPerformance:
    """اختبارات الأداء"""

    def test_insert_10000_materials_performance(self, temp_db):
        group_id = insert_group('perf_bulk_group')
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()
        start = time.time()
        for i in range(10000):
            cursor.execute(
                "INSERT INTO المواد_الفرعية (الاسم, الوحدة, معرف_المجموعة, سعر_الشراء_الأخير) VALUES (?, ?, ?, ?)",
                (f'perf_mat_{i}', 'قطعة', group_id, 100.0)
            )
        conn.commit()
        conn.close()
        elapsed = time.time() - start
        assert elapsed < 30.0

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM المواد_الفرعية WHERE معرف_المجموعة = ?", (group_id,))
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 10000

    def test_generate_report_for_100000_operations(self, temp_db):
        group_id = insert_group('perf_report_group')
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        for i in range(100000):
            cursor.execute(
                "INSERT INTO المبيعات_اليومية (التاريخ, معرف_المجموعة, المبلغ_الإجمالي, العملة) VALUES (?, ?, ?, ?)",
                ('2026-05-01', group_id, 1000.0, 'ليرة_سورية')
            )
        conn.commit()
        conn.close()

        start = time.time()
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT معرف_المجموعة, COUNT(*) AS cnt, SUM(المبلغ_الإجمالي) AS total
            FROM المبيعات_اليومية
            WHERE date(التاريخ) = '2026-05-01'
            GROUP BY معرف_المجموعة
        """)
        rows = cursor.fetchall()
        conn.close()
        elapsed = time.time() - start

        assert len(rows) == 1
        assert rows[0][1] == 100000
        assert elapsed < 5.0

    def test_concurrent_ui_operations_no_deadlock(self, qt_app, temp_db):
        insert_vault_balance(5000000.0)

        results = []

        def query_vault():
            try:
                conn = sqlite3.connect(temp_db)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM الخزنة")
                count = cursor.fetchone()[0]
                conn.close()
                return count
            except Exception as e:
                return str(e)

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(query_vault) for _ in range(10)]
            for future in as_completed(futures):
                results.append(future.result())

        assert all(isinstance(r, int) for r in results)

    def test_database_reset_and_rebuild(self, temp_db):
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO المجموعات (الاسم) VALUES (?)", ('reset_test',))
        cursor.execute("INSERT INTO المواد_الفرعية (الاسم, الوحدة, معرف_المجموعة) VALUES (?, ?, ?)",
                       ('reset_mat', 'قطعة', cursor.lastrowid))
        conn.commit()
        conn.close()

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        for table in tables:
            if table[0] != 'sqlite_sequence':
                cursor.execute(f"DELETE FROM {table[0]}")
        conn.commit()
        conn.close()

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM المجموعات WHERE الاسم = 'reset_test'")
        assert cursor.fetchone()[0] == 0
        cursor.execute("SELECT COUNT(*) FROM المواد_الفرعية")
        assert cursor.fetchone()[0] == 0
        conn.close()

        gid = insert_group('rebuild_group')
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM المجموعات WHERE الاسم = 'rebuild_group'")
        assert cursor.fetchone()[0] == 1
        conn.close()
