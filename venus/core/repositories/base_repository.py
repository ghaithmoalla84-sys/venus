# -*- coding: utf-8 -*-
"""
المستودع الأساسي - Venus Coffee
يوفر دوال CRUD عامة (get_all, get_by_id, create, update, delete, search)
باستخدام get_conn() من venus.core.database.
يدعم فحص الارتباطات قبل الحذف لتجنب فقدان البيانات.
"""

from venus.core.database import get_conn


class RepositoryError(Exception):
    """خطأ أساسي للمستودعات"""
    pass


class BaseRepository:
    """
    مستودع عام يُعرّف عليه بجدول واحد.
    الفئات الفرعة تحدد: table_name، id_column، columns، search_columns،
    و _related_tables (الجداول المرتبطة التي تحمل مفاتيح أجنبية إلى هذا الجدول).
    """

    table_name = None
    id_column = "معرف"
    columns = []
    search_columns = []
    # قائمة من الكوابل (جدول, عمود المفتاح الأجنبي) للتحقق منها قبل الحذف
    _related_tables = []

    def __init__(self, conn=None):
        # إذا تم توفير اتصال، يتم استخدامه (مفيد لاختبارات التراكم ذات الاتصال الواحد)؛
        # خلاف ذلك يتم الحصول على اتصال جديد عبر get_conn().
        self._conn = conn

    # ─────────────────────── إدارة الاتصال ───────────────────────

    def _get_conn(self):
        if self._conn is not None:
            return self._conn
        return get_conn()

    def _owns_conn(self):
        return self._conn is None

    def _execute(self, query, params=()):
        conn = self._get_conn()
        cursor = conn.execute(query, params)
        return conn, cursor

    # ─────────────────────── CRUD الأساسي ───────────────────────

    def get_all(self):
        """إرجاع جميع السجلات كقوائم من القواميس."""
        query = "SELECT * FROM [{table}] ORDER BY [{id}] DESC".format(
            table=self.table_name, id=self.id_column)
        conn, cursor = self._execute(query)
        try:
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            if self._owns_conn():
                conn.close()

    def get_by_id(self, record_id):
        """إرجاع سجل واحد بواسطة المعرف أو None."""
        query = "SELECT * FROM [{table}] WHERE [{id}] = ?".format(
            table=self.table_name, id=self.id_column)
        conn, cursor = self._execute(query, (record_id,))
        try:
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            if self._owns_conn():
                conn.close()

    def create(self, **kwargs):
        """
        إنشاء سجل جديد. يُرجى تمرير الأعمدة كـ keyword arguments.
        يُرجع المعرف (lastrowid) للسجل المُنشأ.
        """
        cols = list(kwargs.keys())
        if not cols:
            raise RepositoryError("لا يمكن إنشاء سجل بدون بيانات")
        col_names = ", ".join("[{c}]".format(c=c) for c in cols)
        placeholders = ", ".join("?" for _ in cols)
        query = "INSERT INTO [{table}] ({cols}) VALUES ({placeholders})".format(
            table=self.table_name, cols=col_names, placeholders=placeholders)
        conn, cursor = self._execute(query, tuple(kwargs.values()))
        try:
            conn.commit()
            return cursor.lastrowid
        finally:
            if self._owns_conn():
                conn.close()

    def update(self, record_id, **kwargs):
        """تحديث سجل بواسطة المعرف. يُرجع عدد الصفوف المُحدَّثة."""
        if not kwargs:
            raise RepositoryError("لا توجد بيانات لتحديثها")
        set_clauses = ", ".join("[{c}] = ?".format(c=c) for c in kwargs)
        query = "UPDATE [{table}] SET {set_clauses} WHERE [{id}] = ?".format(
            table=self.table_name, set_clauses=set_clauses, id=self.id_column)
        params = list(kwargs.values()) + [record_id]
        conn, cursor = self._execute(query, tuple(params))
        try:
            conn.commit()
            return cursor.rowcount
        finally:
            if self._owns_conn():
                conn.close()

    def _discover_related_tables(self, conn):
        """
        اكتشاف الجداول التي تحمل مفاتيح أجنبية تشير إلى جدول هذا المستودع
        عبر PRAGMA foreign_key_list.
        يُرجع قائمة من الكوابل (جدول، عمود الـFK فيه) باستخدام البايتات
        الدقيقة لقاعدة البيانات — مما يتجاوز أي مشاكل تطابق الأحرف العربية.
        """
        results = []
        tables = [
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        for child in tables:
            quoted = '"%s"' % child.replace('"', '""')
            fks = conn.execute(
                "PRAGMA foreign_key_list(%s)" % quoted).fetchall()
            for fk in fks:
                # fk columns: (id, seq, table, from, to, on_update, on_delete, match)
                ref_table = fk[2]
                from_col = fk[3]
                if ref_table == self.table_name:
                    results.append((child, from_col))
        return results

    def delete(self, record_id):
        """
        حذف سجل بواسطة المعرف.
        يتحقق أولاً من عدم وجود سجلات مرتبطة (مثلاً في تحركات المخزون
        أو تفاصيل الشراء)؛ إذا وُجدت، يرفض الحذف ويرفع RepositoryError
        برسالة واضحة بدلاً من الحذف الفعلي.
        يُرجع عدد الصفوف المُحذوفة.
        """
        conn = self._get_conn()
        try:
            related = self._related_tables if self._related_tables else \
                self._discover_related_tables(conn)
            # فحص الارتباطات المرتبطة
            for table, fk_column in related:
                check_query = (
                    "SELECT COUNT(*) FROM [{table}] WHERE [{fk}] = ?".format(
                        table=table, fk=fk_column))
                cursor = conn.execute(check_query, (record_id,))
                count = cursor.fetchone()[0]
                if count > 0:
                    raise RepositoryError(
                        "لا يمكن حذف السجل (المعرّف: {rid}) من جدول {tbl} "
                        "لأنه مرتبط بـ {count} سجل/سجلات في جدول {rel}".format(
                            rid=record_id, tbl=self.table_name,
                            count=count, rel=table))

            query = "DELETE FROM [{table}] WHERE [{id}] = ?".format(
                table=self.table_name, id=self.id_column)
            cursor = conn.execute(query, (record_id,))
            conn.commit()
            return cursor.rowcount
        finally:
            if self._owns_conn():
                conn.close()

    def search(self, query):
        """بحث نصي في الأعمدة المحددة في search_columns."""
        if not self.search_columns or query is None:
            return []
        conditions = " OR ".join(
            "[{c}] LIKE ?".format(c=c) for c in self.search_columns)
        pattern = "%{q}%".format(q=query)
        query_sql = (
            "SELECT * FROM [{table}] WHERE ({conds}) "
            "ORDER BY [{id}] DESC".format(
                table=self.table_name, conds=conditions, id=self.id_column))
        params = tuple(pattern for _ in self.search_columns)
        conn, cursor = self._execute(query_sql, params)
        try:
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            if self._owns_conn():
                conn.close()

    def exists(self, record_id):
        """تحقق مما إذا كان السجل موجوداً."""
        query = ("SELECT 1 FROM [{table}] WHERE [{id}] = ? "
                 "LIMIT 1").format(table=self.table_name, id=self.id_column)
        conn, cursor = self._execute(query, (record_id,))
        try:
            return cursor.fetchone() is not None
        finally:
            if self._owns_conn():
                conn.close()

    def count(self):
        """عدد السجلات في الجدول."""
        query = "SELECT COUNT(*) FROM [{table}]".format(table=self.table_name)
        conn, cursor = self._execute(query)
        try:
            return cursor.fetchone()[0]
        finally:
            if self._owns_conn():
                conn.close()
