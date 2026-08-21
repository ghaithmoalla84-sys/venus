from venus.core.database import get_conn


def get_overdue_debts(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT
            معرف,
            اسم_الطرف,
            نوع_الطرف,
            العملة,
            الرصيد,
            تاريخ_استحقاق,
            CASE
                WHEN تاريخ_استحقاق IS NOT NULL
                THEN CAST(julianday('now') - julianday(تاريخ_استحقاق) AS INTEGER)
                ELSE CAST(julianday('now') - julianday(تاريخ_الإنشاء) AS INTEGER)
            END AS days_overdue
        FROM الديون
        WHERE الرصيد > 0.01
          AND حالة_الدين != 'مسدد'
          AND (
                (تاريخ_استحقاق IS NOT NULL AND تاريخ_استحقاق < date('now'))
                OR
                (تاريخ_استحقاق IS NULL AND (
                      date('now', '-30 days') > date(تاريخ_الإنشاء)
                      OR EXISTS (
                          SELECT 1
                          FROM تحركات_الديون td
                          WHERE td.معرف_الدين = الديون.معرف
                            AND td.نوع_الحركة = 'إضافة'
                            AND date('now', '-30 days') > date(td.التاريخ)
                      )
                ))
          )
        ORDER BY days_overdue DESC, اسم_الطرف ASC
    """)
    return [dict(row) for row in cur.fetchall()]
