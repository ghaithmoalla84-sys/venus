# -*- coding: utf-8 -*-
"""
اختبار استعادة البيانات
"""
import pytest
import time
import sqlite3
import os
import shutil

from venus.core.database import get_conn, DATABASE_PATH, patch_db_path

from tests.fixtures.helpers import insert_group, insert_material, insert_sale, insert_expense


class TestDataRecoveryScenario:
    """استعادة قاعدة البيانات من نسخة احتياطية"""

    def test_full_backup_restore_workflow(self, temp_db):
        patch_db_path(temp_db)

        group_id = insert_group('recovery_group')
        material_id = insert_material('recovery_cake', group_id=group_id, qty=50.0)
        insert_sale(group_id, date='2026-07-01', amount=25000.0, currency='ليرة_سورية')
        insert_expense('2026-07-01 10:00:00', 5000.0, 'مصروف اختبار', etype='أخرى', currency='ليرة_سورية')

        backup_path = temp_db + '.backup'
        shutil.copy2(temp_db, backup_path)

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        for table in tables:
            if table[0] != 'sqlite_sequence':
                cursor.execute(f"DELETE FROM {table[0]}")
        conn.commit()
        conn.close()

        shutil.copy2(backup_path, temp_db)
        os.remove(backup_path)

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM المجموعات WHERE الاسم = 'recovery_group'")
        assert cursor.fetchone()[0] == 1

        cursor.execute("SELECT COUNT(*) FROM المواد_الفرعية WHERE الاسم = 'recovery_cake'")
        assert cursor.fetchone()[0] == 1

        cursor.execute("SELECT COUNT(*) FROM المبيعات_اليومية WHERE معرف_المجموعة = ?", (group_id,))
        assert cursor.fetchone()[0] == 1

        cursor.execute("SELECT COUNT(*) FROM المصروفات")
        assert cursor.fetchone()[0] == 1
        conn.close()

    def test_no_records_lost_after_restore(self, temp_db):
        patch_db_path(temp_db)

        group_id = insert_group('recovery_no_loss_group')
        material_id = insert_material('recovery_no_loss_cake', group_id=group_id, qty=75.0)
        insert_sale(group_id, date='2026-07-02', amount=30000.0, currency='ليرة_سورية')
        insert_expense('2026-07-02 10:00:00', 8000.0, 'مصروف', etype='أخرى', currency='ليرة_سورية')

        backup_path = temp_db + '.backup2'
        shutil.copy2(temp_db, backup_path)

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO المصروفات (التاريخ, المبلغ, الوصف, نوع_المصروف, العملة) VALUES (?, ?, ?, ?, ?)",
                       ('2026-07-03 10:00:00', 9999.0, 'corrupt', 'أخرى', 'ليرة_سورية'))
        conn.commit()
        conn.close()

        shutil.copy2(backup_path, temp_db)
        os.remove(backup_path)

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM المصروفات WHERE الوصف = 'مصروف'")
        expense_count = cursor.fetchone()[0]
        assert expense_count == 1

        cursor.execute("SELECT COUNT(*) FROM المصروفات WHERE الوصف = 'corrupt'")
        assert cursor.fetchone()[0] == 0
        conn.close()
