---
description: صيانة طبقة بيانات Venus (المخطط/الهجرات/integrity_checker/repositories) مع حماية قواعد البيانات الحية.
---

نفّذ مهمة صيانة قاعدة بيانات Venus المطلوبة في $ARGUMENTS بأمان.

1. اقرأ الملفات المعنية أولاً: `migrations/create_database.py`, `venus/core/integrity_checker.py`, وملف المستودع ذو الصلة في `venus/core/repositories/`.
2. **ممنوع** تعديل أو حذف `venus.db`/`venus_notes.db` الحيّة أو أي ملف في `backups/` أو `*.zip`.
3. جرّب أي تغيير مخطط على قاعدة مؤقتة (مثل `temp_test.db` في مجلد مؤقت تُحذف بعد الفحص).
4. عند تغيير المخطط: حدّث `migrations/create_database.py` بهجرة واضحة وقابلة للتطبيق التدريجي (ALTER TABLE بدل إعادة الإنشاء متى أمكن).
5. لا ترفع بـ git؛ قل للمستخدم عند الحاجة للحفظ.
6. لخّص التغيير وأثره المحتمل على البيانات الحية وما يجب مراعاته قبل الرفع.
المطلوب: $ARGUMENTS
