#!/usr/bin/env python3
"""
Re-fetch all archive data with validated sessions (post network / FormID issues).

Order:
  1. Customers with 0 transactions in scrape_log (or all if --customers-all)
  2. Suppliers (full re-list + ledgers)
  3. General Ledger
  4. Inventory
"""

import argparse
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from db import get_conn, init_db


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--customers-all",
        action="store_true",
        help="Re-scrape every customer (not only failed zeros)",
    )
    parser.add_argument("--skip-customers", action="store_true")
    parser.add_argument("--skip-suppliers", action="store_true")
    parser.add_argument("--skip-gl", action="store_true")
    parser.add_argument("--skip-inventory", action="store_true")
    parser.add_argument(
        "--customer-statements",
        action="store_true",
        help="Scrape CustomerStatementBalances.php (debit/credit/running balance)",
    )
    parser.add_argument("--skip-customer-statements", action="store_true")
    args = parser.parse_args()

    print("=" * 70)
    print("  HAPPIFOAM LEGACY ERP — FULL DATA RESCUE")
    print(f"  Started: {datetime.now():%Y-%m-%d %H:%M:%S}")
    print("=" * 70)

    init_db()
    log_path = os.path.join(os.path.dirname(__file__), "..", "data", "rescue_run.log")
    print(f"  Log file: {os.path.abspath(log_path)}")

    if not args.skip_customers:
        print("\n── CUSTOMERS ──")
        if args.customers_all:
            from scrape_customers import scrape_customers

            scrape_customers()
        else:
            from rescue_customers import failed_customer_ids
            from scrape_customers import scrape_customers

            conn = get_conn()
            ids = failed_customer_ids(conn)
            conn.close()
            print(f"  Rescuing {len(ids)} customers previously stored with 0 transactions")
            scrape_customers(customer_filter=ids)

    if args.customer_statements and not args.skip_customer_statements:
        print("\n── CUSTOMER STATEMENTS (CustomerStatementBalances.php) ──")
        from scrape_customer_statements import scrape_customer_statements

        scrape_customer_statements()

    if not args.skip_suppliers:
        print("\n── SUPPLIERS ──")
        from scrape_suppliers import scrape_suppliers

        scrape_suppliers()

    if not args.skip_gl:
        print("\n── GENERAL LEDGER ──")
        from scrape_gl import scrape_gl

        scrape_gl()

    if not args.skip_inventory:
        print("\n── INVENTORY ──")
        from scrape_inventory import scrape_inventory

        scrape_inventory()

    conn = get_conn()
    summary = conn.execute(
        """
        SELECT 'customers' AS k, COUNT(*) FROM customers
        UNION ALL SELECT 'customer_transactions', COUNT(*) FROM customer_transactions
        UNION ALL SELECT 'customer_statement_lines', COUNT(*) FROM customer_statement_lines
        UNION ALL SELECT 'suppliers', COUNT(*) FROM suppliers
        UNION ALL SELECT 'supplier_transactions', COUNT(*) FROM supplier_transactions
        UNION ALL SELECT 'gl_accounts', COUNT(*) FROM gl_accounts
        UNION ALL SELECT 'gl_transactions', COUNT(*) FROM gl_transactions
        UNION ALL SELECT 'stock_items', COUNT(*) FROM stock_items
        """
    ).fetchall()
    conn.close()

    print("\n" + "=" * 70)
    print("  FINAL COUNTS")
    for k, n in summary:
        print(f"  {k:24s} {n:>10,}")
    print(f"  Finished: {datetime.now():%Y-%m-%d %H:%M:%S}")
    print("=" * 70)


if __name__ == "__main__":
    main()
