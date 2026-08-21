# -*- coding: utf-8 -*-
"""
مستودعات الوصول للبيانات (Repositories Layer) - Venus Coffee
توفر طبقة تجريد عليا فوق قاعدة البيانات SQLite باستخدام get_conn() من database.py.
"""

from .base_repository import BaseRepository, RepositoryError
from .groups_repository import GroupsRepository
from .materials_repository import MaterialsRepository
from .creditors_repository import CreditorsRepository
from .sales_repository import SalesRepository

from venus.core.repositories.financial import (
    get_vault_balance,
    get_total_debts_in_syp,
    get_debts_breakdown,
    get_drawer_balance,
    get_inventory_value,
    get_net_capital,
    get_exchange_rate as get_financial_exchange_rate
)

__all__ = [
    "BaseRepository",
    "RepositoryError",
    "GroupsRepository",
    "MaterialsRepository",
    "CreditorsRepository",
    "SalesRepository",
    "get_vault_balance",
    "get_total_debts_in_syp",
    "get_debts_breakdown",
    "get_drawer_balance",
    "get_inventory_value",
    "get_net_capital",
    "get_financial_exchange_rate",
]
