#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Remove business records from a cloned Odoo DB while keeping users, employees,
installed modules, and configuration intact.

Usage:
  sudo -u odoo17-v2 python3 scripts/cleanup_employee_beta_db.py --db BetaEmployeeDB1
"""
from __future__ import print_function

import argparse
import sys

try:
    import psycopg2
except ImportError:
    print("Install psycopg2: pip install psycopg2-binary", file=sys.stderr)
    sys.exit(1)


# Transactional / business tables to clear (child tables first)
BUSINESS_TABLES = [
    "hr_attendance_edit_request",
    "hr_leave_report",
    "mail_notification",
    "mail_followers",
    "mail_mail",
    "mail_message",
    "account_move_line",
    "account_move",
    "account_payment",
    "account_bank_statement_line",
    "account_bank_statement",
    "sale_order_line",
    "sale_order",
    "purchase_order_line",
    "purchase_order",
    "project_task",
    "project_project",
    "stock_move_line",
    "stock_move",
    "stock_picking",
    "stock_quant",
    "hr_leave",
    "hr_leave_allocation",
    "hr_leave_accrual_plan_level",
    "hr_leave_accrual_plan",
    "hr_attendance",
    "hr_expense",
    "hr_expense_sheet",
    "hr_payslip_line",
    "hr_payslip",
    "hr_payslip_run",
    "crm_lead",
    "calendar_event",
    "maintenance_request",
    "mrp_workorder",
    "mrp_production",
]


def table_exists(cur, table):
    cur.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=%s",
        (table,),
    )
    return cur.fetchone() is not None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="BetaEmployeeDB1")
    parser.add_argument("--db-user", default="odoo17-v2")
    args = parser.parse_args()

    conn = psycopg2.connect(dbname=args.db, user=args.db_user)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        for table in BUSINESS_TABLES:
            if not table_exists(cur, table):
                continue
            try:
                cur.execute("DELETE FROM %s" % table)
                print("  cleared %s (%d rows)" % (table, cur.rowcount))
            except Exception as exc:
                conn.rollback()
                cur = conn.cursor()
                try:
                    cur.execute("TRUNCATE %s CASCADE" % table)
                    print("  truncated %s (cascade)" % table)
                except Exception:
                    conn.rollback()
                    cur = conn.cursor()
                    print("  skip %s (%s)" % (table, exc))

        # Reset sequences for cleared tables
        for table in BUSINESS_TABLES:
            if not table_exists(cur, table):
                continue
            cur.execute("SELECT pg_get_serial_sequence(%s, 'id')", (table,))
            row = cur.fetchone()
            if row and row[0]:
                cur.execute("SELECT setval(%s, 1, false)", (row[0],))

        conn.commit()
        print("Cleanup complete for %s." % args.db)
    except Exception as exc:
        conn.rollback()
        print("ERROR: %s" % exc, file=sys.stderr)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
