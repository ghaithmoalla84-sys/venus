# -*- coding: utf-8 -*-
"""
مستودع المجموعات - Venus Coffee
مخصص لجدول المجموعات (تقسيم المبيعات).

سلوك الحذف الآمن: يمنع الحذف إذا وجدت سجلات مرتبطة. تُستخدم
auto-discovery للجداول المرتبطة (مجموعة فرعية، مبيعات يومية)
عبر PRAGMA foreign_key_list.
"""

from venus.core.repositories.base_repository import BaseRepository


class GroupsRepository(BaseRepository):
    """مستودع جدول المجموعات."""

    table_name = "المجموعات"
    id_column = "معرف"
    columns = ["معرف", "الاسم", "الوصف", "تاريخ_الإنشاء"]
    search_columns = ["الاسم"]
    # تُستخدم auto-discovery الآن
    _related_tables = []  # يُكتشف آلياً عبر PRAGMA foreign_key_list

    def __init__(self, conn=None):
        super().__init__(conn)
