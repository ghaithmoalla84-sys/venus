---
description: رفع مشروع Venus إلى GitHub بأمان (فحص الملفات الحساسة قبل الرفع، بدون force push).
---

ارفع مشروع Venus إلى GitHub باتباع خطوات الأمان التالية بدقة. رسالة الـ commit إن وُجدت: $ARGUMENTS

1. نفّذ `git -C D:\acc status` وتأكد من حالة المستودع.
2. إن وُجدت تغييرات غير مرفوعة:
   - `git -C D:\acc add -A`
   - فحص أمان إلزامي (أوقف الرفع إن ظهر أي ملف حساس):
     ```
     git -C D:\acc diff --cached --name-only | Select-String '\.db$|project_backup|backups|zip|venus\.log|\.coverage|\.bak$'
     ```
   - `git -C D:\acc commit -m "<وصف عربي مختصر>"` (استخدم $ARGUMENTS إن وُجد، وإلا اكتب وصفاً مناسباً).
   - `git -C D:\acc push -u origin main` (أو `git push` إن كان الفرع مُتتبَعاً).
3. لا تستخدم `git push --force` أبداً. إن رُفض الدفع لعدم تطابق التاريخ، نفّذ `git -C D:\acc pull --rebase` ثم أعد المحاولة.
4. لا ترفع قواعد البيانات (`*.db`)، النسخ الاحتياطية (`backups/`, `*.zip`, `project_backup_*/`)، السجلات (`*.log`, `*.bak`, `.coverage`)، أو أي أسرار (`.env`, `*.key`, توكنات).
5. بعد النجاح، أبلغ المستخدم بعدد الملفات المرفوعة واسم الفرع ورابط `https://github.com/ghaithmoalla84-sys/venus`.
