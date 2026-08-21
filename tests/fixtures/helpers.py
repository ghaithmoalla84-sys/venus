from venus.core.database import get_conn
from venus.core.repositories import (
    GroupsRepository, MaterialsRepository, CreditorsRepository, SalesRepository
)
from tests.fixtures.constants import (
    TEST_DATE, DEFAULT_GROUP_NAME, DEFAULT_MATERIAL_NAME,
    DEFAULT_CREDITOR_NAME, DEFAULT_CURRENCY
)


def insert_group(name=DEFAULT_GROUP_NAME):
    repo = GroupsRepository()
    return repo.create(الاسم=name)


def insert_material(name=DEFAULT_MATERIAL_NAME, group_id=None, unit="قطعة", price=0.0, qty=0.0):
    if group_id is None:
        group_id = insert_group()
    repo = MaterialsRepository()
    mid = repo.create(الاسم=name, الوحدة=unit, معرف_المجموعة=group_id, سعر_الشراء_الأخير=price)
    if qty > 0:
        conn = get_conn()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO المخزون (معرف_المادة_الفرعية, الكمية_المتوفرة, آخر_تحديث) "
                "VALUES (?, ?, CURRENT_TIMESTAMP)", (mid, qty)
            )
            conn.commit()
        finally:
            conn.close()
    return mid


def insert_creditor(name=DEFAULT_CREDITOR_NAME, ctype="مورد", currency=DEFAULT_CURRENCY,
                    total=0.0, balance=0.0, status="نشط", تاريخ_استحقاق=None,
                    تاريخ_الإنشاء=None):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        if تاريخ_الإنشاء is not None:
            cursor.execute(
                "INSERT INTO الديون (اسم_الطرف, نوع_الطرف, العملة, المبلغ_الإجمالي, "
                "المبلغ_المدفوع, الرصيد, حالة_الدين, تاريخ_استحقاق, تاريخ_الإنشاء) "
                "VALUES (?, ?, ?, ?, 0, ?, 'نشط', ?, ?)",
                (name, ctype, currency, total, balance, تاريخ_استحقاق, تاريخ_الإنشاء)
            )
        else:
            cursor.execute(
                "INSERT INTO الديون (اسم_الطرف, نوع_الطرف, العملة, المبلغ_الإجمالي, "
                "المبلغ_المدفوع, الرصيد, حالة_الدين, تاريخ_استحقاق) "
                "VALUES (?, ?, ?, ?, 0, ?, 'نشط', ?)",
                (name, ctype, currency, total, balance, تاريخ_استحقاق)
            )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def insert_sale(group_id, date=TEST_DATE, amount=5000.0, currency=DEFAULT_CURRENCY, notes=""):
    repo = SalesRepository()
    return repo.create(
        التاريخ=date, معرف_المجموعة=group_id, المبلغ_الإجمالي=amount,
        العملة=currency, نوع_المعاملة="نقدي", ملاحظات=notes
    )


def insert_cash_day(date, opening=0.0, actual=0.0, diff=0.0, currency=DEFAULT_CURRENCY, closed=False):
    conn = get_conn()
    try:
        conn.execute(
            """INSERT INTO أرصدة_الصندوق
               (التاريخ, رصيد_بداية_اليوم, رصيد_نهاية_فعلي, فرق_التسوية, العملة, مغلقة)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (date, opening, actual, diff, currency, 1 if closed else 0)
        )
        conn.commit()
    finally:
        conn.close()


def insert_vault_balance(amount=2000000.0):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO الخزنة (التاريخ, البيان, إيداع, الرصيد_بعد_الحركة, ملاحظات) "
            "VALUES (CURRENT_TIMESTAMP, ?, ?, ?, ?)",
            ("رصيد افتتاحي", amount, amount, "رصيد اختبار")
        )
        conn.commit()
    finally:
        conn.close()


def insert_expense(date, amount, desc, etype="أخرى", currency=DEFAULT_CURRENCY):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO المصروفات (التاريخ, المبلغ, الوصف, نوع_المصروف, العملة) "
            "VALUES (?, ?, ?, ?, ?)",
            (date, amount, desc, etype, currency)
        )
        conn.commit()
    finally:
        conn.close()


def insert_withdrawal(date, amount, desc, currency=DEFAULT_CURRENCY):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO السحوبات (التاريخ, المبلغ, الوصف, العملة) "
            "VALUES (?, ?, ?, ?)",
            (date, amount, desc, currency)
        )
        conn.commit()
    finally:
        conn.close()


def insert_invoice(supplier=DEFAULT_CREDITOR_NAME, total=5000.0, date="2025-01-01",
                   currency=DEFAULT_CURRENCY):
    conn = get_conn()
    try:
        cursor = conn.execute(
            "INSERT INTO الديون (اسم_الطرف, نوع_الطرف, العملة, المبلغ_الإجمالي, "
            "المبلغ_المدفوع, الرصيد, حالة_الدين) VALUES (?, 'مورد', ?, ?, 0, ?, 'نشط')",
            (supplier, currency, total, total))
        debt_id = cursor.lastrowid
        conn.commit()

        cursor = conn.execute(
            "INSERT INTO فواتير_الشراء (التاريخ, معرف_المورد, اسم_المورد, "
            "المبلغ_الإجمالي, العملة) VALUES (?, ?, ?, ?, ?)",
            (date, debt_id, supplier, total, currency))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def insert_invoice_detail(invoice_id, material_id, qty=5.0, price=1000.0):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO تفاصيل_الشراء (معرف_الفاتورة, معرف_المادة_الفرعية, "
            "الكمية, سعر_الوحدة, المبلغ_الإجمالي) VALUES (?, ?, ?, ?, ?)",
            (invoice_id, material_id, qty, price, qty * price)
        )
        conn.commit()
    finally:
        conn.close()


def insert_debt_movement(debt_id, amount, mtype="إضافة", notes=""):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO تحركات_الديون (معرف_الدين, المبلغ, نوع_الحركة, ملاحظات) "
            "VALUES (?, ?, ?, ?)",
            (debt_id, amount, mtype, notes)
        )
        conn.commit()
    finally:
        conn.close()


def insert_operation_log(op_type, record_id, affected_date):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO سجل_العمليات_الأخيرة (نوع_العملية, معرف_السجل, التاريخ_المتأثر) "
            "VALUES (?, ?, ?)",
            (op_type, record_id, affected_date)
        )
        conn.commit()
    finally:
        conn.close()
