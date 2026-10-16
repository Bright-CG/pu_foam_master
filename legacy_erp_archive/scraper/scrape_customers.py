"""
scrape_customers.py — Extracts all customer accounts, balances, and every
transaction from 18-Oct-2021 (the cutover date) onwards.

Strategy:
  1. Load CustomerBalancesMovement.php to get the complete dropdown list of
     all customer IDs and names (includes both standard and REBATE accounts).
  2. For each customer, open CustomerInquiry.php?CustomerID=<id> and then
     POST with TransAfterDate=2021-10-18 to get all transactions.
  3. Parse the summary table (balances) and the transaction table.
  4. Write everything to SQLite + per-customer CSV backup.
"""

import re
import os
import csv
import time
import json
from datetime import datetime

from login import get_session, CUTOVER_DATE
from db import get_conn, init_db
from inquiry_fetch import fetch_customer_inquiry

REQUEST_DELAY = 0.12  # keep-alive session; safe without hammering ERP

# Output directories
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
CUST_DIR = os.path.join(DATA_DIR, "customers")


def clean(text):
    """Strip HTML tags and normalise whitespace."""
    text = re.sub(r"<[^>]+>", "", str(text))
    return re.sub(r"\s+", " ", text).strip()


def parse_td(td_html):
    return clean(td_html)


def extract_all_customers(html):
    """
    Pull (customer_id, customer_name) from the <select name="Customer"> dropdown
    on CustomerBalancesMovement.php — the most complete customer roster.
    """
    opts = re.findall(
        r'<option[^>]*value=[\"\']([^\"\']+)[\"\'][^>]*>(.*?)</option>',
        html, re.DOTALL
    )
    customers = []
    for val, label in opts:
        val = val.strip()
        label = clean(label)
        if val and val != "All" and label:
            customers.append((val, label))
    return customers


def extract_balances(html):
    """Parse the aging summary table (Total, Current, Now Due, 30-60, Over 60)."""
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
    # The first data row after the header row contains the 5 balance columns
    for row in rows:
        tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        if len(tds) >= 5:
            vals = [clean(td) for td in tds[:5]]
            # Check if these look like numbers
            if any(re.match(r'^-?[\d,]+\.?\d*$', v) for v in vals):
                return vals  # [total, current, now_due, 30_60, over_60]
    return ["0.00", "0.00", "0.00", "0.00", "0.00"]


def extract_transactions(html):
    """
    Parse the transaction table from CustomerInquiry.php.
    Columns: Type | Number | Date | Branch | Reference | Comments | Order | Total | Allocated | Balance
    """
    transactions = []
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)

    for row in rows:
        tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        if len(tds) < 6:
            continue
        vals = [clean(td) for td in tds]
        # Skip header rows or empty rows
        trans_type = vals[0].strip()
        if not trans_type or trans_type.lower() in ["type", "trans type", ""]:
            continue
        # Must look like a real transaction type
        known_types = [
            "sales invoice",
            "invoice",
            "receipt",
            "credit note",
            "debit note",
            "payment",
            "journal",
            "opening balance",
            "write off",
        ]
        if not any(t in trans_type.lower() for t in known_types):
            continue

        trans_no = vals[1] if len(vals) > 1 else ""
        trans_date = vals[2] if len(vals) > 2 else ""
        branch = vals[3] if len(vals) > 3 else ""
        reference = vals[4] if len(vals) > 4 else ""
        comments = vals[5] if len(vals) > 5 else ""
        order_no = vals[6] if len(vals) > 6 else ""
        total = vals[7] if len(vals) > 7 else ""
        allocated = vals[8] if len(vals) > 8 else ""
        balance = vals[9] if len(vals) > 9 else ""

        transactions.append({
            "trans_type": trans_type,
            "trans_no": trans_no,
            "trans_date": trans_date,
            "branch": branch,
            "reference": reference,
            "comments": comments,
            "order_no": order_no,
            "total": total,
            "allocated": allocated,
            "balance": balance,
        })
    return transactions


def extract_customer_meta(html):
    """
    Extract customer name, terms, credit limit, and credit status from
    the page_title_text section of CustomerInquiry.php.
    """
    meta = {"name": "", "currency": "Nigerian naira", "terms": "",
            "credit_limit": "", "credit_status": ""}
    m = re.search(r'Customer:\s*\S+\s*-\s*(.+?)<br', html, re.DOTALL)
    if m:
        meta["name"] = clean(m.group(1))
    m2 = re.search(r'Terms:\s*(.*?)<br', html)
    if m2:
        meta["terms"] = clean(m2.group(1))
    m3 = re.search(r'Credit Limit:\s*([\d,]+)', html)
    if m3:
        meta["credit_limit"] = m3.group(1)
    m4 = re.search(r'Credit Status:\s*(.*?)\n', html)
    if m4:
        meta["credit_status"] = clean(m4.group(1))
    return meta


def save_customer_ledger(conn, cust_id, cust_name, meta, balances, transactions):
    """Persist one customer only after a validated inquiry page was parsed."""
    conn.execute(
        """
        INSERT OR REPLACE INTO customers
          (id, name, currency, terms, credit_limit, credit_status,
           balance_total, bal_current, bal_now_due, bal_30_60, bal_over_60)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            cust_id,
            meta["name"],
            meta["currency"],
            meta["terms"],
            meta["credit_limit"],
            meta["credit_status"],
            balances[0],
            balances[1],
            balances[2],
            balances[3],
            balances[4],
        ),
    )

    conn.execute("DELETE FROM customer_transactions WHERE customer_id = ?", (cust_id,))

    for tx in transactions:
        conn.execute(
            """
            INSERT INTO customer_transactions
              (customer_id, trans_type, trans_no, trans_date, branch,
               reference, comments, order_no, total, allocated, balance)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                cust_id,
                tx["trans_type"],
                tx["trans_no"],
                tx["trans_date"],
                tx["branch"],
                tx["reference"],
                tx["comments"],
                tx["order_no"],
                tx["total"],
                tx["allocated"],
                tx["balance"],
            ),
        )

    conn.commit()

    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", cust_id)
    csv_path = os.path.join(CUST_DIR, f"{safe_id}.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as cf:
        writer = csv.DictWriter(
            cf,
            fieldnames=[
                "trans_type",
                "trans_no",
                "trans_date",
                "branch",
                "reference",
                "comments",
                "order_no",
                "total",
                "allocated",
                "balance",
            ],
        )
        writer.writeheader()
        writer.writerows(transactions)


def scrape_one_customer(session, conn, cust_id, cust_name):
    result_html = fetch_customer_inquiry(session, cust_id)
    balances = extract_balances(result_html)
    meta = extract_customer_meta(result_html)
    if not meta["name"]:
        meta["name"] = cust_name
    transactions = extract_transactions(result_html)
    save_customer_ledger(conn, cust_id, cust_name, meta, balances, transactions)
    return len(transactions)


def scrape_customers(customer_filter=None):
    """Main scraper entry point for the customers module."""
    print("\n" + "=" * 60)
    print("  CUSTOMER LEDGER SCRAPER")
    print(f"  Cutover date: {CUTOVER_DATE}")
    print("=" * 60)

    os.makedirs(CUST_DIR, exist_ok=True)
    init_db()

    session = get_session()
    conn = get_conn()

    # ── Step 1: Get complete customer list ─────────────────────────────────
    print("\n[1/3] Fetching complete customer list from CustomerBalancesMovement.php ...")
    cbm_html = session.get("/CustomerBalancesMovement.php")
    all_customers = extract_all_customers(cbm_html)
    print(f"  Found {len(all_customers)} customer entries (including REBATE accounts)")

    # Save master customer list
    with open(os.path.join(DATA_DIR, "customers", "_customer_list.json"), "w") as f:
        json.dump(all_customers, f, indent=2)

    # ── Step 2: Iterate and scrape each customer ───────────────────────────
    print(f"\n[2/3] Fetching individual customer ledgers from {CUTOVER_DATE} ...")
    total = len(all_customers)
    success_count = 0
    error_count = 0

    if customer_filter:
        wanted = set(customer_filter)
        all_customers = [(cid, name) for cid, name in all_customers if cid in wanted]
        total = len(all_customers)
        print(f"  Filtered to {total} customer(s)")

    for idx, (cust_id, cust_name) in enumerate(all_customers, 1):
        prefix = f"  [{idx:04d}/{total}] {cust_id} — {cust_name[:40]:<40}"
        try:
            tx_count = scrape_one_customer(session, conn, cust_id, cust_name)

            conn.execute(
                """
                INSERT INTO scrape_log (module, entity_id, status, message)
                VALUES ('customers', ?, 'ok', ?)
            """,
                (cust_id, f"{tx_count} transactions"),
            )
            conn.commit()

            print(f"{prefix} ✓ {tx_count:>4} transactions")
            success_count += 1

        except Exception as e:
            error_count += 1
            print(f"{prefix} ✗ ERROR: {e}")
            conn.execute("""
                INSERT INTO scrape_log (module, entity_id, status, message)
                VALUES ('customers', ?, 'error', ?)
            """, (cust_id, str(e)))
            conn.commit()
            time.sleep(1)

        # Polite delay to avoid hammering the server
        time.sleep(REQUEST_DELAY)

    conn.close()

    print(f"\n[3/3] Customer scrape complete!")
    print(f"  ✓ Success : {success_count}")
    print(f"  ✗ Errors  : {error_count}")
    print(f"  DB path   : {os.path.abspath(os.path.join(DATA_DIR, 'happifoam.db'))}")


if __name__ == "__main__":
    scrape_customers()
