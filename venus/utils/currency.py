# -*- coding: utf-8 -*-
"""
دوال مساعدة لعرض القيم المالية
الليرة السورية لا تحتوي على كسور عشرية
"""


def fmt(value):
    """تنسيق القيمة المالية كرقم صحيح بدون كسور عشرية"""
    return f"{int(round(value or 0)):,}"


def fmt_syp(value):
    """تنسيق القيمة المالية مع عملة ليرة سورية"""
    return f"{fmt(value)} ليرة سورية"


def fmt_usd(value):
    """تنسيق القيمة المالية مع عملة دولار"""
    return f"{fmt(value)} دولار"


def round_currency(value):
    """تقريب القيمة المالية إلى أقرب ليرة"""
    return int(round(value or 0))


def get_exchange_rate(conn=None):
    from venus.core.database import get_conn
    conn_provided = conn is not None
    if conn is None:
        conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT القيمة FROM الإعدادات WHERE المفتاح = 'سعر_صرف_الدولار'")
        row = cur.fetchone()
        if row and row["القيمة"]:
            return float(row["القيمة"])
        return None
    except Exception:
        return None
    finally:
        if not conn_provided:
            conn.close()
