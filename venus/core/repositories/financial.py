# -*- coding: utf-8 -*-
"""
Financial Repository - مستودع مالي مركزي
مصدر حقيقة واحد لجميع الحسابات المالية في التطبيق
جميع الشاشات يجب أن تقرأ منه بدلاً من حساب أرقامها بنفسها
"""

from venus.core.database import get_conn
from venus.utils.logger import setup_logger
logger = setup_logger()


def get_exchange_rate() -> float:
    """سعر صرف الدولار بالليرة السورية - المصدر الوحيد"""
    from venus.utils.currency import get_exchange_rate as _get
    rate = _get()
    return rate if rate is not None else 8500.0


def get_vault_balance() -> float:
    """
    رصيد الخزنة الحالي - يقرأ مباشرة من جدول الخزنة
    هذا هو المصدر الوحيد الصحيح لرصيد الخزنة
    """
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT الرصيد_بعد_الحركة FROM الخزنة
            ORDER BY معرف DESC LIMIT 1
        """)
        row = cur.fetchone()
        return float(row[0]) if row else 0.0
    except Exception as e:
        logger.error(f"get_vault_balance خطأ: {e}")
        return 0.0
    finally:
        if conn:
            conn.close()


def get_total_debts_in_syp() -> float:
    """
    إجمالي الديون النشطة محوّلة بالكامل إلى ليرة سورية
    الدولار يُحوَّل بسعر الصرف الحالي
    """
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT العملة, COALESCE(الرصيد, 0) as الرصيد
            FROM الديون
            WHERE حالة_الدين != 'مسدد'
        """)
        rows = cur.fetchall()
        rate = get_exchange_rate()
        total = 0.0
        for row in rows:
            if row[0] == "دولار":
                total += row[1] * rate
            else:
                total += row[1]
        return total
    except Exception as e:
        logger.error(f"get_total_debts_in_syp خطأ: {e}")
        return 0.0
    finally:
        if conn:
            conn.close()


def get_debts_breakdown() -> dict:
    """
    تفصيل الديون النشطة منفصلة بالعملة
    يرجع: {syp: float, usd: float, total_in_syp: float}
    """
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT العملة, COALESCE(الرصيد, 0) as الرصيد
            FROM الديون
            WHERE حالة_الدين != 'مسدد'
        """)
        rows = cur.fetchall()
        rate = get_exchange_rate()
        syp = 0.0
        usd = 0.0
        for row in rows:
            if row[0] == "دولار":
                usd += row[1]
            else:
                syp += row[1]
        return {
            "syp": syp,
            "usd": usd,
            "total_in_syp": syp + (usd * rate),
            "rate": rate
        }
    except Exception as e:
        logger.error(f"get_debts_breakdown خطأ: {e}")
        return {"syp": 0.0, "usd": 0.0, "total_in_syp": 0.0, "rate": 8500.0}


def get_drawer_balance(date_str: str) -> float:
    """
    رصيد الدرج ليوم محدد (بالليرة السورية)
    - إذا كانت اليومية مغلقة: استخدم رصيد_نهاية_فعلي
    - إذا كانت مفتوحة: احسب (رصيد_بداية_اليوم + المبيعات)
    - إذا لم توجد يومية للتاريخ: ارجع لآخر يوم مغلق سابق
    - يحوّل الدولار إلى ليرة سورية بسعر الصرف الحالي
    """
    conn = None
    try:
        from datetime import datetime, timedelta
        conn = get_conn()
        cur = conn.cursor()
        next_date = (
            datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)
        ).strftime("%Y-%m-%d")

        cur.execute("""
            SELECT * FROM أرصدة_الصندوق
            WHERE التاريخ >= ? AND التاريخ < ?
        """, (date_str, next_date))
        row = cur.fetchone()
        if row:
            cash_currency = row["العملة"] or "ليرة_سورية"
            if not row["مغلقة"]:
                opening = row["رصيد_بداية_اليوم"] or 0
                cur.execute("""
                    SELECT COALESCE(SUM(المبلغ_الإجمالي), 0)
                    FROM المبيعات_اليومية
                    WHERE التاريخ >= ? AND التاريخ < ?
                """, (date_str, next_date))
                sales = cur.fetchone()[0] or 0
                balance = opening + sales
            else:
                balance = row["رصيد_نهاية_فعلي"] or 0
            if cash_currency == "دولار":
                balance = balance * get_exchange_rate()
            return float(balance)
        else:
            cur.execute("""
                SELECT رصيد_نهاية_فعلي, العملة FROM أرصدة_الصندوق
                WHERE مغلقة = 1 ORDER BY التاريخ DESC LIMIT 1
            """)
            prev = cur.fetchone()
            if prev:
                balance = prev["رصيد_نهاية_فعلي"] or 0
                if prev["العملة"] == "دولار":
                    balance = balance * get_exchange_rate()
                return float(balance)
            return 0.0
    except Exception as e:
        logger.error(f"get_drawer_balance خطأ: {e}")
        return 0.0
    finally:
        if conn:
            conn.close()


def get_inventory_value() -> float:
    """
    قيمة المخزون الحالية = مجموع (الكمية × سعر الشراء الأخير)
    """
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT COALESCE(SUM(خ.الكمية_المتوفرة * م.سعر_الشراء_الأخير), 0)
            FROM المخزون خ
            JOIN المواد_الفرعية م ON خ.معرف_المادة_الفرعية = م.معرف
            WHERE م.سعر_الشراء_الأخير > 0
        """)
        row = cur.fetchone()
        return float(row[0]) if row else 0.0
    except Exception as e:
        logger.error(f"get_inventory_value خطأ: {e}")
        return 0.0
    finally:
        if conn:
            conn.close()


def get_net_capital(date_str: str) -> dict:
    """
    رأس المال الصافي - المعادلة الموحدة:
    رأس المال = الخزنة + الدرج + المخزون - الديون (بالليرة)

    يرجع dict بجميع المكونات للعرض التفصيلي
    """
    vault = get_vault_balance()
    drawer = get_drawer_balance(date_str)
    inventory = get_inventory_value()
    debts = get_total_debts_in_syp()
    net = vault + drawer + inventory - debts

    return {
        "vault": vault,
        "drawer": drawer,
        "inventory": inventory,
        "debts": debts,
        "net_capital": net
    }
