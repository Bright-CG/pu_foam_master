#!/usr/bin/env python3
"""
Full VPS scrape pipeline (fresh or resume).

Order:
  1. Customer master (CustomerInquiry / balances movement roster)
  2. Customer statements (CustomerStatementBalances.php)
  3. Supplier statements (SupplierStatementBalances.php)
  4. GL account inquiry (SelectGLAccount → GLAccountInquiry)
  5. ERPNext master CSV exports

Logs: data/logs/vps_scrape.log (shell tee) + scrape_log table.
"""

import argparse
import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from db import get_conn, init_db

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "logs")


def setup_logging():
    os.makedirs(LOG_DIR, exist_ok=True)
    log_path = os.path.join(LOG_DIR, "vps_scrape.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return log_path


def log_counts():
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT 'customers' AS k, COUNT(*) FROM customers
        UNION ALL SELECT 'customer_statement_lines', COUNT(*) FROM customer_statement_lines
        UNION ALL SELECT 'suppliers', COUNT(*) FROM suppliers
        UNION ALL SELECT 'supplier_statement_lines', COUNT(*) FROM supplier_statement_lines
        UNION ALL SELECT 'gl_inquiry_accounts_done', COUNT(*) FROM (
            SELECT account_code FROM gl_account_inquiry_periods
            GROUP BY account_code HAVING COUNT(*) >= 62
        )
        UNION ALL SELECT 'gl_account_inquiry_lines', COUNT(*) FROM gl_account_inquiry_lines
        """
    ).fetchall()
    conn.close()
    logging.info("── Row counts ──")
    for k, n in rows:
        logging.info("  %-28s %s", k, f"{n:,}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Wipe scraped tables before starting (VPS from scratch)",
    )
    parser.add_argument("--skip-customers", action="store_true")
    parser.add_argument("--skip-customer-statements", action="store_true")
    parser.add_argument("--skip-supplier-statements", action="store_true")
    parser.add_argument("--skip-gl", action="store_true")
    parser.add_argument("--skip-export", action="store_true")
    parser.add_argument(
        "--gl-no-resume",
        action="store_true",
        help="Re-scrape all GL accounts (still per-period safe unless --gl-force)",
    )
    args = parser.parse_args()

    log_path = setup_logging()
    logging.info("=" * 70)
    logging.info("HAPPIFOAM VPS SCRAPE — started %s", datetime.now().isoformat())
    logging.info("Log file: %s", os.path.abspath(log_path))

    init_db()

    if args.fresh:
        logging.info("Fresh run: clearing scraped tables")
        from reset_archive_data import SCRAPE_TABLES
        import sqlite3
        from db import DB_PATH

        conn = sqlite3.connect(DB_PATH)
        for table in SCRAPE_TABLES:
            conn.execute(f"DELETE FROM {table}")
        conn.commit()
        conn.close()

    if not args.skip_customers:
        logging.info("Phase 1: customer master")
        from scrape_customers import scrape_customers

        scrape_customers()

    if not args.skip_customer_statements:
        logging.info("Phase 2: customer statements")
        from scrape_customer_statements import scrape_customer_statements

        scrape_customer_statements()

    if not args.skip_supplier_statements:
        logging.info("Phase 3: supplier statements")
        from scrape_supplier_statements import scrape_supplier_statements

        scrape_supplier_statements()

    if not args.skip_gl:
        logging.info("Phase 4: GL account inquiry")
        from scrape_gl_account_inquiry import scrape_gl_account_inquiry

        scrape_gl_account_inquiry(workers=1, resume=not args.gl_no_resume, force=False)

    if not args.skip_export:
        logging.info("Phase 5: ERPNext master exports")
        from export_master_data import main as export_main

        export_main()

    log_counts()
    logging.info("Finished %s", datetime.now().isoformat())
    logging.info("=" * 70)


if __name__ == "__main__":
    main()
