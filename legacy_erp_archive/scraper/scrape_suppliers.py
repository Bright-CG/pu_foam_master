"""
scrape_suppliers.py — Extracts all supplier accounts, balances, and transactions
from 18-Oct-2021 (the cutover date) onwards.

Strategy:
  1. Fetch index.php?Application=AP to discover all supplier-related inquiry pages.
  2. Use SupplierBalancesMovement.php or SupplierInquiry.php to get the full list.
  3. Iterate each supplier, POST with the cutover date, parse transactions.
  4. Write to SQLite + per-supplier CSV backup.
"""

import re
import os
import csv
import time
import json

from login import get_session, CUTOVER_DATE
from db import get_conn, init_db
from inquiry_fetch import fetch_supplier_inquiry

REQUEST_DELAY = 0.12

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
SUPP_DIR = os.path.join(DATA_DIR, "suppliers")


def clean(text):
    text = re.sub(r"<[^>]+>", "", str(text))
    return re.sub(r"\s+", " ", text).strip()


def extract_all_suppliers(html):
    """
    Pull (supplier_id, name) from <select name="SupplierID"> on SupplierTransInquiry.php
    (same pattern as Customer on CustomerBalancesMovement.php).
    """
    block = html
    m = re.search(
        r'<select[^>]*name=["\']SupplierID["\'][^>]*>(.*?)</select>',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    if m:
        block = m.group(1)

    opts = re.findall(
        r'<option[^>]*value=["\']([^"\']+)["\'][^>]*>(.*?)</option>',
        block,
        re.DOTALL,
    )
    skip_vals = {
        "",
        "all",
        "0",
        "overduesonly",
        "aud",
        "chf",
        "eur",
        "gbp",
        "kes",
        "ngn",
        "usd",
        "yes",
        "no",
    }
    suppliers = []
    seen = set()
    for val, label in opts:
        val = val.strip()
        label = clean(label)
        if not val or val.lower() in skip_vals or label.lower() == "all":
            continue
        if any(
            x in label.lower()
            for x in ("purchase invoice", "debit note", "creditors payment", "creditors journal")
        ):
            continue
        if val in seen:
            continue
        seen.add(val)
        suppliers.append((val, label))
    return suppliers


def load_supplier_master_list(session):
    """Primary source: SupplierStatementBalances.php (full SupplierID roster)."""
    html = session.get("/SupplierStatementBalances.php")
    suppliers = extract_all_suppliers(html)
    if suppliers:
        return suppliers

    # Fallback: keyword sweep on SelectSupplier (partial code/name required on this tenant)
    found = {}
    for token in list("0123456789") + [chr(c) for c in range(ord("A"), ord("Z") + 1)]:
        page = session.get("/SelectSupplier.php")
        form_id = session.get_form_id(page)
        res = session.post(
            "/SelectSupplier.php",
            {
                "FormID": form_id,
                "Keywords": token,
                "SupplierCode": "",
                "Search": "Search Now",
            },
        )
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", res, re.DOTALL):
            tds = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
            if len(tds) < 2:
                continue
            code, name = clean(tds[0]), clean(tds[1])
            if re.match(r"^[A-Z0-9][A-Z0-9\-]{0,18}$", code) and name:
                found[code] = name
    return sorted(found.items(), key=lambda x: x[0])


def extract_balances(html):
    """Parse supplier balance row."""
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
    for row in rows:
        tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        if len(tds) >= 3:
            vals = [clean(td) for td in tds[:5]]
            if any(re.match(r'^-?[\d,]+\.?\d*$', v) for v in vals):
                return vals
    return ["0.00", "0.00", "0.00", "0.00", "0.00"]


def extract_transactions(html):
    """Parse supplier transaction table (Date | Type | Number | ... on this ERP)."""
    transactions = []
    known_types = [
        "purchase invoice",
        "invoice",
        "payment",
        "debit note",
        "credit note",
        "journal",
        "opening balance",
        "purchase",
        "bill",
        "creditors",
    ]
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL)
    for row in rows:
        tds = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
        if len(tds) < 5:
            continue
        vals = [clean(td) for td in tds]

        if re.match(r"^\d{4}-\d{2}-\d{2}$", vals[0]):
            trans_date, trans_type, trans_no = vals[0], vals[1], vals[2]
            reference = vals[3] if len(vals) > 3 else ""
            comments = vals[4] if len(vals) > 4 else ""
            total = vals[5] if len(vals) > 5 else ""
            allocated = vals[6] if len(vals) > 6 else ""
            balance = vals[7] if len(vals) > 7 else ""
        else:
            trans_type = vals[0].strip()
            trans_no = vals[1] if len(vals) > 1 else ""
            trans_date = vals[2] if len(vals) > 2 else ""
            reference = vals[3] if len(vals) > 3 else ""
            comments = vals[4] if len(vals) > 4 else ""
            total = vals[5] if len(vals) > 5 else ""
            allocated = vals[6] if len(vals) > 6 else ""
            balance = vals[7] if len(vals) > 7 else ""

        if not trans_type or not any(t in trans_type.lower() for t in known_types):
            continue

        transactions.append(
            {
                "trans_type": trans_type,
                "trans_no": trans_no,
                "trans_date": trans_date,
                "reference": reference,
                "comments": comments,
                "total": total,
                "allocated": allocated,
                "balance": balance,
            }
        )
    return transactions


def extract_supplier_meta(html):
    """Extract supplier name and terms from page title area."""
    meta = {"name": "", "currency": "NGN", "terms": ""}
    m = re.search(r'Supplier:\s*\S+\s*-\s*(.+?)<br', html, re.DOTALL)
    if m:
        meta["name"] = clean(m.group(1))
    m2 = re.search(r'Terms:\s*(.*?)<br', html)
    if m2:
        meta["terms"] = clean(m2.group(1))
    return meta


def scrape_suppliers():
    print("\n" + "=" * 60)
    print("  SUPPLIER LEDGER SCRAPER")
    print(f"  Cutover date: {CUTOVER_DATE}")
    print("=" * 60)

    os.makedirs(SUPP_DIR, exist_ok=True)
    init_db()

    session = get_session()
    conn = get_conn()

    # ── Step 1: Get complete supplier list ─────────────────────────────────
    print("\n[1/3] Fetching supplier list ...")

    try:
        all_suppliers = load_supplier_master_list(session)
        print(f"  Supplier master list: {len(all_suppliers)} suppliers")
    except Exception as e:
        all_suppliers = []
        print(f"  Supplier list failed: {e}")

    if not all_suppliers:
        print("  ⚠ Could not retrieve supplier list. Skipping suppliers module.")
        conn.close()
        return

    # Save master list
    with open(os.path.join(SUPP_DIR, "_supplier_list.json"), "w") as f:
        json.dump(all_suppliers, f, indent=2)

    # ── Step 2: Iterate each supplier ─────────────────────────────────────
    print(f"\n[2/3] Fetching individual supplier ledgers from {CUTOVER_DATE} ...")
    total = len(all_suppliers)
    success_count = 0
    error_count = 0

    for idx, (supp_id, supp_name) in enumerate(all_suppliers, 1):
        supp_id = str(supp_id).strip()
        supp_name = clean(supp_name)
        prefix = f"  [{idx:04d}/{total}] {supp_id} — {supp_name[:40]:<40}"
        try:
            result_html = fetch_supplier_inquiry(session, supp_id)

            balances = extract_balances(result_html)
            meta = extract_supplier_meta(result_html)
            if not meta["name"]:
                meta["name"] = supp_name

            transactions = extract_transactions(result_html)

            conn.execute("""
                INSERT OR REPLACE INTO suppliers
                  (id, name, currency, terms, balance_total)
                VALUES (?, ?, ?, ?, ?)
            """, (supp_id, meta["name"], meta["currency"], meta["terms"], balances[0]))

            conn.execute("DELETE FROM supplier_transactions WHERE supplier_id = ?", (supp_id,))

            for tx in transactions:
                conn.execute("""
                    INSERT INTO supplier_transactions
                      (supplier_id, trans_type, trans_no, trans_date,
                       reference, comments, total, allocated, balance)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    supp_id, tx["trans_type"], tx["trans_no"], tx["trans_date"],
                    tx["reference"], tx["comments"], tx["total"], tx["allocated"], tx["balance"],
                ))

            conn.commit()

            safe_id = re.sub(r'[^a-zA-Z0-9_-]', '_', supp_id)
            csv_path = os.path.join(SUPP_DIR, f"{safe_id}.csv")
            with open(csv_path, "w", newline="", encoding="utf-8") as cf:
                writer = csv.DictWriter(cf, fieldnames=[
                    "trans_type", "trans_no", "trans_date", "reference",
                    "comments", "total", "allocated", "balance"
                ])
                writer.writeheader()
                writer.writerows(transactions)

            conn.execute("""
                INSERT INTO scrape_log (module, entity_id, status, message)
                VALUES ('suppliers', ?, 'ok', ?)
            """, (supp_id, f"{len(transactions)} transactions"))
            conn.commit()

            print(f"{prefix} ✓ {len(transactions):>4} transactions")
            success_count += 1

        except Exception as e:
            error_count += 1
            print(f"{prefix} ✗ ERROR: {e}")
            conn.execute("""
                INSERT INTO scrape_log (module, entity_id, status, message)
                VALUES ('suppliers', ?, 'error', ?)
            """, (supp_id, str(e)))
            conn.commit()
            time.sleep(1)

        time.sleep(REQUEST_DELAY)

    conn.close()

    print(f"\n[3/3] Supplier scrape complete!")
    print(f"  ✓ Success : {success_count}")
    print(f"  ✗ Errors  : {error_count}")


if __name__ == "__main__":
    scrape_suppliers()
