"""
run_all.py — Master runner for the Happifoam Legacy ERP Archive scraper.

Usage:
    cd legacy_erp_archive/scraper
    pip install -r requirements.txt
    python run_all.py

This will:
  1. Login to the ERP
  2. Scrape all customers
  3. Scrape all suppliers
  4. Scrape the General Ledger (Chart of Accounts, Trial Balance, Journals)
  5. Scrape inventory / stock items
  6. Print a summary report
"""

import os
import sys
import time
from datetime import datetime

print("=" * 65)
print("  HAPPIFOAM LEGACY ERP ARCHIVE — MASTER RUNNER")
print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 65)

# Add scraper dir to path so all imports work
sys.path.insert(0, os.path.dirname(__file__))

from db import init_db, get_conn

# Initialize DB first
print("\n🔧  Initializing SQLite database ...")
init_db()

# ── 1. Customers ────────────────────────────────────────────────────────────
print("\n" + "─" * 65)
print("  MODULE 1/4: CUSTOMERS")
print("─" * 65)
try:
    from scrape_customers import scrape_customers
    scrape_customers()
except Exception as e:
    print(f"  ✗ Customers module failed: {e}")

# ── 2. Suppliers ────────────────────────────────────────────────────────────
print("\n" + "─" * 65)
print("  MODULE 2/4: SUPPLIERS")
print("─" * 65)
try:
    from scrape_suppliers import scrape_suppliers
    scrape_suppliers()
except Exception as e:
    print(f"  ✗ Suppliers module failed: {e}")

# ── 3. General Ledger ───────────────────────────────────────────────────────
print("\n" + "─" * 65)
print("  MODULE 3/4: GENERAL LEDGER")
print("─" * 65)
try:
    from scrape_gl import scrape_gl
    scrape_gl()
except Exception as e:
    print(f"  ✗ General Ledger module failed: {e}")

# ── 4. Inventory ────────────────────────────────────────────────────────────
print("\n" + "─" * 65)
print("  MODULE 4/4: INVENTORY")
print("─" * 65)
try:
    from scrape_inventory import scrape_inventory
    scrape_inventory()
except Exception as e:
    print(f"  ✗ Inventory module failed: {e}")

# ── Summary ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 65)
print("  SCRAPE SUMMARY")
print("=" * 65)
try:
    conn = get_conn()
    c_count = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    ct_count = conn.execute("SELECT COUNT(*) FROM customer_transactions").fetchone()[0]
    s_count = conn.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0]
    st_count = conn.execute("SELECT COUNT(*) FROM supplier_transactions").fetchone()[0]
    gl_count = conn.execute("SELECT COUNT(*) FROM gl_accounts").fetchone()[0]
    glt_count = conn.execute("SELECT COUNT(*) FROM gl_transactions").fetchone()[0]
    inv_count = conn.execute("SELECT COUNT(*) FROM stock_items").fetchone()[0]
    err_count = conn.execute("SELECT COUNT(*) FROM scrape_log WHERE status='error'").fetchone()[0]
    conn.close()

    print(f"  Customers       : {c_count:>6,}   ({ct_count:>8,} transactions)")
    print(f"  Suppliers       : {s_count:>6,}   ({st_count:>8,} transactions)")
    print(f"  GL Accounts     : {gl_count:>6,}   ({glt_count:>8,} journal lines)")
    print(f"  Stock Items     : {inv_count:>6,}")
    print(f"  Errors logged   : {err_count:>6,}")
    print(f"\n  Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)
    print("\n✅  Scrape complete! The data is in: legacy_erp_archive/data/happifoam.db")
    print("   You can now set up the Laravel archive viewer.\n")
except Exception as e:
    print(f"  Summary query failed: {e}")
