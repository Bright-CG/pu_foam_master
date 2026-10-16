"""
db.py — SQLite database schema and helpers for the Happifoam Legacy ERP Archive.
All scraped data is written here and the Laravel app reads from it.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "happifoam.db")


def get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create all tables if they don't exist."""
    conn = get_conn()
    c = conn.cursor()

    # ── CUSTOMERS ─────────────────────────────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id            TEXT PRIMARY KEY,    -- e.g. "001", "692", "REBATE304"
        name          TEXT NOT NULL,
        phone         TEXT,
        address       TEXT,
        area          TEXT,
        cust_type     TEXT,
        credit_limit  TEXT,
        credit_status TEXT,
        currency      TEXT DEFAULT 'NGN',
        terms         TEXT,
        balance_total TEXT DEFAULT '0.00',
        bal_current   TEXT DEFAULT '0.00',
        bal_now_due   TEXT DEFAULT '0.00',
        bal_30_60     TEXT DEFAULT '0.00',
        bal_over_60   TEXT DEFAULT '0.00',
        scraped_at    DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS customer_transactions (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id     TEXT NOT NULL REFERENCES customers(id),
        trans_type      TEXT,           -- Invoice, Receipt, Credit Note, etc.
        trans_no        TEXT,
        trans_date      DATE,
        branch          TEXT,
        reference       TEXT,
        comments        TEXT,
        order_no        TEXT,
        total           TEXT,
        allocated       TEXT,
        balance         TEXT,
        scraped_at      DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")

    # CustomerStatementBalances.php — debit/credit + running balance (kept separate from inquiry scrape)
    c.execute("""
    CREATE TABLE IF NOT EXISTS customer_statement_lines (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id     TEXT NOT NULL,
        line_no         TEXT,
        trans_type      TEXT,
        trans_no        TEXT,
        narration       TEXT,
        trans_date      DATE,
        reference       TEXT,
        debit           TEXT,
        credit          TEXT,
        balance         TEXT,
        report_from_date TEXT,
        report_to_date   TEXT,
        scraped_at      DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""
    CREATE INDEX IF NOT EXISTS idx_customer_statement_lines_cust_date
    ON customer_statement_lines (customer_id, trans_date, line_no)
    """)

    # SupplierStatementBalances.php — debit/credit + running balance
    c.execute("""
    CREATE TABLE IF NOT EXISTS supplier_statement_lines (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_id     TEXT NOT NULL,
        line_no         TEXT,
        trans_type      TEXT,
        trans_no        TEXT,
        narration       TEXT,
        trans_date      DATE,
        reference       TEXT,
        debit           TEXT,
        credit          TEXT,
        balance         TEXT,
        report_from_date TEXT,
        report_to_date   TEXT,
        scraped_at      DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""
    CREATE INDEX IF NOT EXISTS idx_supplier_statement_lines_supp_date
    ON supplier_statement_lines (supplier_id, trans_date, line_no)
    """)

    # ── SUPPLIERS ─────────────────────────────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS suppliers (
        id            TEXT PRIMARY KEY,
        name          TEXT NOT NULL,
        phone         TEXT,
        address       TEXT,
        currency      TEXT DEFAULT 'NGN',
        terms         TEXT,
        balance_total TEXT DEFAULT '0.00',
        scraped_at    DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS supplier_transactions (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_id     TEXT NOT NULL REFERENCES suppliers(id),
        trans_type      TEXT,
        trans_no        TEXT,
        trans_date      DATE,
        reference       TEXT,
        comments        TEXT,
        total           TEXT,
        allocated       TEXT,
        balance         TEXT,
        scraped_at      DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")

    # ── GENERAL LEDGER ────────────────────────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS gl_accounts (
        account_code  TEXT PRIMARY KEY,
        account_name  TEXT NOT NULL,
        account_type  TEXT,
        account_group TEXT,
        section       TEXT,
        balance       TEXT DEFAULT '0.00',
        scraped_at    DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS gl_transactions (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        account_code    TEXT REFERENCES gl_accounts(account_code),
        trans_date      DATE,
        trans_no        TEXT,
        trans_type      TEXT,
        narrative       TEXT,
        debit           TEXT DEFAULT '0.00',
        credit          TEXT DEFAULT '0.00',
        balance         TEXT DEFAULT '0.00',
        scraped_at      DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")

    # SelectGLAccount.php → GLAccountInquiry.php (per account, per period)
    c.execute("""
    CREATE TABLE IF NOT EXISTS gl_account_inquiry_lines (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        account_code    TEXT NOT NULL,
        period_id       TEXT,
        period_label    TEXT,
        trans_type      TEXT,
        trans_no        TEXT,
        trans_date      DATE,
        narrative       TEXT,
        debit           TEXT,
        credit          TEXT,
        balance         TEXT,
        tag             TEXT,
        scraped_at      DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""
    CREATE INDEX IF NOT EXISTS idx_gl_inquiry_acct_date
    ON gl_account_inquiry_lines (account_code, trans_date, trans_no)
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS gl_account_inquiry_periods (
        account_code    TEXT NOT NULL,
        period_id       TEXT NOT NULL,
        period_label    TEXT,
        line_count      INTEGER DEFAULT 0,
        scraped_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (account_code, period_id)
    )
    """)

    # ── INVENTORY ─────────────────────────────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS stock_items (
        item_code     TEXT PRIMARY KEY,
        description   TEXT NOT NULL,
        uom           TEXT,
        category      TEXT,
        stock_qty     TEXT DEFAULT '0',
        unit_cost     TEXT DEFAULT '0.00',
        scraped_at    DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")

    # ── SCRAPE LOG ────────────────────────────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS scrape_log (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        module      TEXT NOT NULL,
        entity_id   TEXT,
        status      TEXT,
        message     TEXT,
        scraped_at  DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")

    conn.commit()
    conn.close()
    print("  [DB] Database initialized:", DB_PATH)


if __name__ == "__main__":
    init_db()
