# -*- coding: utf-8 -*-
"""
مستودع المواد الفرعية - Venus Coffee
مخصص لجدول المواد_الفرعية (مخزون).

سلوك الحذف الآمن: يمنع الحذف إذا وجدت سجلات مرتبطة في أي جدول
له مفتاح أجنبي يشير إلى هذا الجدول. يتم اكتشاف الجداول المرتبطة
آلياً عبر PRAGMA foreign_key_list، ويشمل ذلك:
    تحركات_المخزون، تفاصيل_الشراء، المخزون، الجرد
"""

from venus.core.repositories.base_repository import BaseRepository


class MaterialsRepository(BaseRepository):
    """مستودع جدول المواد الفرعية."""

    table_name = "المواد_الفرعية"
    id_column = "معرف"
    columns = [
        "معرف", "الاسم", "الوحدة", "معرف_المجموعة",
        "سعر_الشراء_الأخير", "الحد_الأدنى", "ملاحظات",
    ]
    search_columns = ["الاسم"]
    # تُستخدم auto-discovery الآن (قائمة فارغة → يكتشف الجداول المرتبطة من المخطط)
    _related_tables = []  # يُكتشف آلياً عبر PRAGMA foreign_key_list

    def __init__(self, conn=None):
        super().__init__(conn)
