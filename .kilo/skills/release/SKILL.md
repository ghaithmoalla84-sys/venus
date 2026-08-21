---
name: release
description: رفع إصدار جديد لمشروع Venus — تعديل __version__ ووسم (tag) ورفع للـ repo بأمان.
---

مهارة لإصدار نسخة جديدة من تطبيق Venus (مجلد `D:\acc`).

## المدخلات
- رقم الإصدار الجديد (مثل `1.0.1` أو `1.1.0`) يُمرَّر في $ARGUMENTS. إن لم يُذكر، اسأل المستخدم ولا تخمّن.

## الخطوات
1. اقرأ `venus/__init__.py` وأكّد قيمة `__version__` الحالية.
2. عدّل `__version__` إلى القيمة الجديدة فقط (لا تغيّر شيئاً آخر).
3. تحقق من نظافة شجرة العمل قبل الوسم:
   ```
   git -C D:\acc status --short
   ```
   إن وُجدت تغييرات غير مربوطة بالإصدار، نبّه المستخدم ولا تكمل حتى تحسم.
4. اعمل commit للإصدار:
   ```
   git -C D:\acc add venus/__init__.py
   git -C D:\acc commit -m "Bump version to <NEW>"
   ```
5. أنشئ وسماً (annotated tag):
   ```
   git -C D:\acc tag -a v<NEW> -m "Release v<NEW>"
   ```
6. ارفع الفرع والوسم:
   ```
   git -C D:\acc push -u origin main
   git -C D:\acc push origin v<NEW>
   ```
   لا تستخدم `git push --force`.
7. لا ترفع قواعد بيانات (`*.db`) أو نسخاً احتياطية؛ تحقق أنها مستثناة عبر `.gitignore`.

## ملاحظة
بعد نجاح الرفع، أبلغ المستخدم بالإصدار الجديد ورابط الوسم:
`https://github.com/ghaithmoalla84-sys/venus/releases/tag/v<NEW>`
