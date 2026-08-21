# -*- coding: utf-8 -*-
"""
مستودع المبيعات اليومية - Venus Coffee
مخصص لجدول المبيعات_اليومية.
يتضمن دالة get_by_date لجلب مبيعات تاريخ معين،
ودالة is_day_closed للتحقق من إغلاق اليومية بالرجوع لجدول أرصدة_الصندوق.
"""

from datetime import datetime, timedelta

from venus.core.repositories.base_repository import BaseRepository


class SalesRepository(BaseRepository):
    """مستودع جدول المبيعات اليومية."""

    table_name = "المبيعات_اليومية"
    id_column = "معرف"
    columns = [
        "معرف",
        "التاريخ",
        "معرف_المجموعة",
        "المبلغ_الإجمالي",
        "العملة",
        "نوع_المعاملة",
        "ملاحظات",
    ]
    search_columns = ["ملاحظات"]
    _related_tables = []

    def __init__(self, conn=None):
        super().__init__(conn)

    def get_by_date(self, date):
        """إرجاع جميع مبيعات تاريخ محدد مع اسم المجموعة مرتبة حسب المعرف."""
        date = str(date).translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
        next_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    م.معرف,
                    م.التاريخ,
                    م.معرف_المجموعة,
                    م.المبلغ_الإجمالي,
                    م.العملة,
                    م.نوع_المعاملة,
                    م.ملاحظات,
                    ج.الاسم AS اسم_المجموعة
                FROM المبيعات_اليومية م
                JOIN المجموعات ج ON م.معرف_المجموعة = ج.معرف
                WHERE م.التاريخ >= ? AND م.التاريخ < ?
                ORDER BY م.معرف
            """, (date, next_date))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            if self._owns_conn():
                conn.close()

    def is_day_closed(self, date):
        """التحقق مما إذا كانت يومية التاريخ مُغلقة.

        اليومية مُغلقة إذا كان عمود مغلقة = 1 في جدول أرصدة_الصندوق لنفس التاريخ.
        """
        if not date:
            return False
        date = str(date).translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT مغلقة FROM أرصدة_الصندوق WHERE التاريخ = ?",
                (date,),
            )
            row = cursor.fetchone()
            if row:
                return bool(row["مغلقة"])
            return False
        finally:
            if self._owns_conn():
                conn.close()
