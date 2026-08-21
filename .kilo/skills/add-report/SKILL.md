---
name: add-report
description: إضافة تقرير/تبويب جديد إلى شاشة التقارير في Venus باتباع النمط الثابت لـ ReportsScreen مع دعم التصدير والاختبار.
---

مهارة لإضافة تقرير محاسبي جديد في تطبيق Venus (PySide) إلى شاشة `venus/ui/screens/reports.py`.

## المدخلات
- وصف التقرير المطلوب في $ARGUMENTS (مثل "تقرير المصروفات الشهرية" أو "تقرير أفضل المواد مبيعاً").

## الخطوات
1. اقرأ `venus/ui/screens/reports.py` كمرجع إلزامي لفهم النمط (خاصة `build_sales_tab` + `load_sales_report`).
2. أضف تبويباً جديداً داخل `ReportsScreen`:
   - أنشئ `self.<name>_tab = QWidget()` و سجّله: `tabs.addTab(self.<name>_tab, "🏷 العنوان")`.
   - أنشئ `build_<name>_tab()` يبني الواجهة (فلاتر التاريخ بـ `QDateEdit`، زر عرض، أزرار تصدير Excel/PDF، جدول `SearchableTable`).
   - أنشئ `load_<name>_report()` يحمّل البيانات.
   - استدعِ `self.build_<name>_tab()` داخل `init_ui()`، وأضف فرعاً في `_on_app_data_changed` لتحديثه عند `app_events.data_changed`.
3. الوصول للبيانات:
   - استخدم `from venus.core.database import get_conn` وافتح الاتصال داخل `try/except/finally` مع `conn.close()` في `finally` (انظر `load_sales_report`).
   - **أعمدة قاعدة البيانات بالعربية** (مثل `المبيعات_اليومية`, `المجموعات`, `الديون`) — انسخ الأسماء من الاستعلامات القائمة بدقة، ولا تخترع أسماء.
   - التواريخ: حوّل `QDate` إلى `yyyy-MM-dd` ثم نظّف الأرقام العربية: `s.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩","0123456789"))`، واستخدم `date(normalize_date(التاريخ))` في الشرط.
4. العرض:
   - الجداول عبر `SearchableTable(show_actions=False)` و `.set_data(headers, rows)`.
   - الأزرار تستدعي `self._run_with_loading(btn, self.load_<name>_report)`.
   - التصدير أعد استخدام `self.export_table_to_excel(table, "اسم.xlsx", "ورقة", headers)` و `export_table_to_pdf(...)`.
   - التنسيق المالي: `from venus.utils.currency import fmt, fmt_syp, fmt_usd`.
   - السجلات: `from venus.utils.logger import setup_logger; logger = setup_logger()`، والتقاط الأخطاء بـ `QMessageBox.critical`.
5. لا تلمس `venus.db`/`venus_notes.db` الحيّة؛ جرّب عبر بيانات موجودة فعلياً.
6. أضف اختباراً في `tests/unit/test_reports.py` يحاكي بناء الشاشة وتحميل التقرير (انظر `test_dashboard.py` لنمط الاختبار واستخدام fixtures).

## قواعد أمان
- لا تعدّل قواعد البيانات الحية.
- حافظ على اتجاه الواجهة `Qt.RightToLeft` ودوال التنسيق الموجودة.
- لا تستخدم `git` للرفع؛ قل للمستخدم عند الجاهزية (يمكنه `/github-push`).

## بعد الإكمال
لخّص: التبويب الجديد، الاستعلام الأساسي المستخدم، دوال التصدير المفعّلة، وملف/دالة الاختبار.
