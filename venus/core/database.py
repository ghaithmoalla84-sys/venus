# Path: D:\acc\venus\core\database.py
# -*- coding: utf-8 -*-
"""
نظام إدارة قاعدة البيانات الموحد - Venus Coffee
يوفر اتصالاً موحداً بقاعدة البيانات مع تفعيل foreign_keys و row_factory
"""

import sqlite3
import os
from datetime import datetime, timedelta

DATABASE_PATH = "venus.db"
_TEST_MODE = False


def _normalize_date(date_str):
    """تحويل الأرقام العربية في التاريخ إلى أرقام إنجليزية"""
    if date_str is None:
        return None
    return str(date_str).translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))


def get_conn():
    """إنشاء اتصال بقاعدة البيانات مع الإعدادات المثالية"""
    if _TEST_MODE and os.path.abspath(DATABASE_PATH) == os.path.abspath("venus.db"):
        raise RuntimeError(
            "get_conn() called with production database path during tests. "
            "Use temp_db fixture or patch_db_path() to set a test database path."
        )
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.create_function("normalize_date", 1, _normalize_date)
    return conn


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


def yesterday_str():
    return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def patch_db_path(path):
    """تعديل مسار قاعدة البيانات في جميع وحدات التطبيق (للاستخدام في الاختبارات)"""
    global DATABASE_PATH
    DATABASE_PATH = path


def init_db():
    """تهيئة قاعدة البيانات إذا لم تكن موجودة"""
    from migrations.create_database import create_database, migrate_due_date
    create_database()
    migrate_due_date()


def create_views(conn=None):
    """إنشاء العروض (Views) المطلوبة إذا لم تكن موجودة"""
    if conn is None:
        conn = get_conn()
        close_after = True
    else:
        close_after = False
    try:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE VIEW IF NOT EXISTS view_المبيعات_المفصلة AS
            SELECT
                م.معرف,
                م.التاريخ,
                م.معرف_المجموعة,
                ج.الاسم AS اسم_المجموعة,
                م.المبلغ_الإجمالي,
                م.العملة,
                م.ملاحظات
            FROM المبيعات_اليومية م
            JOIN المجموعات ج ON م.معرف_المجموعة = ج.معرف
        """)

        cursor.execute("""
            CREATE VIEW IF NOT EXISTS view_المخزون_المفصل AS
            SELECT
                م.معرف_المادة_الفرعية,
                م.الاسم AS اسم_المادة,
                م.الوحدة,
                ج.الاسم AS اسم_المجموعة,
                خ.الكمية_المتوفرة,
                خ.آخر_تحديث
            FROM المخزون خ
            JOIN المواد_الفرعية م ON خ.معرف_المادة_الفرعية = م.معرف
            JOIN المجموعات ج ON م.معرف_المجموعة = ج.معرف
        """)

        cursor.execute("""
            CREATE VIEW IF NOT EXISTS view_ملخص_الديون AS
            SELECT
                نوع_الطرف,
                العملة,
                COUNT(*) AS عدد_الديون,
                SUM(الرصيد) AS إجمالي_الأرصدة,
                SUM(المبلغ_الإجمالي) AS إجمالي_الديون
            FROM الديون
            WHERE حالة_الدين != 'مسدد'
            GROUP BY نوع_الطرف, العملة
        """)

        conn.commit()
    finally:
        if close_after:
            conn.close()
