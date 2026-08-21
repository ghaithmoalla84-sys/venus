# -*- coding: utf-8 -*-
"""
Financial Integrity Checker - نظام فحص النزاهة المالية
يتحقق من صحة المعادلات المحاسبية الأساسية
ويُنبّه عند اكتشاف أي تناقض
"""

from venus.core.database import get_conn
from venus.utils.logger import setup_logger
logger = setup_logger()


class IntegrityResult:
    """نتيجة فحص واحد"""
    def __init__(self, name, passed, expected, actual, diff, note=""):
        self.name = name
        self.passed = passed
        self.expected = expected
        self.actual = actual
        self.diff = diff
        self.note = note

    def __repr__(self):
        status = "✅" if self.passed else "❌"
        return (
            f"{status} {self.name}: "
            f"متوقع={self.expected:,.0f} | "
            f"فعلي={self.actual:,.0f} | "
            f"فرق={self.diff:,.0f}"
            + (f" | {self.note}" if self.note else "")
        )


def check_vault_balance() -> IntegrityResult:
    """
    فحص 1: رصيد الخزنة
    المعادلة: آخر رصيد = مجموع الإيداعات - مجموع السحوبات
    """
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()

        # آخر رصيد مسجل
        cur.execute("""
            SELECT COALESCE(الرصيد_بعد_الحركة, 0)
            FROM الخزنة ORDER BY معرف DESC LIMIT 1
        """)
        row = cur.fetchone()
        last_balance = float(row[0]) if row else 0.0

        # مجموع الإيداعات - مجموع السحوبات
        cur.execute("""
            SELECT
                COALESCE(SUM(إيداع), 0) - COALESCE(SUM(سحب), 0)
            FROM الخزنة
        """)
        row = cur.fetchone()
        calculated = float(row[0]) if row else 0.0

        diff = abs(last_balance - calculated)
        passed = diff < 1.0  # هامش ليرة واحدة للتقريب

        return IntegrityResult(
            name="رصيد الخزنة",
            passed=passed,
            expected=calculated,
            actual=last_balance,
            diff=diff,
            note="الرصيد الأخير لا يتطابق مع مجموع الحركات"
                 if not passed else ""
        )
    except Exception as e:
        logger.error(f"check_vault_balance خطأ: {e}")
        return IntegrityResult(
            "رصيد الخزنة", False, 0, 0, 0,
            f"خطأ في الفحص: {e}"
        )
    finally:
        if conn:
            conn.close()


def check_debt_balances() -> IntegrityResult:
    """
    فحص 2: أرصدة الديون
    المعادلة: الرصيد = المبلغ_الإجمالي - المبلغ_المدفوع
    لكل دائن
    """
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            SELECT معرف, اسم_الطرف,
                   المبلغ_الإجمالي,
                   المبلغ_المدفوع,
                   الرصيد
            FROM الديون
            WHERE حالة_الدين != 'مسدد'
        """)
        rows = cur.fetchall()

        errors = []
        for row in rows:
            cid, name, total, paid, balance = (
                row[0], row[1], row[2] or 0,
                row[3] or 0, row[4] or 0
            )
            expected_balance = total - paid
            diff = abs(balance - expected_balance)
            if diff >= 1.0:
                errors.append(
                    f"{name}: رصيد={balance:,.0f} "
                    f"متوقع={expected_balance:,.0f}"
                )

        passed = len(errors) == 0
        return IntegrityResult(
            name="أرصدة الديون",
            passed=passed,
            expected=0,
            actual=len(errors),
            diff=len(errors),
            note=("تناقض في: " + " | ".join(errors))
                 if errors else ""
        )
    except Exception as e:
        logger.error(f"check_debt_balances خطأ: {e}")
        return IntegrityResult(
            "أرصدة الديون", False, 0, 0, 0,
            f"خطأ في الفحص: {e}"
        )
    finally:
        if conn:
            conn.close()


def check_debt_movements() -> IntegrityResult:
    """
    فحص 3: حركات الديون
    المعادلة: المبلغ_الإجمالي = مجموع حركات الإضافة
              المبلغ_المدفوع = مجموع حركات الدفعات
    """
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                د.معرف,
                د.اسم_الطرف,
                د.المبلغ_الإجمالي,
                د.المبلغ_المدفوع,
                COALESCE(SUM(CASE WHEN ح.نوع_الحركة='إضافة'
                    THEN ح.المبلغ ELSE 0 END), 0) as إجمالي_إضافات,
                COALESCE(SUM(CASE WHEN ح.نوع_الحركة='دفعة'
                    THEN ح.المبلغ ELSE 0 END), 0) as إجمالي_دفعات
            FROM الديون د
            LEFT JOIN تحركات_الديون ح ON ح.معرف_الدين = د.معرف
            GROUP BY د.معرف
        """)
        rows = cur.fetchall()

        errors = []
        for row in rows:
            (cid, name, total, paid,
             sum_add, sum_pay) = (
                row[0], row[1],
                row[2] or 0, row[3] or 0,
                row[4] or 0, row[5] or 0
            )
            if abs(total - sum_add) >= 1.0:
                errors.append(
                    f"{name}: إجمالي={total:,.0f} "
                    f"مجموع_إضافات={sum_add:,.0f}"
                )
            if abs(paid - sum_pay) >= 1.0:
                errors.append(
                    f"{name}: مدفوع={paid:,.0f} "
                    f"مجموع_دفعات={sum_pay:,.0f}"
                )

        passed = len(errors) == 0
        return IntegrityResult(
            name="حركات الديون",
            passed=passed,
            expected=0,
            actual=len(errors),
            diff=len(errors),
            note=("تناقض في: " + " | ".join(errors[:3]))
                 if errors else ""
        )
    except Exception as e:
        logger.error(f"check_debt_movements خطأ: {e}")
        return IntegrityResult(
            "حركات الديون", False, 0, 0, 0,
            f"خطأ في الفحص: {e}"
        )
    finally:
        if conn:
            conn.close()


def check_inventory_movements() -> IntegrityResult:
    """
    فحص 4: المخزون
    المعادلة: الكمية_المتوفرة = مجموع حركات الشراء - مجموع تعديلات الجرد
    (تحقق مبسّط: الكمية لا تكون سالبة)
    """
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            SELECT م.الاسم, خ.الكمية_المتوفرة
            FROM المخزون خ
            JOIN المواد_الفرعية م
              ON خ.معرف_المادة_الفرعية = م.معرف
            WHERE خ.الكمية_المتوفرة < 0
        """)
        negative = cur.fetchall()

        errors = [
            f"{row[0]}: {row[1]:,.2f}"
            for row in negative
        ]

        passed = len(errors) == 0
        return IntegrityResult(
            name="سلامة المخزون",
            passed=passed,
            expected=0,
            actual=len(errors),
            diff=len(errors),
            note=("كميات سالبة: " + " | ".join(errors))
                 if errors else ""
        )
    except Exception as e:
        logger.error(f"check_inventory_movements خطأ: {e}")
        return IntegrityResult(
            "سلامة المخزون", False, 0, 0, 0,
            f"خطأ في الفحص: {e}"
        )
    finally:
        if conn:
            conn.close()


def check_daily_cash_balance(date_str: str) -> IntegrityResult:
    """
    فحص 5: تطابق مبيعات اليوم المخزونة مع الفعلية
    المعادلة: مبيعات_اليوم في أرصدة_الصندوق
              = SUM من المبيعات_اليومية
    """
    conn = None
    try:
        from datetime import datetime, timedelta
        conn = get_conn()
        cur = conn.cursor()

        next_date = (
            datetime.strptime(date_str, "%Y-%m-%d")
            + timedelta(days=1)
        ).strftime("%Y-%m-%d")

        cur.execute("""
            SELECT مبيعات_اليوم, مغلقة
            FROM أرصدة_الصندوق
            WHERE التاريخ >= ? AND التاريخ < ?
            LIMIT 1
        """, (date_str, next_date))
        row = cur.fetchone()

        if not row or not row[1]:
            return IntegrityResult(
                f"مبيعات {date_str}",
                True, 0, 0, 0,
                "يوم مفتوح أو غير موجود - تجاوز"
            )

        stored_sales = float(row[0] or 0)

        cur.execute("""
            SELECT COALESCE(SUM(المبلغ_الإجمالي), 0)
            FROM المبيعات_اليومية
            WHERE التاريخ >= ? AND التاريخ < ?
        """, (date_str, next_date))
        actual_sales = float(cur.fetchone()[0] or 0)

        diff = abs(stored_sales - actual_sales)
        passed = diff < 1.0

        return IntegrityResult(
            name=f"مبيعات {date_str}",
            passed=passed,
            expected=actual_sales,
            actual=stored_sales,
            diff=diff,
            note="مبيعات مخزونة لا تتطابق مع المبيعات الفعلية"
                 if not passed else ""
        )
    except Exception as e:
        logger.error(f"check_daily_cash_balance خطأ: {e}")
        return IntegrityResult(
            f"مبيعات {date_str}", False, 0, 0, 0,
            f"خطأ في الفحص: {e}"
        )
    finally:
        if conn:
            conn.close()


def run_all_checks(days_back: int = 7) -> list:
    """
    تشغيل جميع الفحوصات وإرجاع النتائج
    days_back: عدد الأيام الماضية للتحقق من التسويات
    """
    from datetime import datetime, timedelta

    results = []

    # الفحوصات الثابتة
    results.append(check_vault_balance())
    results.append(check_debt_balances())
    results.append(check_debt_movements())
    results.append(check_inventory_movements())

    return results


def get_failed_checks(days_back: int = 7) -> list:
    """إرجاع الفحوصات الفاشلة فقط"""
    return [r for r in run_all_checks(days_back)
            if not r.passed]
