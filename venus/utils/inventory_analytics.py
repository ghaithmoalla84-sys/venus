# -*- coding: utf-8 -*-
"""
تحليلات المخزون الذكي - Venus Coffee
دوال مساعدة لحساب معدل الاستهلاك الشهري وتقرير "ما يجب شراؤه الآن".
"""

from datetime import datetime

from venus.utils.logger import setup_logger

logger = setup_logger()


def calculate_monthly_consumption(cur, material_id):
    """حساب معدل الاستهلاك الشهري التقديري لمادة معينة.

    يعتمد على آخر عمليتي جرد متتاليتين وفوق الشراء المسجل بينهما:
        الاستهلاك = (كمية الجرد الأقدم + مشتريات بين الجردين) − كمية الجرد الأحدث
        ثم يقسَّب على عدد الأيام الفعلي ويُضاعف × 30.

    :param cur: مؤشر قاعدة بيانات (cursor) متصل.
    :param material_id: معرف المادة الفرعية.
    :return: tuple (monthly_rate, details) إذا توفرت البيانات، وإلا (None, reason_msg).
             monthly_rate: float — معدل شهري تقديري.
             details: dict يحتوي على القيم الوسيطة للشرح.
    """
    cur.execute(
        """
        SELECT التاريخ, الكمية_الفعلي
        FROM الجرد
        WHERE معرف_المادة_الفرعية = ?
        ORDER BY التاريخ DESC
        LIMIT 2
        """,
        (material_id,),
    )
    audits = cur.fetchall()

    if len(audits) < 2:
        reason = (
            "جرد واحد فقط — يحتاج جرداً ثانياً لاحقاً"
            if len(audits) == 1
            else "لا يوجد جرد مسجل بعد"
        )
        return None, reason

    newer_date, newer_qty = audits[0]["التاريخ"], audits[0]["الكمية_الفعلي"]
    older_date, older_qty = audits[1]["التاريخ"], audits[1]["الكمية_الفعلي"]

    cur.execute(
        """
        SELECT COALESCE(SUM(الكمية), 0) AS total_purchases
        FROM تحركات_المخزون
        WHERE معرف_المادة_الفرعية = ?
          AND نوع_الحركة = 'شراء'
          AND التاريخ >= ? AND التاريخ <= ?
        """,
        (material_id, older_date, newer_date),
    )
    purchases_row = cur.fetchone()
    purchases = purchases_row["total_purchases"] if purchases_row else 0
    if purchases is None:
        purchases = 0

    consumption = (older_qty or 0) + purchases - (newer_qty or 0)

    try:
        t1 = datetime.strptime(str(older_date), "%Y-%m-%d %H:%M:%S")
        t2 = datetime.strptime(str(newer_date), "%Y-%m-%d %H:%M:%S")
        days = (t2 - t1).total_seconds() / 86400.0
    except (ValueError, TypeError):
        return None, "تنسيق تاريخ الجرد غير صالح"

    if days <= 0:
        return None, "تواريخ الجرد غير متسلسلة"

    monthly_rate = (consumption / days) * 30

    details = {
        "older_qty": older_qty,
        "newer_qty": newer_qty,
        "purchases": purchases,
        "consumption": consumption,
        "days": days,
    }
    return monthly_rate, details


def get_buy_list(cur, include_consumption=True):
    """الحصول على قائمة المواد التي يجب شراؤها الآن.

    يرجع المواد التي:
        - الكمية المتوفرة <= الحد الأدنى
        - الحد الأدنى > 0 (أي أن صاحب المتجر حدد حدّاً مخصّصاً)

    :param cur: مؤشر قاعدة بيانات متصل.
    :param include_consumption: إذا True، يحسّن معدل الاستهلاك لكل مادة.
    :return: قائمة من القواميس تحتوي على:
             - الاسم، الوحدة، اسم المجموعة
             - الكمية_الحالية، الحد_الأدنى، الفرق
             - المقترح_شراء (لضعف الحد الأدنى)
             - معدل_الاستهلاك_الشهري (float أو "لا تتوفر بيانات كافية")
    """
    cur.execute(
        """
        SELECT
            م.معرف             AS material_id,
            م.الاسم            AS name,
            م.الوحدة           AS unit,
            ج.الاسم            AS group_name,
            COALESCE(خ.الكمية_المتوفرة, 0) AS current_qty,
            COALESCE(م.الحد_الأدنى, 0)      AS min_qty
        FROM المواد_الفرعية م
        JOIN المجموعات ج ON م.معرف_المجموعة = ج.معرف
        LEFT JOIN المخزون خ ON م.معرف = خ.معرف_المادة_الفرعية
        WHERE COALESCE(م.الحد_الأدنى, 0) > 0
          AND COALESCE(خ.الكمية_المتوفرة, 0) <= COALESCE(م.الحد_الأدنى, 0)
        ORDER BY (خ.الكمية_المتوفرة - م.الحد_الأدنى) ASC, م.الاسم
        """
    )
    rows = cur.fetchall()

    result = []
    for row in rows:
        current = row["current_qty"] or 0
        minimum = row["min_qty"] or 0
        diff = minimum - current
        suggested = max(minimum * 2 - current, 0)

        consumption_str = "—"
        if include_consumption:
            rate, reason = calculate_monthly_consumption(cur, row["material_id"])
            if rate is not None:
                consumption_str = f"{rate:,.2f}"
            else:
                consumption_str = "لا تتوفر بيانات كافية"

        result.append({
            "material_id": row["material_id"],
            "name": row["name"],
            "unit": row["unit"],
            "group_name": row["group_name"],
            "current_qty": current,
            "min_qty": minimum,
            "diff": diff,
            "suggested_qty": suggested,
            "monthly_consumption": consumption_str,
            "consumption_reason": None,
        })

        if include_consumption and consumption_str == "لا تتوفر بيانات كافية":
            result[-1]["consumption_reason"] = reason

    return result
