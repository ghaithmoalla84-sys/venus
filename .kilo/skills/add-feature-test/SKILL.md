---
name: add-feature-test
description: إضافة اختبار (unit/integration) لميزة في Venus باتباع اصطلاحات conftest والمخطط المؤقت العربي ومساعِدات fixtures دون لمس قاعدة البيانات الحية.
---

مهارة لإضافة اختبار جديد لمشروع Venus ضمن `tests/`.

## المدخلات
- وصف ما يجب اختباره في $ARGUMENTS (مثل "اختبار حفظ فاتورة شراء" أو "اختبار تقرير الأرباح").

## أين تُضاف
- اختبار وحدة: `tests/unit/test_<feature>.py`
- اختبار تكاملي: `tests/integration/test_<feature>.py`
- شغّله من `D:\acc\tests`:
  ```
  cd D:\acc\tests; python -m pytest unit/test_<feature>.py -q
  ```

## اصطلاحات إلزامية (من `tests/conftest.py`)
1. **قاعدة بيانات مؤقتة آمنة**: المنطقة `patch_database_path` (autouse) توجّه `venus.core.database.DATABASE_PATH` إلى `temp_db` — مخطط كامل بأسماء عربية، **لا يلمس `venus.db` أبداً**. لا تعدّل هذا السلوك.
2. **مساعِدات جاهزة** من `tests.fixtures.helpers`:
   `insert_group(name)`, `insert_material(name, group_id, qty=...)`, `insert_creditor(...)`, `insert_cash_day(...)`. استوردها دائماً بدل إدراج SQL يدوي.
   ```python
   from tests.fixtures.helpers import insert_group, insert_material, insert_creditor
   ```
3. **الواجهات (Qt)**: مرّر fixture `qt_app` وأنشئ الشاشة مباشرة:
   ```python
   screen = InventoryScreen()
   ```
   وحِد الحوارات بنمط:
   ```python
   with patch.object(QDialog, 'exec_', return_value=QDialog.Accepted):
       with patch.object(QMessageBox, 'information'):
           screen._on_inventory_edit(material_id)
   ```
   (رسائل `QMessageBox` مُصمتة تلقائياً عبر fixture `_mock_qmessagebox`).
4. **الاتصال المباشر** عند الحاجة: fixture `db_conn` (يثبّت `row_factory=sqlite3.Row` ويفعّل المفاتيح الأجنبية).
5. **التنظيف**: fixture `clean_db` (autouse) يفرغ الجداول قبل كل اختبار — لا تفترض بيانات موجودة؛ أدرج ما تحتاج عبر المساعِدات.

## قواعد أمان
- ممنوع لمس `venus.db`/`venus_notes.db` الحيّة (المنطقة تضمن ذلك، لكن لا تلتفها).
- لا تكتب مسار DB مطلقاً؛ استخدم الـ fixtures.
- لا تستخدم `git` للرفع؛ قل للمستخدم عند الجاهزية (`/github-push`).

## بعد الإكمال
لخّص: ملف الاختبار، الحالات المغطاة، المساعِدات/الـ fixtures المستخدمة، ونتيجة تشغيل `pytest` (كم اختبار نجح). إن فشل أي اختبار، صلّح الكود أو الاختبار ضمن نطاقهما فقط.
