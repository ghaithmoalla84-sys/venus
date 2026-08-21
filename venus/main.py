# -*- coding: utf-8 -*-
"""
الملف الرئيسي لتطبيق محاسبة متجر "فينوس كوفي"
"""

import sys
import os
import faulthandler
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from venus.utils.logger import setup_logger
logger = setup_logger()

import traceback

crash_log = open("venus_crash.log", "a", encoding="utf-8")
faulthandler.enable(crash_log)

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.critical("خطأ غير ملتقط:", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_exception

def apply_global_style(app):
    """تطبيق الستايل العام للتطبيق"""
    app.setStyleSheet("""
        * {
            font-family: 'Segoe UI', 'Arial', 'Tahoma', sans-serif;
            font-size: 14px;
        }
        QMainWindow {
            background-color: #f5f6fa;
        }
        QStatusBar {
            background-color: #ecf0f1;
            color: #2c3e50;
            font-size: 13px;
            padding: 5px;
        }
        QStackedWidget {
            background-color: #f5f6fa;
        }
        QLabel {
            color: #2c3e50;
        }
    """)

def check_and_create_database():
    """فحص وجود قاعدة البيانات وإنشاؤها إذا لم تكن موجودة"""
    db_path = "venus.db"
    needs_init = False
    if not os.path.exists(db_path):
        needs_init = True
    else:
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='الديون'")
            if not cursor.fetchone():
                needs_init = True
            conn.close()
        except Exception:
            needs_init = True
    if needs_init:
        try:
            from migrations.create_database import create_database
            create_database()
        except ImportError as e:
            logger.error(str(e))
            QMessageBox.critical(None, "خطأ", "فشل تحميل وحدة إنشاء قاعدة البيانات")
            sys.exit(1)
        except Exception as e:
            logger.error(str(e))
            QMessageBox.critical(None, "خطأ", f"فشل إنشاء قاعدة البيانات:\n{str(e)}")
            sys.exit(1)
    if not os.path.exists(db_path):
        QMessageBox.critical(None, "خطأ", "لم يتم العثور على قاعدة البيانات بعد الإنشاء")
        sys.exit(1)
    return db_path

def main():
    app = QApplication(sys.argv)
    app.setLayoutDirection(Qt.RightToLeft)
    
    # فحص وإنشاء قاعدة البيانات
    check_and_create_database()

    # تشغيل ترحيل عمود تاريخ_استحقاق على قاعدة البيانات الحالية
    from migrations.create_database import migrate_due_date, migrate_audit_table, migrate_group_order, migrate_remove_vault_check
    migrate_due_date()
    migrate_audit_table()
    migrate_group_order()
    migrate_remove_vault_check()

    # إنشاء العروض (Views) المطلوبة
    from venus.core.database import create_views
    create_views()
    
    # تطبيق الستايل العام
    apply_global_style(app)
    
    # استيراد النافذة الرئيسية بعد إنشاء التطبيق
    from venus.ui.main_window import MainWindow
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
