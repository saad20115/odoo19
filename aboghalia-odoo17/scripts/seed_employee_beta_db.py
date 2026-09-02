#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
One-time seed: copy users, employees, and auth data from BetaDB1 → BetaEmployeeDB1.

Preserves login passwords and group memberships. Does NOT copy business records.

Usage (on server):
  sudo -u odoo17-v2 python3 scripts/seed_employee_beta_db.py \\
    --source BetaDB1 --target BetaEmployeeDB1
"""
from __future__ import print_function

import argparse
import sys

try:
    import psycopg2
    from psycopg2 import sql
except ImportError:
    print("Install psycopg2: pip install psycopg2-binary", file=sys.stderr)
    sys.exit(1)


def connect(dbname, host=False, port=False, user="odoo17-v2", password=None):
    kwargs = {"dbname": dbname, "user": user}
    if host:
        kwargs["host"] = host
    if port:
        kwargs["port"] = port
    if password:
        kwargs["password"] = password
    return psycopg2.connect(**kwargs)


def table_exists(cur, table):
    cur.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=%s",
        (table,),
    )
    return cur.fetchone() is not None


def get_columns(cur, table):
    cur.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        ORDER BY ordinal_position
        """,
        (table,),
    )
    return [r[0] for r in cur.fetchall()]


def copy_table(src, tgt, table, where=None, delete_target=True):
    src_cur = src.cursor()
    tgt_cur = tgt.cursor()
    if not table_exists(src_cur, table):
        print("  skip %s (missing on source)" % table)
        return 0
    if not table_exists(tgt_cur, table):
        print("  skip %s (missing on target)" % table)
        return 0

    src_cols = get_columns(src_cur, table)
    tgt_cols = get_columns(tgt_cur, table)
    cols = [c for c in src_cols if c in tgt_cols]
    if not cols:
        print("  skip %s (no common columns)" % table)
        return 0

    col_list = sql.SQL(", ").join(map(sql.Identifier, cols))
    placeholders = sql.SQL(", ").join(sql.Placeholder() * len(cols))

    if delete_target:
        if where:
            tgt_cur.execute(sql.SQL("DELETE FROM {} WHERE ").format(sql.Identifier(table)) + sql.SQL(where))
        else:
            tgt_cur.execute(sql.SQL("DELETE FROM {}").format(sql.Identifier(table)))

    query = sql.SQL("SELECT {} FROM {}").format(col_list, sql.Identifier(table))
    if where:
        query = query + sql.SQL(" WHERE ") + sql.SQL(where)
    src_cur.execute(query)
    rows = src_cur.fetchall()
    if not rows:
        print("  %s: 0 rows" % table)
        return 0

    insert = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        sql.Identifier(table), col_list, placeholders
    )
    for row in rows:
        tgt_cur.execute(insert, row)
    print("  %s: %d rows" % (table, len(rows)))
    return len(rows)


def reset_sequence(tgt, table):
    cur = tgt.cursor()
    if not table_exists(cur, table):
        return
    cur.execute(
        """
        SELECT pg_get_serial_sequence(%s, 'id')
        """,
        (table,),
    )
    row = cur.fetchone()
    if not row or not row[0]:
        return
    seq = row[0]
    cur.execute(
        sql.SQL("SELECT setval({}, COALESCE((SELECT MAX(id) FROM {}), 1))").format(
            sql.Literal(seq), sql.Identifier(table)
        )
    )


def collect_partner_ids(src):
    cur = src.cursor()
    ids = set()
    cur.execute("SELECT partner_id FROM res_users WHERE partner_id IS NOT NULL")
    ids.update(r[0] for r in cur.fetchall())
    if table_exists(cur, "hr_employee"):
        cur.execute(
            """
            SELECT work_contact_id, address_id, user_partner_id
            FROM hr_employee
            """
        )
        for row in cur.fetchall():
            for v in row:
                if v:
                    ids.add(v)
    # Include company partners
    cur.execute("SELECT partner_id FROM res_company WHERE partner_id IS NOT NULL")
    ids.update(r[0] for r in cur.fetchall())
    # Walk parent chain
    expanded = set(ids)
    while ids:
        cur.execute(
            "SELECT parent_id FROM res_partner WHERE id = ANY(%s) AND parent_id IS NOT NULL",
            (list(ids),),
        )
        parents = {r[0] for r in cur.fetchall()} - expanded
        expanded.update(parents)
        ids = parents
    return expanded


def copy_partners(src, tgt, partner_ids):
    if not partner_ids:
        return 0
    src_cur = src.cursor()
    tgt_cur = tgt.cursor()
    table = "res_partner"
    src_cols = get_columns(src_cur, table)
    tgt_cols = get_columns(tgt_cur, table)
    cols = [c for c in src_cols if c in tgt_cols]
    col_list = sql.SQL(", ").join(map(sql.Identifier, cols))
    placeholders = sql.SQL(", ").join(sql.Placeholder() * len(cols))
    insert = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        sql.Identifier(table), col_list, placeholders
    )
    src_cur.execute(
        sql.SQL("SELECT {} FROM {} WHERE id = ANY(%s)").format(col_list, sql.Identifier(table)),
        (list(partner_ids),),
    )
    rows = src_cur.fetchall()
    tgt_cur.execute(
        sql.SQL("DELETE FROM {} WHERE id = ANY(%s)").format(sql.Identifier(table)),
        (list(partner_ids),),
    )
    for row in rows:
        tgt_cur.execute(insert, row)
    print("  res_partner: %d rows" % len(rows))
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description="Seed BetaEmployeeDB1 users/employees from BetaDB1")
    parser.add_argument("--source", default="BetaDB1")
    parser.add_argument("--target", default="BetaEmployeeDB1")
    parser.add_argument("--db-user", default="odoo17-v2")
    parser.add_argument("--db-host", default=False)
    parser.add_argument("--db-port", default=False)
    args = parser.parse_args()

    print("Connecting source=%s target=%s" % (args.source, args.target))
    src = connect(args.source, args.db_host, args.db_port, args.db_user)
    tgt = connect(args.target, args.db_host, args.db_port, args.db_user)
    src.autocommit = False
    tgt.autocommit = False

    try:
        print("Collecting partner IDs...")
        partner_ids = collect_partner_ids(src)

        print("Copying res_company...")
        tgt_cur = tgt.cursor()
        tgt_cur.execute("DELETE FROM res_company WHERE id > 0")
        copy_table(src, tgt, "res_company", delete_target=False)

        print("Copying res_partner...")
        copy_partners(src, tgt, partner_ids)

        print("Copying hr_department...")
        copy_table(src, tgt, "hr_department")

        print("Copying res_users (preserving passwords)...")
        tgt_cur.execute("DELETE FROM res_users WHERE id > 2")
        copy_table(src, tgt, "res_users", "id > 2", delete_target=False)

        print("Copying res_groups_users_rel...")
        copy_table(src, tgt, "res_groups_users_rel")

        print("Copying res_company_users_rel...")
        if table_exists(tgt.cursor(), "res_company_users_rel"):
            copy_table(src, tgt, "res_company_users_rel")

        print("Copying hr_employee...")
        copy_table(src, tgt, "hr_employee")

        print("Copying api_access_token...")
        copy_table(src, tgt, "api_access_token")

        for table in (
            "res_company",
            "res_partner",
            "res_users",
            "hr_department",
            "hr_employee",
            "api_access_token",
        ):
            reset_sequence(tgt, table)

        tgt.commit()
        print("Done. Users and employees copied from %s → %s." % (args.source, args.target))
    except Exception as e:
        tgt.rollback()
        print("ERROR: %s" % e, file=sys.stderr)
        raise
    finally:
        src.close()
        tgt.close()


if __name__ == "__main__":
    main()
