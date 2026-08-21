# -*- coding: utf-8 -*-
"""
مستودع الديون/الدوائن - Venus Coffee
مخصص لجدول الديون (الدوائن مع الموردين والأصدقاء).

سلوك الحذف الآمن: يمنع الحذف إذا وجدت حركات ديون مرتبطة.
تُستخدم auto-discovery للجداول المرتبطة (تحركات_الديون)
عبر PRAGMA foreign_key_list.
"""

from venus.core.repositories.base_repository import BaseRepository


class CreditorsRepository(BaseRepository):
    """مستودع جدول الديون (الدوائن)."""

    table_name = "الديون"
    id_column = "معرف"
    columns = [
        "معرف", "اسم_الطرف", "نوع_الطرف", "العملة", "المبلغ_الإجمالي",
        "المبلغ_المدفوع", "الرصيد", "حالة_الدين", "ملاحظات",
        "تاريخ_استحقاق", "تاريخ_الإنشاء", "تاريخ_التحديث",
    ]
    search_columns = ["اسم_الطرف"]
    # تُستخدم auto-discovery الآن
    _related_tables = []  # يُكتشف آلياً عبر PRAGMA foreign_key_list

    def __init__(self, conn=None):
        super().__init__(conn)
