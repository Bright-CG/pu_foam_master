#!/usr/bin/env python3
"""Clear scraped archive tables for a fresh VPS run (keeps schema)."""

import argparse
import os
import sqlite3

from db import DB_PATH, init_db

SCRAPE_TABLES = [
    "customer_transactions",
    "customer_statement_lines",
    "customers",
    "supplier_transactions",
    "supplier_statement_lines",
    "suppliers",
    "gl_account_inquiry_lines",
    "gl_account_inquiry_periods",
    "gl_transactions",
    "gl_accounts",
    "stock_items",
    "scrape_log",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required — deletes all scraped rows",
    )
    args = parser.parse_args()
    if not args.confirm:
        print("Refusing to run without --confirm")
        raise SystemExit(1)

    init_db()
    conn = sqlite3.connect(DB_PATH)
    for table in SCRAPE_TABLES:
        conn.execute(f"DELETE FROM {table}")
    conn.commit()
    conn.execute("VACUUM")
    conn.close()

    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    print("Cleared tables:", ", ".join(SCRAPE_TABLES))
    print("Database:", os.path.abspath(DB_PATH))
    print(
        "Optional: remove CSV backups under data/customers, data/customer_statements,"
        " data/supplier_statements, data/suppliers, data/gl_inquiry manually."
    )


if __name__ == "__main__":
    main()
