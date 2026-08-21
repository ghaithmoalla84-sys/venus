# -*- coding: utf-8 -*-
"""اختبارات المخزون الذكي — الحد الأدنى، تقرير ما يجب شراؤه، معدل الاستهلاك.

الاختبارات الأربعة المطلوبة:
  1. مادة كميتها أقل من حدها الأدنى المحدد → تظهر في تقرير "ما يجب شراؤه".
  2. مادة بلا حد أدنى محدد (0) → لا تظهر في التقرير حتى لو كانت كميتها منخفضة.
  3. مادة لها جردان متتاليان + مشتريات بينهما → معدل استهلاك شهري صحيح رقمياً.
  4. مادة بجرد واحد فقط (أو بلا جرد) → تُعرض "لا تتوفر بيانات كافية" دون خطأ.
"""

import pytest
from venus.core.database import get_conn
from venus.core.repositories import MaterialsRepository
from venus.utils.inventory_analytics import get_buy_list, calculate_monthly_consumption


def _make_material(min_qty, qty=0.0, name="اختبار"):
    """إنشاء مجموعة ومادة بالحد الأدنى والكمية المحددين."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO المجموعات (الاسم) VALUES (?)", (name + "_group",))
        group_id = cur.lastrowid

        repo = MaterialsRepository(conn=conn)
        mid = repo.create(
            الاسم=name,
            الوحدة="قطعة",
            معرف_المجموعة=group_id,
            سعر_الشراء_الأخير=100.0,
            الحد_الأدنى=min_qty,
        )
        if qty > 0:
            cur.execute(
                "INSERT OR REPLACE INTO المخزون (معرف_المادة_الفرعية, الكمية_المتوفرة, آخر_تحديث) "
                "VALUES (?, ?, CURRENT_TIMESTAMP)",
                (mid, qty),
            )
        conn.commit()
        return mid
    finally:
        conn.close()


def _insert_audit_record(material_id, date_str, actual_qty):
    """تسجيل جرد دوري في جدول الجرد + تحرك المخزون."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO الجرد (التاريخ, معرف_المادة_الفرعية, الكمية_النظري, الكمية_الفعلي, فرق_الجرد, قيمة_الفرق, ملاحظات) "
            "VALUES (?, ?, ?, ?, ?, 0, ?)",
            (date_str, material_id, actual_qty, actual_qty, 0.0, "جرد اختبار"),
        )
        cur.execute(
            "INSERT INTO تحركات_المخزون (معرف_المادة_الفرعية, التاريخ, نوع_الحركة, الكمية, الرصيد_بعد, ملاحظات) "
            "VALUES (?, ?, 'جرد', 0, ?, ?)",
            (material_id, date_str, actual_qty, "جرد اختبار"),
        )
        conn.commit()
    finally:
        conn.close()


def _insert_purchase_movement(material_id, date_str, qty):
    """تسجيل حركة شراء في تحركات المخزون."""
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO تحركات_المخزون (معرف_المادة_الفرعية, التاريخ, نوع_الحركة, الكمية, الرصيد_بعد, ملاحظات) "
            "VALUES (?, ?, 'شراء', ?, ?, 'شراء اختبار')",
            (material_id, date_str, qty, qty),
        )
        conn.commit()
    finally:
        conn.close()


class TestBuyList:
    def test_material_below_min_appears_in_buy_list(self, db_conn):
        """مادة كميتها أقل من حدها الأدنى المحدد → تظهر في تقرير 'ما يجب شراؤه'."""
        mid = _make_material(min_qty=10.0, qty=5.0, name="قهوة غرين")
        cur = db_conn.cursor()

        items = get_buy_list(cur)

        assert len(items) == 1, f"توقع مادة واحدة، وصلنا {len(items)}"
        item = items[0]
        assert item["name"] == "قهوة غرين"
        assert item["current_qty"] == 5.0
        assert item["min_qty"] == 10.0
        assert item["diff"] == 5.0
        assert item["suggested_qty"] == 15.0

    def test_material_with_no_min_not_in_buy_list(self, db_conn):
        """مادة بلا حد أدنى محدد (0) → لا تظهر في التقرير حتى لو كانت كميتها منخفضة."""
        mid = _make_material(min_qty=0.0, qty=2.0, name="سكر")
        cur = db_conn.cursor()

        items = get_buy_list(cur)

        assert len(items) == 0, "المادة بلا حد أدنى لا يجب أن تظهر"
        cur.execute(
            "SELECT الكمية_المتوفرة FROM المخزون WHERE معرف_المادة_الفرعية = ?",
            (mid,),
        )
        assert cur.fetchone()[0] == 2.0


class TestConsumptionRate:
    def test_consumption_rate_correct_with_two_audits_and_purchases(self, db_conn):
        """مادة لها جردان متتاليان + مشتريات بينهما → معدل استهلاك شهري صحيح رقمياً.

        البيانات:
          - جرد أقدم: 2026-07-15 10:00:00 → الكمية = 100
          - شراء بينهما: 2026-08-01 12:00:00 → الكمية = 50
          - جرد أحدث: 2026-08-14 10:00:00 → الكمية = 80

          الاستهلاك = (100 + 50) - 80 = 70
          عدد الأيام = 30
          المعدل الشهري = 70 / 30 * 30 = 70.0
        """
        mid = _make_material(min_qty=50.0, qty=80.0, name="حليب")

        _insert_audit_record(mid, "2026-07-15 10:00:00", actual_qty=100.0)
        _insert_purchase_movement(mid, "2026-08-01 12:00:00", qty=50.0)
        _insert_audit_record(mid, "2026-08-14 10:00:00", actual_qty=80.0)

        cur = db_conn.cursor()
        rate, details = calculate_monthly_consumption(cur, mid)

        assert rate is not None, "يجب أن يُحسب معدل الاستهلاك"
        assert rate == pytest.approx(70.0, abs=0.01), f"معدل غير صحيح: {rate}"
        assert details["older_qty"] == 100.0
        assert details["newer_qty"] == 80.0
        assert details["purchases"] == 50.0
        assert details["consumption"] == 70.0
        assert details["days"] == pytest.approx(30.0, abs=0.01)

    def test_consumption_insufficient_data_with_one_audit(self, db_conn):
        """مادة بجرد واحد فقط → تُعرض 'لا تتوفر بيانات كافية' دون خطأ."""
        mid = _make_material(min_qty=10.0, qty=5.0, name="ملح")
        _insert_audit_record(mid, "2026-08-01 10:00:00", actual_qty=100.0)

        cur = db_conn.cursor()
        rate, reason = calculate_monthly_consumption(cur, mid)

        assert rate is None, "لا يجب حساب معدل به أقل من جردين"
        assert reason is not None
        assert "جرد" in reason or "بيانات" in reason

    def test_consumption_insufficient_data_with_no_audit(self, db_conn):
        """مادة بلا جرد أصلاً → تُعرض 'لا تتوفر بيانات كافية' دون خطأ."""
        _make_material(min_qty=5.0, qty=2.0, name="عسل")

        cur = db_conn.cursor()
        cur.execute(
            "SELECT معرف FROM المواد_الفرعية WHERE الاسم = ?",
            ("عسل",),
        )
        row = cur.fetchone()
        assert row is not None
        mid = row["معرف"]

        rate, reason = calculate_monthly_consumption(cur, mid)

        assert rate is None, "لا يجب حساب معدل بدون أي جرد"
        assert reason is not None
        assert "جرد" in reason or "بيانات" in reason
