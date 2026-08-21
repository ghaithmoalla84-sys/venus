# Path: D:\acc\migrations\create_database.py
# -*- coding: utf-8 -*-
"""
نظام محاسبة متجر "فينوس كوفي" - Venus Coffee
إنشاء قاعدة بيانات SQLite مع جميع الجداول المطلوبة
"""

import sqlite3
import os
from datetime import datetime, timedelta

DATABASE_PATH = "venus.db"


def create_database():
    """إنشاء قاعدة البيانات وجميع الجداول إذا لم تكن موجودة"""
    from venus.core.database import create_views
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()
    try:

        # ─────────────────────────────────────────────
        # 1. جدول المجموعات - لتقسيم المبيعات
        # ─────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS المجموعات (
                معرف INTEGER PRIMARY KEY AUTOINCREMENT,
                الاسم TEXT NOT NULL UNIQUE CHECK(الاسم != ''),
                الوصف TEXT,
                تاريخ_الإنشاء TEXT DEFAULT CURRENT_TIMESTAMP,
                الترتيب INTEGER DEFAULT 9999
            )
        """)

        # ─────────────────────────────────────────────
        # 2. جدول المواد الفرعية - للمخزون
        # ─────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS المواد_الفرعية (
                معرف INTEGER PRIMARY KEY AUTOINCREMENT,
                الاسم TEXT NOT NULL CHECK(الاسم != ''),
                الوحدة TEXT CHECK(الوحدة IN ('كيلوغرام', 'قطعة', 'لتر')) NOT NULL,
                معرف_المجموعة INTEGER NOT NULL,
                سعر_الشراء_الأخير REAL DEFAULT 0 CHECK(سعر_الشراء_الأخير >= 0),
                الحد_الأدنى REAL DEFAULT 0 CHECK(الحد_الأدنى >= 0),
                ملاحظات TEXT,
                FOREIGN KEY (معرف_المجموعة) REFERENCES المجموعات(معرف) ON DELETE CASCADE
            )
        """)

        # ─────────────────────────────────────────────
        # 3. جدول المبيعات اليومية - حسب المجموعات
        # ─────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS المبيعات_اليومية (
                معرف INTEGER PRIMARY KEY AUTOINCREMENT,
                التاريخ TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                معرف_المجموعة INTEGER NOT NULL,
                المبلغ_الإجمالي REAL NOT NULL CHECK(المبلغ_الإجمالي > 0),
                العملة TEXT CHECK(العملة IN ('ليرة_سورية', 'دولار')) DEFAULT 'ليرة_سورية',
                نوع_المعاملة TEXT CHECK(نوع_المعاملة IN ('نقدي')) DEFAULT 'نقدي',
                ملاحظات TEXT,
                FOREIGN KEY (معرف_المجموعة) REFERENCES المجموعات(معرف) ON DELETE CASCADE
            )
        """)

        # ─────────────────────────────────────────────
        # 4. جدول المصروفات - مصاريف الصندوق
        # ─────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS المصروفات (
                معرف INTEGER PRIMARY KEY AUTOINCREMENT,
                التاريخ TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                المبلغ REAL NOT NULL CHECK(المبلغ >= 0),
                الوصف TEXT NOT NULL CHECK(الوصف != ''),
                نوع_المصروف TEXT CHECK(نوع_المصروف IN ('إيجار', 'رواتب', 'كهرباء', 'ماء', 'نقل', 'أخرى')) DEFAULT 'أخرى',
                العملة TEXT CHECK(العملة IN ('ليرة_سورية', 'دولار')) DEFAULT 'ليرة_سورية',
                ملاحظات TEXT
            )
        """)

        # ─────────────────────────────────────────────
        # 5. جدول السحوبات - سحوبات من الصندوق
        # ─────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS السحوبات (
                معرف INTEGER PRIMARY KEY AUTOINCREMENT,
                التاريخ TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                المبلغ REAL NOT NULL CHECK(المبلغ >= 0),
                الوصف TEXT NOT NULL,
                العملة TEXT CHECK(العملة IN ('ليرة_سورية', 'دولار')) DEFAULT 'ليرة_سورية',
                ملاحظات TEXT
            )
        """)

        # ─────────────────────────────────────────────
        # 6. جدول سجل العمليات الأخيرة - لعمليات التراجع
        # ─────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS سجل_العمليات_الأخيرة (
                معرف INTEGER PRIMARY KEY AUTOINCREMENT,
                نوع_العملية TEXT CHECK(نوع_العملية IN ('بيع', 'مصروف', 'سحب')) NOT NULL,
                معرف_السجل INTEGER NOT NULL,
                التاريخ_المتأثر TEXT NOT NULL,
                وقت_التسجيل TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                تم_التراجع INTEGER NOT NULL DEFAULT 0
            )
        """)

        # ─────────────────────────────────────────────
        # 7. جدول الديون - دائنون (موردون وأصدقاء)
        # ─────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS الديون (
                معرف INTEGER PRIMARY KEY AUTOINCREMENT,
                اسم_الطرف TEXT NOT NULL,
                نوع_الطرف TEXT CHECK(نوع_الطرف IN ('مورد', 'صديق')) NOT NULL,
                العملة TEXT CHECK(العملة IN ('ليرة_سورية', 'دولار')) DEFAULT 'ليرة_سورية',
                المبلغ_الإجمالي REAL NOT NULL DEFAULT 0 CHECK(المبلغ_الإجمالي >= 0),
                المبلغ_المدفوع REAL NOT NULL DEFAULT 0 CHECK(المبلغ_المدفوع >= 0),
                الرصيد REAL NOT NULL DEFAULT 0 CHECK(الرصيد >= 0),
                حالة_الدين TEXT CHECK(حالة_الدين IN ('نشط', 'مسدد', 'متأخر')) DEFAULT 'نشط',
                ملاحظات TEXT,
                تاريخ_استحقاق TEXT,
                تاريخ_الإنشاء TEXT DEFAULT CURRENT_TIMESTAMP,
                تاريخ_التحديث TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ─────────────────────────────────────────────
        # 8. جدول تحركات الديون - سجل الدفعات والإضافات
        # ─────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS تحركات_الديون (
                معرف INTEGER PRIMARY KEY AUTOINCREMENT,
                معرف_الدين INTEGER NOT NULL,
                التاريخ TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                المبلغ REAL NOT NULL CHECK(المبلغ >= 0),
                نوع_الحركة TEXT CHECK(نوع_الحركة IN ('إضافة', 'دفعة')) NOT NULL,
                ملاحظات TEXT,
                FOREIGN KEY (معرف_الدين) REFERENCES الديون(معرف) ON DELETE CASCADE
            )
        """)

        # ─────────────────────────────────────────────
        # 9. جدول فواتير الشراء - شراء المواد الفرعية
        # ─────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS فواتير_الشراء (
                معرف INTEGER PRIMARY KEY AUTOINCREMENT,
                التاريخ TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                معرف_المورد INTEGER NOT NULL DEFAULT 0 REFERENCES الديون(معرف),
                اسم_المورد TEXT NOT NULL CHECK(اسم_المورد != ''),
                المبلغ_الإجمالي REAL NOT NULL CHECK(المبلغ_الإجمالي > 0),
                العملة TEXT CHECK(العملة IN ('ليرة_سورية', 'دولار')) DEFAULT 'ليرة_سورية',
                ملاحظات TEXT,
                تاريخ_الإنشاء TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ─────────────────────────────────────────────
        # 10. جدول تفاصيل فواتير الشراء
        # ─────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS تفاصيل_الشراء (
                معرف INTEGER PRIMARY KEY AUTOINCREMENT,
                معرف_الفاتورة INTEGER NOT NULL,
                معرف_المادة_الفرعية INTEGER NOT NULL,
                الكمية REAL NOT NULL CHECK(الكمية > 0),
                سعر_الوحدة REAL NOT NULL CHECK(سعر_الوحدة > 0),
                المبلغ_الإجمالي REAL NOT NULL CHECK(المبلغ_الإجمالي > 0),
                FOREIGN KEY (معرف_الفاتورة) REFERENCES فواتير_الشراء(معرف) ON DELETE CASCADE,
                FOREIGN KEY (معرف_المادة_الفرعية) REFERENCES المواد_الفرعية(معرف)
            )
        """)

        # ─────────────────────────────────────────────
        # 11. جدول أرصدة الصندوق - التسوية اليومية
        # ─────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS أرصدة_الصندوق (
                معرف INTEGER PRIMARY KEY AUTOINCREMENT,
                التاريخ TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                رصيد_بداية_اليوم REAL NOT NULL DEFAULT 0 CHECK(رصيد_بداية_اليوم >= 0),
                مبيعات_اليوم REAL NOT NULL DEFAULT 0 CHECK(مبيعات_اليوم >= 0),
                مصروفات_اليوم REAL NOT NULL DEFAULT 0 CHECK(مصروفات_اليوم >= 0),
                سحوبات_اليوم REAL NOT NULL DEFAULT 0 CHECK(سحوبات_اليوم >= 0),
                رصيد_نهاية_نظري REAL NOT NULL DEFAULT 0 CHECK(رصيد_نهاية_نظري >= 0),
                رصيد_نهاية_فعلي REAL NOT NULL DEFAULT 0 CHECK(رصيد_نهاية_فعلي >= 0),
                فرق_التسوية REAL NOT NULL DEFAULT 0,
                مبيعات_غير_مسجلة REAL NOT NULL DEFAULT 0 CHECK(مبيعات_غير_مسجلة >= 0),
            رصيد_الخزنة REAL NOT NULL DEFAULT 0 CHECK(رصيد_الخزنة >= 0),
            ملاحظات TEXT,
            العملة TEXT CHECK(العملة IN ('ليرة_سورية', 'دولار')) DEFAULT 'ليرة_سورية',
            مغلقة INTEGER NOT NULL DEFAULT 0
        )
        """)

        # إضافة عمود رصيد_الخزنة لقواعد البيانات القديمة
        try:
            cursor.execute("ALTER TABLE أرصدة_الصندوق ADD COLUMN رصيد_الخزنة REAL DEFAULT 0")
        except sqlite3.OperationalError:
            pass

        # ─────────────────────────────────────────────
        # 12. جدول الخزنة - سجل حركات الخزنة
        # ─────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS الخزنة (
                معرف INTEGER PRIMARY KEY AUTOINCREMENT,
                التاريخ TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                البيان TEXT NOT NULL,
                إيداع REAL NOT NULL DEFAULT 0 CHECK(إيداع >= 0),
                سحب REAL NOT NULL DEFAULT 0 CHECK(سحب >= 0),
                الرصيد_بعد_الحركة REAL NOT NULL DEFAULT 0 CHECK(الرصيد_بعد_الحركة >= 0),
                ملاحظات TEXT
            )
        """)

        # ─────────────────────────────────────────────
        # 13. جدول تحويلات_الصندوق - سجل التحويلات بين الخزنة والدرج
        # ─────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS تحويلات_الصندوق (
                معرف INTEGER PRIMARY KEY AUTOINCREMENT,
                التاريخ TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                من_حساب TEXT NOT NULL CHECK(من_حساب IN ('الخزنة', 'الدرج', 'الخارجي')),
                إلى_حساب TEXT NOT NULL CHECK(إلى_حساب IN ('الخزنة', 'الدرج', 'الخارجي')),
                المبلغ REAL NOT NULL CHECK(المبلغ >= 0),
                ملاحظات TEXT
            )
        """)

        # ─────────────────────────────────────────────
        # 14. جدول الجرد الدوري - للمخزون
        # ─────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS الجرد (
                معرف INTEGER PRIMARY KEY AUTOINCREMENT,
                التاريخ TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                معرف_المادة_الفرعية INTEGER NOT NULL,
                الكمية_النظري REAL NOT NULL CHECK(الكمية_النظري >= 0),
                الكمية_الفعلي REAL NOT NULL CHECK(الكمية_الفعلي >= 0),
                فرق_الجرد REAL NOT NULL,
                قيمة_الفرق REAL NOT NULL DEFAULT 0 CHECK(قيمة_الفرق >= 0),
                ملاحظات TEXT,
                FOREIGN KEY (معرف_المادة_الفرعية) REFERENCES المواد_الفرعية(معرف)
            )
        """)

        # ─────────────────────────────────────────────
        # 15. جدول المخزون الحالي - الكميات المتوفرة
        # ─────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS المخزون (
                معرف_المادة_الفرعية INTEGER PRIMARY KEY,
                الكمية_المتوفرة REAL NOT NULL DEFAULT 0 CHECK(الكمية_المتوفرة >= 0),
                آخر_تحديث TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (معرف_المادة_الفرعية) REFERENCES المواد_الفرعية(معرف) ON DELETE CASCADE
            )
        """)

        # ─────────────────────────────────────────────
        # 16. جدول تحركات المخزون - سجل العمليات
        # ─────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS تحركات_المخزون (
                معرف INTEGER PRIMARY KEY AUTOINCREMENT,
                معرف_المادة_الفرعية INTEGER NOT NULL,
                التاريخ TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                نوع_الحركة TEXT CHECK(نوع_الحركة IN ('شراء', 'تعديل_يدوي', 'جرد')) NOT NULL,
                الكمية REAL NOT NULL CHECK(الكمية >= 0),
                الرصيد_بعد REAL NOT NULL CHECK(الرصيد_بعد >= 0),
                معرف_الفاتورة INTEGER,
                معرف_الجرد INTEGER,
                ملاحظات TEXT,
                FOREIGN KEY (معرف_المادة_الفرعية) REFERENCES المواد_الفرعية(معرف),
                FOREIGN KEY (معرف_الفاتورة) REFERENCES فواتير_الشراء(معرف),
                FOREIGN KEY (معرف_الجرد) REFERENCES الجرد(معرف)
            )
        """)

        # ─────────────────────────────────────────────
        # 17. جدول الإعدادات - إعدادات عامة للمتجر
        # ─────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS الإعدادات (
                المفتاح TEXT PRIMARY KEY,
                القيمة TEXT NOT NULL,
                الوصف TEXT,
                تاريخ_التحديث TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ─────────────────────────────────────────────
        # 18. جدول سجل أسعار الصرف - للتتبع التاريخي
        # ─────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS أسعار_الصرف (
                معرف INTEGER PRIMARY KEY AUTOINCREMENT,
                سعر_الدولار REAL NOT NULL CHECK(سعر_الدولار > 0),
                التاريخ TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                ملاحظات TEXT
            )
        """)

        # ─────────────────────────────────────────────
        # إنشاء الفهارس لتسريع الاستعلامات
        # ─────────────────────────────────────────────

        # فهارس جدول المجموعات
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_المجموعات_الاسم ON المجموعات(الاسم)")

        # فهارس جدول المواد الفرعية
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_المواد_المجموعة ON المواد_الفرعية(معرف_المجموعة)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_المواد_الاسم ON المواد_الفرعية(الاسم)")

        # فهارس جدول فواتير الشراء
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_الفواتير_التاريخ ON فواتير_الشراء(التاريخ)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_الفواتير_المورد_اسم ON فواتير_الشراء(اسم_المورد)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_الفواتير_المورد_معرف ON فواتير_الشراء(معرف_المورد)")

        # فهارس جدول تفاصيل الشراء
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_تفاصيل_الفاتورة ON تفاصيل_الشراء(معرف_الفاتورة)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_تفاصيل_المادة ON تفاصيل_الشراء(معرف_المادة_الفرعية)")

        # فهارس جدول المبيعات اليومية
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_المبيعات_التاريخ ON المبيعات_اليومية(التاريخ)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_المبيعات_المجموعة ON المبيعات_اليومية(معرف_المجموعة)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_المبيعات_التاريخ_المجموعة ON المبيعات_اليومية(التاريخ, معرف_المجموعة)")

        # فهارس جدول المصروفات
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_المصروفات_التاريخ ON المصروفات(التاريخ)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_المصروفات_النوع ON المصروفات(نوع_المصروف)")

        # فهارس جدول السحوبات
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_السحوبات_التاريخ ON السحوبات(التاريخ)")

        # فهارس جدول الديون
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_الديون_الطرف ON الديون(اسم_الطرف)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_الديون_النوع ON الديون(نوع_الطرف)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_الديون_الحالة ON الديون(حالة_الدين)")

        # فهارس جدول تحركات الديون
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_تحركات_الديون_الدين ON تحركات_الديون(معرف_الدين)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_تحركات_الديون_التاريخ ON تحركات_الديون(التاريخ)")

        # فهارس جدول أرصدة الصندوق
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_الصندوق_التاريخ ON أرصدة_الصندوق(التاريخ)")

        # فهارس جدول الجرد
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_الجرد_التاريخ ON الجرد(التاريخ)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_الجرد_المادة ON الجرد(معرف_المادة_الفرعية)")

        # فهارس جدول المخزون
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_المخزون_المادة ON المخزون(معرف_المادة_الفرعية)")

        # فهارس جدول تحركات المخزون
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_تحركات_المخزون_المادة ON تحركات_المخزون(معرف_المادة_الفرعية)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_تحركات_المخزون_التاريخ ON تحركات_المخزون(التاريخ)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_تحركات_المخزون_النوع ON تحركات_المخزون(نوع_الحركة)")

        # فهارس جدول أسعار الصرف
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_أسعار_الصرف_التاريخ ON أسعار_الصرف(التاريخ)")

        # فهارس جدول الخزنة
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_الخزنة_التاريخ ON الخزنة(التاريخ)")

        # فهارس جدول تحويلات الصندوق
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_تحويلات_الصندوق_التاريخ ON تحويلات_الصندوق(التاريخ)")

        # فهرس جدول سجل العمليات الأخيرة
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_سجل_العمليات_النوع_تراجع_وقت ON سجل_العمليات_الأخيرة(نوع_العملية, تم_التراجع, وقت_التسجيل)")

        # فهارس إضافية لتحسين أداء الاستعلامات
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_المبيعات_ملاحظات ON المبيعات_اليومية(ملاحظات)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_المصروفات_التاريخ_العملة ON المصروفات(التاريخ, العملة)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_السحوبات_التاريخ_العملة ON السحوبات(التاريخ, العملة)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_الخزنة_البيان ON الخزنة(البيان)")

        # ─────────────────────────────────────────────
        # إدخال البيانات الأولية
        # ─────────────────────────────────────────────

        # إعدادات افتراضية
        default_settings = [
            ('اسم_المحل', 'فينوس كوفي', 'اسم المتجر'),
            ('سعر_صرف_الدولار', '8500', 'سعر صرف الدولار الأمريكي بالليرة السورية'),
            ('العملة_الافتراضية', 'ليرة_سورية', 'العملة الافتراضية للمعاملات'),
            ('إصدار_النظام', '1.0', 'إصدار النظام الحالي'),
            ('رصيد_النقدية_الافتتاحي', '0', 'رصيد النقدية الافتتاحي'),
            ('مبلغ_الفكة', '65000', 'مبلغ فكة الدرج الثابت'),
            ('رصيد_الخزنة_الافتتاحي', '0', 'رصيد الخزنة الافتتاحي'),
        ]
        cursor.executemany(
            "INSERT OR IGNORE INTO الإعدادات (المفتاح, القيمة, الوصف) VALUES (?, ?, ?)",
            default_settings
        )

        # إدخال سعر صرف أولي
        cursor.execute(
            "INSERT INTO أسعار_الصرف (سعر_الدولار, ملاحظات) VALUES (?, ?)",
            (8500, 'السعر الابتدائي')
        )

        # مجموعة المبيعات غير المسجلة
        cursor.execute(
            "INSERT OR IGNORE INTO المجموعات (الاسم, الوصف) VALUES (?, ?)",
            ("مبيعات غير مسجلة", "مجموعة خاصة للمبيعات غير المسجلة في التسوية")
        )

        # رصيد افتتاحي للخزنة
        cursor.execute("SELECT COUNT(*) FROM الخزنة")
        if cursor.fetchone()[0] == 0:
            cursor.execute("SELECT القيمة FROM الإعدادات WHERE المفتاح = 'رصيد_الخزنة_الافتتاحي'")
            vault_setting = cursor.fetchone()
            vault_opening = float(vault_setting[0]) if vault_setting and vault_setting[0] else 0.0

            cursor.execute("""
                INSERT INTO الخزنة (التاريخ, البيان, إيداع, الرصيد_بعد_الحركة, ملاحظات)
                VALUES (?, ?, ?, ?, ?)
            """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "رصيد افتتاحي", vault_opening, vault_opening, "رصيد افتتاحي للخزنة"))

        # ─────────────────────────────────────────────
        # إنشاء Views للاستعلامات الشائعة
        # ─────────────────────────────────────────────
        create_views(conn=conn)

        # حفظ التغييرات
        conn.commit()

    finally:
        conn.close()

    migrate_transfers_table()
    migrate_supplier_to_fk()
    migrate_debt_status_constraint()
    migrate_closed_flag()
    migrate_operations_log()
    migrate_due_date()
    migrate_min_stock()
    migrate_audit_table()
    migrate_group_order()
    migrate_remove_vault_check()

    print("[OK] تم إنشاء قاعدة البيانات بنجاح: " + DATABASE_PATH)
    print("المسار: " + os.path.abspath(DATABASE_PATH))


def migrate_transfers_table():
    from venus.core.database import get_conn
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS تحويلات_الصندوق_new (
                معرف INTEGER PRIMARY KEY AUTOINCREMENT,
                التاريخ TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                من_حساب TEXT NOT NULL CHECK(من_حساب IN ('الخزنة', 'الدرج', 'الخارجي')),
                إلى_حساب TEXT NOT NULL CHECK(إلى_حساب IN ('الخزنة', 'الدرج', 'الخارجي')),
                المبلغ REAL NOT NULL CHECK(المبلغ >= 0),
                ملاحظات TEXT
            )
        """)
        cursor.execute("INSERT INTO تحويلات_الصندوق_new SELECT * FROM تحويلات_الصندوق")
        cursor.execute("DROP TABLE تحويلات_الصندوق")
        cursor.execute("ALTER TABLE تحويلات_الصندوق_new RENAME TO تحويلات_الصندوق")
        conn.commit()
        print("[OK] تم تحديث جدول تحويلات_الصندوق")
    except Exception as e:
        conn.rollback()
        print(f"[SKIP] لم يتم تحديث جدول تحويلات_الصندوق: {e}")
    finally:
        conn.close()


def migrate_supplier_to_fk():
    """ربط فواتير الشراء بمعرف المورد بدلاً من اسمه النصي.

    تنفيذ الخطوات التالية داخل معاملة واحدة:
    1. إضافة عمود معرف_المورد INTEGER إذا لم يكن موجوداً
    2. ربط كل فاتورة بمعرف المورد من جدول الديون (أو إنشاء مورد جديد للبيانات اليتيمة)
    3. إعادة بناء الجدول مع FK constraint بعد التحقق من اكتمال البيانات
    """
    from venus.core.database import get_conn
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN TRANSACTION")

        # ── الخطوة 1: التحقق من وجود عمود معرف_المورد ──
        cursor.execute("PRAGMA table_info(فواتير_الشراء)")
        columns = [row[1] for row in cursor.fetchall()]

        if "معرف_المورد" not in columns:
            cursor.execute("ALTER TABLE فواتير_الشراء ADD COLUMN معرف_المورد INTEGER")
            print("[Migrate] تم إضافة عمود معرف_المورد إلى جدول فواتير_الشراء")

        # ── الخطوة 2: التحقق من وجود FK constraint ──
        cursor.execute("PRAGMA foreign_key_list(فواتير_الشراء)")
        fks = cursor.fetchall()
        has_fk = any(
            fk[2] == "الديون" and fk[3] == "معرف_المورد"
            for fk in fks
        )

        needs_rebuild = not has_fk

        if needs_rebuild:
            # ── ربط كل فاتورة بمعرف المورد ──
            cursor.execute("SELECT معرف, اسم_المورد FROM فواتير_الشراء")
            invoices = cursor.fetchall()

            for invoice_id, supplier_name in invoices:
                cursor.execute(
                    "SELECT معرف FROM الديون WHERE اسم_الطرف = ? AND نوع_الطرف = 'مورد'",
                    (supplier_name,)
                )
                row = cursor.fetchone()

                if row:
                    supplier_id = row[0]
                    print(f"[Migrate] ربط فاتورة #{invoice_id} بالمورد '{supplier_name}' (معرف: {supplier_id})")
                else:
                    cursor.execute("""
                        INSERT INTO الديون 
                        (اسم_الطرف, نوع_الطرف, العملة, المبلغ_الإجمالي, المبلغ_المدفوع, الرصيد, حالة_الدين)
                        VALUES (?, 'مورد', 'ليرة_سورية', 0, 0, 0, 'نشط')
                    """, (supplier_name,))
                    print(f"[Migrate] تم إنشاء مورد جديد: {supplier_name}")
                    supplier_id = cursor.lastrowid

                cursor.execute(
                    "UPDATE فواتير_الشراء SET معرف_المورد = ? WHERE معرف = ?",
                    (supplier_id, invoice_id)
                )

            # ── التحقق من أن جميع الصفوف لديها معرّف المورد ──
            cursor.execute(
                "SELECT COUNT(*) FROM فواتير_الشراء WHERE معرف_المورد IS NULL"
            )
            null_count = cursor.fetchone()[0]
            if null_count > 0:
                raise Exception(
                    f"[Migrate] {null_count} فاتورة لا تحتوي على معرف المورد"
                )

            # ── إعادة بناء الجدول مع FK constraint ──
            cursor.execute("""
                CREATE TABLE فواتير_الشراء_new (
                    معرف INTEGER PRIMARY KEY AUTOINCREMENT,
                    التاريخ TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    معرف_المورد INTEGER NOT NULL REFERENCES الديون(معرف),
                    اسم_المورد TEXT NOT NULL CHECK(اسم_المورد != ''),
                    المبلغ_الإجمالي REAL NOT NULL CHECK(المبلغ_الإجمالي > 0),
                    العملة TEXT CHECK(العملة IN ('ليرة_سورية', 'دولار')) DEFAULT 'ليرة_سورية',
                    ملاحظات TEXT,
                    تاريخ_الإنشاء TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                INSERT INTO فواتير_الشراء_new
                (معرف, التاريخ, معرف_المورد, اسم_المورد, المبلغ_الإجمالي, العملة, ملاحظات, تاريخ_الإنشاء)
                SELECT معرف, التاريخ, معرف_المورد, اسم_المورد, المبلغ_الإجمالي, العملة, ملاحظات, تاريخ_الإنشاء
                FROM فواتير_الشراء
            """)
            cursor.execute("DROP TABLE فواتير_الشراء")
            cursor.execute("ALTER TABLE فواتير_الشراء_new RENAME TO فواتير_الشراء")

            # إعادة إنشاء الفهارس
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_الفواتير_التاريخ ON فواتير_الشراء(التاريخ)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_الفواتير_المورد_اسم ON فواتير_الشراء(اسم_المورد)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_الفواتير_المورد_معرف ON فواتير_الشراء(معرف_المورد)"
            )

            print("[OK] تم بناء جدول فواتير_الشراء مع FK إلى الديون")

        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] فشل ترحيل معرّف المورد: {e}")
        raise
    finally:
        conn.close()


def migrate_debt_status_constraint():
    from venus.core.database import get_conn, create_views
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN TRANSACTION")

        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='الديون'")
        row = cursor.fetchone()
        if not row:
            conn.commit()
            return

        table_sql = row[0]
        has_old = "'مسد'" in table_sql and "'مسدد'" not in table_sql

        if has_old:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='view'")
            for (view_name,) in cursor.fetchall():
                cursor.execute(f"DROP VIEW IF EXISTS {view_name}")

            cursor.execute("""
                CREATE TABLE الديون_new (
                    معرف INTEGER PRIMARY KEY AUTOINCREMENT,
                    اسم_الطرف TEXT NOT NULL,
                    نوع_الطرف TEXT CHECK(نوع_الطرف IN ('مورد', 'صديق')) NOT NULL,
                    العملة TEXT CHECK(العملة IN ('ليرة_سورية', 'دولار')) DEFAULT 'ليرة_سورية',
                    المبلغ_الإجمالي REAL NOT NULL DEFAULT 0 CHECK(المبلغ_الإجمالي >= 0),
                    المبلغ_المدفوع REAL NOT NULL DEFAULT 0 CHECK(المبلغ_المدفوع >= 0),
                    الرصيد REAL NOT NULL DEFAULT 0 CHECK(الرصيد >= 0),
                    حالة_الدين TEXT CHECK(حالة_الدين IN ('نشط', 'مسدد', 'متأخر')) DEFAULT 'نشط',
                    ملاحظات TEXT,
                    تاريخ_الإنشاء TEXT DEFAULT CURRENT_TIMESTAMP,
                    تاريخ_التحديث TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                INSERT INTO الديون_new
                SELECT معرف, اسم_الطرف, نوع_الطرف, العملة, المبلغ_الإجمالي,
                       المبلغ_المدفوع, الرصيد,
                       CASE WHEN حالة_الدين = 'مسد' THEN 'مسدد' ELSE حالة_الدين END,
                       ملاحظات, تاريخ_الإنشاء, تاريخ_التحديث
                FROM الديون
            """)
            cursor.execute("DROP TABLE الديون")
            cursor.execute("ALTER TABLE الديون_new RENAME TO الديون")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_الديون_الطرف ON الديون(اسم_الطرف)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_الديون_النوع ON الديون(نوع_الطرف)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_الديون_الحالة ON الديون(حالة_الدين)")

            conn.commit()
            create_views(conn=conn)

            print("[OK] تم تحديث قيد حالة_الدين من 'مسد' إلى 'مسدد'")
        else:
            print("[SKIP] قيد حالة_الدين محدّث بالفعل")

        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] فشل ترحيل قيد حالة_الدين: {e}")
        raise
    finally:
        conn.close()


def migrate_closed_flag():
    from venus.core.database import get_conn
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(أرصدة_الصندوق)")
        columns = [row[1] for row in cursor.fetchall()]

        if "مغلقة" not in columns:
            cursor.execute("ALTER TABLE أرصدة_الصندوق ADD COLUMN مغلقة INTEGER DEFAULT 0")
            cursor.execute("UPDATE أرصدة_الصندوق SET مغلقة = 1 WHERE رصيد_نهاية_فعلي > 0 OR رصيد_نهاية_نظري > 0")
            print("[Migrate] تم إضافة عمود مغلقة إلى جدول أرصدة_الصندوق")
        else:
            print("[SKIP] عمود مغلقة موجود بالفعل")
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] فشل ترحيل عمود مغلقة: {e}")
        raise
    finally:
        conn.close()


def migrate_operations_log():
    from venus.core.database import get_conn
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS سجل_العمليات_الأخيرة (
                معرف INTEGER PRIMARY KEY AUTOINCREMENT,
                نوع_العملية TEXT CHECK(نوع_العملية IN ('بيع', 'مصروف', 'سحب')) NOT NULL,
                معرف_السجل INTEGER NOT NULL,
                التاريخ_المتأثر TEXT NOT NULL,
                وقت_التسجيل TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                تم_التراجع INTEGER NOT NULL DEFAULT 0
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_سجل_العمليات_النوع_تراجع_وقت ON سجل_العمليات_الأخيرة(نوع_العملية, تم_التراجع, وقت_التسجيل)")
        conn.commit()
        print("[OK] تم إنشاء جدول سجل_العمليات_الأخيرة")
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] فشل إنشاء جدول سجل_العمليات_الأخيرة: {e}")
    finally:
        conn.close()


def migrate_due_date():
    from venus.core.database import get_conn
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(الديون)")
        columns = [row[1] for row in cursor.fetchall()]

        if "تاريخ_استحقاق" not in columns:
            cursor.execute("ALTER TABLE الديون ADD COLUMN تاريخ_استحقاق TEXT")
            conn.commit()
            print("[Migrate] تم إضافة عمود تاريخ_استحقاق إلى جدول الديون")
        else:
            print("[SKIP] عمود تاريخ_استحقاق موجود بالفعل")
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] فشل ترحيل عمود تاريخ_استحقاق: {e}")
        raise
    finally:
        conn.close()


def migrate_min_stock():
    """إضافة عمود الحد الأدنى لكل مادة في جدول المواد الفرعية.

    يسمح بتحديد حد أدنى مخصص لكل مادة؛ عندما تكون الكمية المتوفرة أقل من
    هذا الحد (وكان الحد > 0) تظهر التنبيهات والتقارير ذات الصلة.
    """
    from venus.core.database import get_conn
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(المواد_الفرعية)")
        columns = [row[1] for row in cursor.fetchall()]

        if "الحد_الأدنى" not in columns:
            cursor.execute("ALTER TABLE المواد_الفرعية ADD COLUMN الحد_الأدنى REAL DEFAULT 0 CHECK(الحد_الأدنى >= 0)")
            print("[Migrate] تم إضافة عمود الحد_الأدنى إلى جدول المواد_الفرعية")
        else:
            print("[SKIP] عمود الحد_الأدنى موجود بالفعل")
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] فشل ترحيل عمود الحد_الأدنى: {e}")
        raise
    finally:
        conn.close()


def migrate_audit_table():
    """إصلاح أسماء الأعمدة في جدول الجرد للقواعد القديمة"""
    from venus.core.database import get_conn
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(الجرد)")
        columns = [row[1] for row in cursor.fetchall()]
        
        # إذا كان العمود القديم موجوداً بدون "ال" التعريف
        if "الكمية_فعلي" in columns and "الكمية_الفعلي" not in columns:
            # إعادة بناء الجدول بالأسماء الصحيحة
            cursor.execute("""
                CREATE TABLE الجرد_new (
                    معرف INTEGER PRIMARY KEY AUTOINCREMENT,
                    التاريخ TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    معرف_المادة_الفرعية INTEGER NOT NULL,
                    الكمية_النظري REAL NOT NULL CHECK(الكمية_النظري >= 0),
                    الكمية_الفعلي REAL NOT NULL CHECK(الكمية_الفعلي >= 0),
                    فرق_الجرد REAL NOT NULL,
                    قيمة_الفرق REAL NOT NULL DEFAULT 0 CHECK(قيمة_الفرق >= 0),
                    ملاحظات TEXT,
                    FOREIGN KEY (معرف_المادة_الفرعية) REFERENCES المواد_الفرعية(معرف)
                )
            """)
            cursor.execute("""
                INSERT INTO الجرد_new 
                SELECT معرف, التاريخ, معرف_المادة_الفرعية, الكمية_النظري, 
                       الكمية_فعلي, فرق_الجرد, قيمة_الفرق, ملاحظات
                FROM الجرد
            """)
            cursor.execute("DROP TABLE الجرد")
            cursor.execute("ALTER TABLE الجرد_new RENAME TO الجرد")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_الجرد_التاريخ ON الجرد(التاريخ)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_الجرد_المادة ON الجرد(معرف_المادة_الفرعية)")
            conn.commit()
            print("[Migrate] تم إصلاح أسماء أعمدة جدول الجرد")
        else:
            print("[SKIP] جدول الجرد لا يحتاج ترحيل")
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] فشل ترحيل جدول الجرد: {e}")
        raise
    finally:
        conn.close()


def migrate_group_order():
    """إضافة عمود الترتيب إلى جدول المجموعات وتهعيد ترقيم المجموعات الموجودة.

    يحدد الترتيب وفق التسلسل التالي للمجموعات الستة القابلة للبيع:
      1 = قهوة
      2 = موالح
      3 = بوظة
      4 = مشكل
      5 = براد
      6 = بودرة
      7 = سكاكر

    أي مجموعة أخرى غير مطلوبة (مثل "مبيعات غير مسجلة") يتم منحها رقم ترتيب
    يبدأ من 8 تصاعدياً حسب معرفها لضمان استقرار الترتيب.
    """
    from venus.core.database import get_conn
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(المجموعات)")
        columns = [row[1] for row in cursor.fetchall()]

        if "الترتيب" in columns:
            print("[SKIP] عمود الترتيب موجود بالفعل في جدول المجموعات")
            conn.close()
            return

        cursor.execute("ALTER TABLE المجموعات ADD COLUMN الترتيب INTEGER DEFAULT 9999")

        cursor.execute("SELECT الاسم FROM المجموعات ORDER BY معرف")
        existing_names = [row[0] for row in cursor.fetchall()]

        name_order_map = {
            "قهوة": 1,
            "موالح": 2,
            "بوظة": 3,
            "مشكل": 4,
            "براد": 5,
            "بودرة": 6,
            "سكاكر": 7,
        }

        matched_orders = []
        for name, order in name_order_map.items():
            if name in existing_names:
                cursor.execute(
                    "UPDATE المجموعات SET الترتيب = ? WHERE الاسم = ?",
                    (order, name)
                )
                matched_orders.append((name, order))

        cursor.execute("SELECT معرف, الاسم FROM المجموعات ORDER BY معرف")
        all_rows = cursor.fetchall()

        next_auto_order = 8
        for gid, gname in all_rows:
            if gname not in name_order_map:
                cursor.execute(
                    "UPDATE المجموعات SET الترتيب = ? WHERE معرف = ?",
                    (next_auto_order, gid)
                )
                matched_orders.append((gname, next_auto_order))
                next_auto_order += 1

        conn.commit()
        print("[Migrate] تم إضافة عمود الترتيب إلى جدول المجموعات")
        print("[OK] تم ترقيم {} مجموعة:".format(len(matched_orders)))
        for name, order in matched_orders:
            print("  - {} = {}".format(name, order))
    except Exception as e:
        conn.rollback()
        print("[ERROR] فشل ترحيل الترتيب: {}".format(e))
        raise
    finally:
        conn.close()


def migrate_remove_vault_check():
    """إزالة CHECK constraint من الرصيد_بعد_الحركة في جدول الخزنة
    للسماح برصيد سالب مؤقت"""
    from venus.core.database import get_conn, create_views
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN TRANSACTION")

        cursor.execute("SELECT name FROM sqlite_master WHERE type='view'")
        for (view_name,) in cursor.fetchall():
            cursor.execute(f"DROP VIEW IF EXISTS {view_name}")
        
        cursor.execute("""
            CREATE TABLE الخزنة_new (
                معرف INTEGER PRIMARY KEY AUTOINCREMENT,
                التاريخ TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                البيان TEXT NOT NULL,
                إيداع REAL NOT NULL DEFAULT 0 CHECK(إيداع >= 0),
                سحب REAL NOT NULL DEFAULT 0 CHECK(سحب >= 0),
                الرصيد_بعد_الحركة REAL NOT NULL DEFAULT 0,
                ملاحظات TEXT
            )
        """)
        cursor.execute("""
            INSERT INTO الخزنة_new
            SELECT * FROM الخزنة
        """)
        cursor.execute("DROP TABLE الخزنة")
        cursor.execute("""
            ALTER TABLE الخزنة_new RENAME TO الخزنة
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_الخزنة_التاريخ
            ON الخزنة(التاريخ)
        """)
        conn.commit()
        create_views(conn=conn)
        print("[OK] تم إزالة CHECK constraint من جدول الخزنة")
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] فشل ترحيل جدول الخزنة: {e}")
        raise
    finally:
        conn.close()


def verify_database():
    """التحقق من صحة قاعدة البيانات"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()
    try:
        # الحصول على قائمة الجداول
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = cursor.fetchall()

        print("\n[Tables] الجداول المُنشأة:")
        print("-" * 40)
        for table in tables:
            print("  - " + table[0])
            # الحصول على أعمدة الجدول
            cursor.execute(f'PRAGMA table_info("{table[0]}")')
            columns = cursor.fetchall()
            for col in columns:
                print("      " + col[1] + " (" + col[2] + ")")

        # عد الفهارس
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND sql IS NOT NULL")
        indexes = cursor.fetchall()
        print("\n[Indexes] الفهارس: " + str(len(indexes)) + " فهرس")

        # عد الـ Views
        cursor.execute("SELECT name FROM sqlite_master WHERE type='view'")
        views = cursor.fetchall()
        print("[Views] الـ Views: " + str(len(views)) + " عرض")
        for view in views:
            print("      - " + view[0])
    finally:
        conn.close()
    print("\n[OK] التحقق اكتمل بنجاح")


if __name__ == "__main__":
    create_database()
    migrate_supplier_to_fk()
    migrate_debt_status_constraint()
    migrate_operations_log()
    migrate_min_stock()
    migrate_group_order()
    verify_database()
