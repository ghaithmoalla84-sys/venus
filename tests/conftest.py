import pytest
import sqlite3
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch
from PyQt5.QtWidgets import QApplication, QMessageBox

from venus.core.database import get_conn, create_views

app = None


@pytest.fixture(autouse=True)
def _mock_qmessagebox():
    with patch.object(QMessageBox, 'warning', return_value=QMessageBox.Ok), \
         patch.object(QMessageBox, 'critical', return_value=QMessageBox.Ok), \
         patch.object(QMessageBox, 'information', return_value=QMessageBox.Ok), \
         patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
        yield


def pytest_configure(config):
    global app
    if app is None:
        app = QApplication.instance()
        if app is None:
            app = QApplication([])


@pytest.fixture(scope="session")
def qt_app():
    """Session-scoped QApplication instance"""
    global app
    if app is None:
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
    return app


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database with full schema for each test"""
    db_path = str(tmp_path / "test_venus.db")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    schema_statements = [
        """
        CREATE TABLE IF NOT EXISTS المجموعات (
            معرف INTEGER PRIMARY KEY AUTOINCREMENT,
            الاسم TEXT NOT NULL UNIQUE CHECK(الاسم != ''),
            الوصف TEXT,
            تاريخ_الإنشاء TEXT DEFAULT CURRENT_TIMESTAMP,
            الترتيب INTEGER DEFAULT 9999
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS المواد_الفرعية (
            معرف INTEGER PRIMARY KEY AUTOINCREMENT,
            الاسم TEXT NOT NULL,
            الوحدة TEXT CHECK(الوحدة IN ('كيلوغرام', 'قطعة', 'لتر')) NOT NULL,
            معرف_المجموعة INTEGER NOT NULL,
            سعر_الشراء_الأخير REAL DEFAULT 0 CHECK(سعر_الشراء_الأخير >= 0),
            الحد_الأدنى REAL DEFAULT 0 CHECK(الحد_الأدنى >= 0),
            ملاحظات TEXT,
            FOREIGN KEY (معرف_المجموعة) REFERENCES المجموعات(معرف) ON DELETE CASCADE
        )
        """,
        """
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
        """,
        """
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
        """,
        """
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
        """,
        """
        CREATE TABLE IF NOT EXISTS المبيعات_اليومية (
            معرف INTEGER PRIMARY KEY AUTOINCREMENT,
            التاريخ TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            معرف_المجموعة INTEGER NOT NULL,
            المبلغ_الإجمالي REAL NOT NULL CHECK(المبلغ_الإجمالي > 0),
            العملة TEXT CHECK(العملة IN ('ليرة_سورية', 'دولار')) DEFAULT 'ليرة_سورية',
            نوع_المعاملة TEXT DEFAULT 'نقدي',
            ملاحظات TEXT,
            FOREIGN KEY (معرف_المجموعة) REFERENCES المجموعات(معرف) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS المصروفات (
            معرف INTEGER PRIMARY KEY AUTOINCREMENT,
            التاريخ TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            المبلغ REAL NOT NULL CHECK(المبلغ >= 0),
            الوصف TEXT NOT NULL,
            نوع_المصروف TEXT CHECK(نوع_المصروف IN ('إيجار', 'رواتب', 'كهرباء', 'ماء', 'نقل', 'أخرى')) DEFAULT 'أخرى',
            العملة TEXT CHECK(العملة IN ('ليرة_سورية', 'دولار')) DEFAULT 'ليرة_سورية',
            ملاحظات TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS السحوبات (
            معرف INTEGER PRIMARY KEY AUTOINCREMENT,
            التاريخ TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            المبلغ REAL NOT NULL CHECK(المبلغ >= 0),
            الوصف TEXT NOT NULL,
            العملة TEXT CHECK(العملة IN ('ليرة_سورية', 'دولار')) DEFAULT 'ليرة_سورية',
            ملاحظات TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS سجل_العمليات_الأخيرة (
            معرف INTEGER PRIMARY KEY AUTOINCREMENT,
            نوع_العملية TEXT CHECK(نوع_العملية IN ('بيع', 'مصروف', 'سحب')) NOT NULL,
            معرف_السجل INTEGER NOT NULL,
            التاريخ_المتأثر TEXT NOT NULL,
            وقت_التسجيل TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            تم_التراجع INTEGER NOT NULL DEFAULT 0
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS تحركات_الديون (
            معرف INTEGER PRIMARY KEY AUTOINCREMENT,
            معرف_الدين INTEGER NOT NULL,
            التاريخ TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            المبلغ REAL NOT NULL CHECK(المبلغ >= 0),
            نوع_الحركة TEXT CHECK(نوع_الحركة IN ('إضافة', 'دفعة')) NOT NULL,
            ملاحظات TEXT,
            FOREIGN KEY (معرف_الدين) REFERENCES الديون(معرف) ON DELETE CASCADE
        )
        """,
        """
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
        """,
        """
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
        """,
        """
        CREATE TABLE IF NOT EXISTS المخزون (
            معرف_المادة_الفرعية INTEGER PRIMARY KEY,
            الكمية_المتوفرة REAL NOT NULL DEFAULT 0 CHECK(الكمية_المتوفرة >= 0),
            آخر_تحديث TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (معرف_المادة_الفرعية) REFERENCES المواد_الفرعية(معرف) ON DELETE CASCADE
        )
        """,
        """
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
        """,
        """
        CREATE TABLE IF NOT EXISTS الإعدادات (
            المفتاح TEXT PRIMARY KEY,
            القيمة TEXT NOT NULL,
            الوصف TEXT,
            تاريخ_التحديث TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS أسعار_الصرف (
            معرف INTEGER PRIMARY KEY AUTOINCREMENT,
            سعر_الدولار REAL NOT NULL CHECK(سعر_الدولار > 0),
            التاريخ TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            ملاحظات TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS الخزنة (
            معرف INTEGER PRIMARY KEY AUTOINCREMENT,
            التاريخ TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            البيان TEXT NOT NULL,
            إيداع REAL NOT NULL DEFAULT 0 CHECK(إيداع >= 0),
            سحب REAL NOT NULL DEFAULT 0 CHECK(سحب >= 0),
            الرصيد_بعد_الحركة REAL NOT NULL DEFAULT 0 CHECK(الرصيد_بعد_الحركة >= 0),
            ملاحظات TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS تحويلات_الصندوق (
            معرف INTEGER PRIMARY KEY AUTOINCREMENT,
            التاريخ TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            من_حساب TEXT NOT NULL CHECK(من_حساب IN ('الخزنة', 'الدرج', 'الخارجي')),
            إلى_حساب TEXT NOT NULL CHECK(إلى_حساب IN ('الخزنة', 'الدرج', 'الخارجي')),
            المبلغ REAL NOT NULL CHECK(المبلغ >= 0),
            ملاحظات TEXT,
            CHECK(من_حساب != إلى_حساب)
        )
        """,
    ]

    for stmt in schema_statements:
        cursor.execute(stmt)

    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_المجموعات_الاسم ON المجموعات(الاسم)",
        "CREATE INDEX IF NOT EXISTS idx_المواد_المجموعة ON المواد_الفرعية(معرف_المجموعة)",
        "CREATE INDEX IF NOT EXISTS idx_المواد_الاسم ON المواد_الفرعية(الاسم)",
        "CREATE INDEX IF NOT EXISTS idx_الفواتير_التاريخ ON فواتير_الشراء(التاريخ)",
        "CREATE INDEX IF NOT EXISTS idx_الفواتير_المورد_اسم ON فواتير_الشراء(اسم_المورد)",
        "CREATE INDEX IF NOT EXISTS idx_الفواتير_المورد_معرف ON فواتير_الشراء(معرف_المورد)",
        "CREATE INDEX IF NOT EXISTS idx_المبيعات_التاريخ ON المبيعات_اليومية(التاريخ)",
        "CREATE INDEX IF NOT EXISTS idx_المبيعات_المجموعة ON المبيعات_اليومية(معرف_المجموعة)",
        "CREATE INDEX IF NOT EXISTS idx_المبيعات_التاريخ_المجموعة ON المبيعات_اليومية(التاريخ, معرف_المجموعة)",
        "CREATE INDEX IF NOT EXISTS idx_المصروفات_التاريخ ON المصروفات(التاريخ)",
        "CREATE INDEX IF NOT EXISTS idx_السحوبات_التاريخ ON السحوبات(التاريخ)",
        "CREATE INDEX IF NOT EXISTS idx_الديون_الطرف ON الديون(اسم_الطرف)",
        "CREATE INDEX IF NOT EXISTS idx_تحركات_الديون_الدين ON تحركات_الديون(معرف_الدين)",
        "CREATE INDEX IF NOT EXISTS idx_الصندوق_التاريخ_ON أرصدة_الصندوق(التاريخ)",
        "CREATE INDEX IF NOT EXISTS idx_الجرد_التاريخ_ON الجرد(التاريخ)",
        "CREATE INDEX IF NOT EXISTS idx_المخزون_المادة_ON المخزون(معرف_المادة_الفرعية)",
        "CREATE INDEX IF NOT EXISTS idx_تحركات_المخزون_المادة_ON تحركات_المخزون(معرف_المادة_الفرعية)",
        "CREATE INDEX IF NOT EXISTS idx_أسعار_الصرف_التاريخ_ON أسعار_الصرف(التاريخ)",
        "CREATE INDEX IF NOT EXISTS idx_الخزنة_التاريخ_ON الخزنة(التاريخ)",
        "CREATE INDEX IF NOT EXISTS idx_تحويلات_الصندوق_التاريخ_ON تحويلات_الصندوق(التاريخ)",
        "CREATE INDEX IF NOT EXISTS idx_سجل_العمليات_النوع_تراجع_وقت ON سجل_العمليات_الأخيرة(نوع_العملية, تم_التراجع, وقت_التسجيل)",
    ]

    for idx in indexes:
        try:
            cursor.execute(idx)
        except Exception:
            pass

    conn.commit()
    conn.close()

    # Insert default settings
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()
    cursor.executemany(
        "INSERT OR IGNORE INTO الإعدادات (المفتاح, القيمة, الوصف) VALUES (?, ?, ?)",
        [
            ('اسم_المحل', 'فينوس كوفي', 'اسم المتجر'),
            ('سعر_صرف_الدولار', '8500', 'سعر صرف الدولار الأمريكي بالليرة السورية'),
            ('العملة_الافتراضية', 'ليرة_سورية', 'العملة الافتراضية للمعاملات'),
            ('إصدار_النظام', '1.0', 'إصدار النظام الحالي'),
            ('رصيد_النقدية_الافتتاحي', '0', 'رصيد النقدية الافتتاحي'),
            ('رصيد_الخزنة_الافتتاحي', '0', 'رصيد الخزنة الافتتاحي'),
            ('مبلغ_الفكة', '65000', 'مبلغ فكة الدرج الثابت'),
        ]
    )

    # Add initial vault balance
    cursor.execute("SELECT COUNT(*) FROM الخزنة")
    if cursor.fetchone()[0] == 0:
        from datetime import datetime
        cursor.execute("""
            INSERT INTO الخزنة (التاريخ, البيان, إيداع, الرصيد_بعد_الحركة, ملاحظات)
            VALUES (?, ?, ?, ?, ?)
        """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "رصيد افتتاحي", 2000000.0, 2000000.0, "رصيد افتتاحي للخزنة"))
    conn.commit()
    conn.close()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    create_views(conn=conn)
    conn.close()

    return db_path


@pytest.fixture
def qt_app():
    """Session-scoped QApplication instance"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(autouse=True)
def patch_database_path(temp_db, monkeypatch):
    """Patch the database path in all modules to use temp database"""
    from venus.core import database
    monkeypatch.setattr(database, "DATABASE_PATH", temp_db)
    database._TEST_MODE = True


@pytest.fixture(autouse=True)
def clean_db(patch_database_path):
    """Clean database before each test."""
    conn = get_conn()
    try:
        cursor = conn.cursor()
        tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        for table in tables:
            if table[0] != 'sqlite_sequence':
                cursor.execute(f"DELETE FROM {table[0]}")
                if table[0] == 'الإعدادات':
                    cursor.executemany(
                        "INSERT OR IGNORE INTO الإعدادات (المفتاح, القيمة, الوصف) VALUES (?, ?, ?)",
                        [
                            ('اسم_المحل', 'فينوس كوفي', 'اسم المتجر'),
                            ('سعر_صرف_الدولار', '8500', 'سعر صرف الدولار الأمريكي بالليرة السورية'),
                            ('العملة_الافتراضية', 'ليرة_سورية', 'العملة الافتراضية للمعاملات'),
                            ('إصدار_النظام', '1.0', 'إصدار النظام الحالي'),
                            ('رصيد_النقدية_الافتتاحي', '0', 'رصيد النقدية الافتتاحي'),
                            ('رصيد_الخزنة_الافتتاحي', '0', 'رصيد الخزنة الافتتاحي'),
                            ('مبلغ_الفكة', '65000', 'مبلغ فكة الدرج الثابت'),
                        ]
                    )
                elif table[0] == 'الخزنة':
                    from datetime import datetime
                    cursor.execute("""
                        INSERT INTO الخزنة (التاريخ, البيان, إيداع, الرصيد_بعد_الحركة, ملاحظات)
                        VALUES (?, ?, ?, ?, ?)
                    """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "رصيد افتتاحي", 2000000.0, 2000000.0, "رصيد افتتاحي للخزنة"))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def db_conn(temp_db):
    """Get a database connection for direct SQL operations"""
    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    yield conn
    conn.close()
