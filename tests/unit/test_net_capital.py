# -*- coding: utf-8 -*-
"""Tests for net capital calculation - Venus Coffee"""

import pytest
from unittest.mock import patch
from datetime import datetime, timedelta

from venus.utils.net_capital import calculate_net_capital, get_yesterday_net_capital
from tests.fixtures.helpers import (
    insert_group, insert_material, insert_vault_balance,
    insert_cash_day, insert_expense, insert_withdrawal,
    insert_creditor, insert_sale
)
from venus.core.database import get_conn, today_str


class TestNetCapitalCalculation:
    def test_manual_calculation_known_values(self, qt_app, temp_db):
        with patch('venus.core.database.today_str', return_value="2026-08-15"):
            conn = get_conn()
            conn.execute(
                "UPDATE الإعدادات SET القيمة = '10000' WHERE المفتاح = 'سعر_صرف_الدولار'"
            )
            conn.commit()
            conn.close()

            group_id = insert_group('test_manual')
            insert_material('mat_manual', group_id=group_id, qty=10, price=5000)

            insert_vault_balance(2000000)

            insert_cash_day('2026-08-15', opening=100000, actual=0, diff=0, closed=False)
            insert_sale(group_id, date='2026-08-15', amount=50000)
            insert_expense('2026-08-15', 10000, 'manual expense')
            insert_withdrawal('2026-08-15', 5000, 'manual withdrawal')

            insert_creditor('manual_creditor', balance=100000, currency='ليرة_سورية', status='نشط')

            expected = 100000 + 50000 - 10000 - 5000 + 2000000 + 50000 - 100000
            result = calculate_net_capital('2026-08-15')
            assert result == expected

    def test_no_yesterday_closed_journal(self, qt_app, temp_db):
        with patch('venus.core.database.today_str', return_value="2026-08-15"):
            conn = get_conn()
            conn.execute(
                "UPDATE الإعدادات SET القيمة = '10000' WHERE المفتاح = 'سعر_صرف_الدولار'"
            )
            conn.commit()
            conn.close()

            group_id = insert_group('test_no_yesterday')
            insert_material('mat_no_yesterday', group_id=group_id, qty=5, price=2000)
            insert_vault_balance(1000000)

            insert_cash_day('2026-08-15', opening=50000, actual=0, diff=0, closed=False)
            insert_sale(group_id, date='2026-08-15', amount=20000)
            insert_expense('2026-08-15', 5000, 'expense')
            insert_withdrawal('2026-08-15', 2000, 'withdrawal')

            result = get_yesterday_net_capital()
            assert result is None

    def test_usd_debt_converted_with_exchange_rate(self, qt_app, temp_db):
        with patch('venus.core.database.today_str', return_value="2026-08-15"):
            conn = get_conn()
            conn.execute(
                "UPDATE الإعدادات SET القيمة = '10000' WHERE المفتاح = 'سعر_صرف_الدولار'"
            )
            conn.commit()
            conn.close()

            group_id = insert_group('test_usd')
            insert_material('mat_usd', group_id=group_id, qty=5, price=2000)
            insert_vault_balance(1000000)

            insert_cash_day('2026-08-15', opening=50000, actual=0, diff=0, closed=False, currency='دولار')
            insert_sale(group_id, date='2026-08-15', amount=20000)
            insert_expense('2026-08-15', 5000, 'expense', currency='دولار')
            insert_withdrawal('2026-08-15', 2000, 'withdrawal', currency='دولار')

            insert_creditor('usd_creditor', balance=100, currency='دولار', status='نشط')

            expected = (50000 + 20000 - 5000 - 2000) * 10000 + 1000000 + 10000 - (100 * 10000)
            result = calculate_net_capital('2026-08-15')
            assert result == expected

    def test_usd_drawer_converted_to_syp(self, qt_app, temp_db):
        with patch('venus.core.database.today_str', return_value="2026-08-15"):
            conn = get_conn()
            conn.execute(
                "UPDATE الإعدادات SET القيمة = '10000' WHERE المفتاح = 'سعر_صرف_الدولار'"
            )
            conn.commit()
            conn.close()

            group_id = insert_group('test_usd_drawer')
            insert_material('mat_usd_drawer', group_id=group_id, qty=5, price=2000)
            insert_vault_balance(1000000)

            insert_cash_day('2026-08-15', opening=50000, actual=0, diff=0, closed=False, currency='دولار')
            insert_sale(group_id, date='2026-08-15', amount=20000)
            insert_expense('2026-08-15', 5000, 'expense', currency='دولار')
            insert_withdrawal('2026-08-15', 2000, 'withdrawal', currency='دولار')

            result = calculate_net_capital('2026-08-15')
            drawer_in_syp = (50000 + 20000 - 5000 - 2000) * 10000
            expected = drawer_in_syp + 1000000 + 10000
            assert result == expected
