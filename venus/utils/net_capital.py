# -*- coding: utf-8 -*-
"""
حساب رأس المال الصافي التقديري - Venus Coffee
الصيغة: رأس المال الصافي = (رصيد الدرج + رصيد الخزنة + قيمة المخزون) - إجمالي الديون

هذه الوحدة أصبحت غلافاً (wrapper) حول المستودع المالي المركزي
venus.core.repositories.financial لضمان مصدر حقيقة واحد لجميع الحسابات المالية.
"""

from datetime import datetime, timedelta

from venus.core.database import get_conn, today_str, yesterday_str
from venus.core.repositories import (
    get_financial_exchange_rate as _get_exchange_rate,
    get_vault_balance as _get_vault_balance,
    get_total_debts_in_syp as _get_total_debts,
    get_inventory_value as _get_inventory_value,
    get_drawer_balance,
    get_net_capital,
)


def _get_drawer_balance(date_str):
    return get_drawer_balance(date_str)


def calculate_net_capital(date=None):
    d = date or today_str()
    result = get_net_capital(d)
    return result["net_capital"]


def get_yesterday_net_capital():
    yesterday = yesterday_str()
    conn = get_conn()
    try:
        cur = conn.cursor()
        next_date = (datetime.strptime(yesterday, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        cur.execute(
            "SELECT مغلقة, رصيد_نهاية_فعلي, رصيد_الخزنة, العملة FROM أرصدة_الصندوق WHERE التاريخ >= ? AND التاريخ < ?",
            (yesterday, next_date),
        )
        row = cur.fetchone()
        if row and row["مغلقة"]:
            drawer = row["رصيد_نهاية_فعلي"] or 0
            vault = row["رصيد_الخزنة"] or 0
            currency = row["العملة"] or "ليرة_سورية"
            if currency == "دولار":
                drawer = drawer * _get_exchange_rate()
            inventory = _get_inventory_value()
            debts = _get_total_debts()
            return drawer + vault + inventory - debts
        return None
    finally:
        conn.close()
