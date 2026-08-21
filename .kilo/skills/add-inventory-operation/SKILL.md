---
name: add-inventory-operation
description: إضافة عملية مخزون/شراء/جرد جديدة في Venus باتباع أنماط PurchaseBillMixin وStockMixin والمستودعات مع احترام المعاملات وأقفال اليومية.
---

مهارة لإضافة عملية تتعامل مع المخزون أو المشتريات أو الجرد في تطبيق Venus (PySide).

## المدخلات
- وصف العملية في $ARGUMENTS (مثل "عملية جرد للمواد" أو "فاتورة شراء بمورد جديد" أو "تعديل يدوي للمخزون").

## أين تُضاف
- عمليات الشراء/الفواتير: `venus/ui/screens/inventory/purchase.py` (كلاس `PurchaseBillMixin`).
- عرض/تعديل المخزون: `venus/ui/screens/inventory/stock.py` (كلاس `StockMixin`).
- الجرد (stock-taking): `venus/ui/screens/inventory/audit.py` (يستخدم جدول `الجرد` وحركة `تحركات_المخزون` بنوع `'جرد'`).
- CRUD على الكيانات (مادة/مورد): عبر المستودعات في `venus/core/repositories/` (`MaterialsRepository`, `CreditorsRepository`).

## القواعد الإلزامية (مستخلصة من الكود القائم)
1. **أسماء الجداول/الأعمدة عربية** — انسخها من الاستعلامات الموجودة بدقة:
   `المجموعات`, `المواد_الفرعية`, `المخزون`, `تحركات_المخزون`, `فواتير_الشراء`, `تفاصيل_الشراء`, `الديون`, `تحركات_الديون`, `السحوبات`, `الخزنة`, `تحويلات_الصندوق`, `أرصدة_الصندوق`, `الجرد`.
2. **المعاملات متعددة الجداول** تُغلَّف بـ:
   ```
   conn = get_conn(); cur = conn.cursor()
   cur.execute("BEGIN TRANSACTION")
   ... عمليات ...
   conn.commit()
   ```
   وعند الخطأ `conn.rollback()`، وأغلق دائماً في `finally: conn.close()` (انظر `save_purchase_bill`).
3. **تحديث المخزون**: عند أي تغيّر كمية، حدّث `المخزون` (`INSERT OR REPLACE`) وسجّل في `تحركات_المخزون` (النوع `'شراء'`/`'تعديل_يدوي'`/`'جرد'`) مع `الرصيد_بعد`.
4. **إشعار الواجهات**: بعد أي تغيير استدعِ `from venus.core.events import app_events; app_events.emit_data_changed("<entity>")` للكيانات المتأثرة: `sales`, `purchases`, `materials`, `creditors`, `cash`, `expenses`, `withdrawals`.
5. **قفل اليومية**: قبل تسجيل عملية تؤثر النقدية، افحص `أرصدة_الصندوق.مغلقة` ليوم التاريخ؛ إن كان مغلقاً، امنع العملية وأبلغ المستخدم (نمط `save_purchase_bill`).
6. **التواريخ**: حوّل `QDate` إلى `yyyy-MM-dd` ونظّف الأرقام العربية: `s.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩","0123456789"))`.
7. **الكيانات**: استخدم `MaterialsRepository().create/update/delete` و`CreditorsRepository()` بدل SQL مباشر لإضافة مادة/مورد (نمط `_add_material_dialog`, `_add_supplier_dialog`).

## قواعد أمان
- **ممنوع** تعديل `venus.db`/`venus_notes.db` الحيّة؛ جرّب عبر الاختبارات (انظر مهارة `add-feature-test`).
- لا تكسر حسابات المخزون/الديون؛ أي حذف يجب أن يعيد الحساب الكامل كما في `_force_delete_purchase_invoice`.
- لا تستخدم `git` للرفع؛ قل للمستخدم عند الجاهزية (`/github-push`).

## بعد الإكمال
لخّص: العملية الجديدة، الجداول/المستودعات المستخدمة، معاملات DB، دوال `emit_data_changed` المُستدعاة، وملف/دالة الاختبار.
