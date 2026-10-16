"""
Re-scrape customers that were saved with 0 transactions due to FormID / session errors.

Usage:
  cd legacy_erp_archive/scraper
  python rescue_customers.py              # all failed (logged as 0 transactions)
  python rescue_customers.py 448 447      # specific customer IDs
"""

import argparse
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from db import DB_PATH, init_db
from login import get_session
from scrape_customers import scrape_one_customer, scrape_customers


def failed_customer_ids(conn):
    """Customers with no rows in customer_transactions (includes FormID false zeros)."""
    rows = conn.execute(
        """
        SELECT c.id
        FROM customers c
        LEFT JOIN (
            SELECT customer_id, COUNT(*) AS cnt
            FROM customer_transactions
            GROUP BY customer_id
        ) t ON t.customer_id = c.id
        WHERE COALESCE(t.cnt, 0) = 0
        ORDER BY c.id
        """
    ).fetchall()
    return [r[0] for r in rows]


def main():
    parser = argparse.ArgumentParser(description="Rescue customer ledger scrapes")
    parser.add_argument(
        "customer_ids",
        nargs="*",
        help="Optional customer IDs (default: all logged with 0 transactions)",
    )
    args = parser.parse_args()

    init_db()
    conn = sqlite3.connect(DB_PATH)

    if args.customer_ids:
        ids = args.customer_ids
        print(f"Rescuing {len(ids)} specified customer(s) ...")
        session = get_session()
        ok = 0
        for cust_id in ids:
            name = conn.execute(
                "SELECT name FROM customers WHERE id = ?", (cust_id,)
            ).fetchone()
            label = name[0] if name else cust_id
            try:
                n = scrape_one_customer(session, conn, cust_id, label)
                print(f"  {cust_id}: {n} transactions")
                ok += 1
            except Exception as e:
                print(f"  {cust_id}: FAILED — {e}")
        print(f"Done. {ok}/{len(ids)} succeeded.")
        conn.close()
        return

    ids = failed_customer_ids(conn)
    conn.close()
    if not ids:
        print("No customers flagged with 0 transactions in scrape_log.")
        return

    print(f"Rescuing {len(ids)} customers previously stored with 0 transactions ...")
    scrape_customers(customer_filter=ids)


if __name__ == "__main__":
    main()
