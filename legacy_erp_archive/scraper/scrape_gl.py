"""
scrape_gl.py — Extracts the full General Ledger from the old ERP.

Fetches:
  1. Chart of Accounts (all GL account codes and names) via GLAccounts.php
  2. GL Account detail report (GLAccountReport.php) for each account
  3. Trial Balance (GLTrialBalance.php) for the period from cutover to today
  4. Journal entries (GLJournalInquiry.php) for the full period
"""

import re
import os
import csv
import json
import time

from login import get_session, CUTOVER_DATE
from db import get_conn, init_db
from form_post import safe_post
from erp_html import is_form_verification_error, is_login_page

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
GL_DIR = os.path.join(DATA_DIR, "gl")

# Happifoam webERP — GLJournalInquiry.php transaction type dropdown values
JOURNAL_TRANS_TYPES = {
    "0": "Journal - GL",
    "1": "Payment - GL",
    "2": "Receipt - GL",
    "10": "Sales Invoice",
    "11": "Credit Note",
    "12": "Receipt",
    "20": "Purchase Invoice",
    "21": "Debit Note",
    "22": "Creditors Payment",
    "25": "Purchase Order Delivery",
}

# Trial balance uses accounting periods; Oct 2021 (cutover) ≈ period 12 on this tenant
TB_PERIOD_FROM_CUTOVER = "12"
TB_PERIOD_TO_LATEST = "73"


def clean(text):
    text = re.sub(r"<[^>]+>", "", str(text))
    return re.sub(r"\s+", " ", text).strip()


def amount_to_debit_credit(amount_str):
    """Journal inquiry shows a single signed amount column."""
    raw = (amount_str or "").replace(",", "").strip()
    if not raw or raw == "-":
        return "0.00", "0.00"
    try:
        value = float(raw)
    except ValueError:
        return raw, "0.00"
    if value < 0:
        return "0.00", f"{abs(value):.2f}"
    return f"{value:.2f}", "0.00"


def parse_journal_rows(html):
    """Rows: Date | No | Account | Name | Narrative | Amount | Branch | Print."""
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL)
    parsed = []
    for row in rows:
        tds = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
        if len(tds) < 6:
            continue
        vals = [clean(td) for td in tds]
        if not re.match(r"\d{4}-\d{2}-\d{2}", vals[0]):
            continue
        debit, credit = amount_to_debit_credit(vals[5] if len(vals) > 5 else "")
        parsed.append({
            "trans_date": vals[0],
            "trans_no": vals[1],
            "account_code": vals[2],
            "narrative": vals[4] if len(vals) > 4 else "",
            "debit": debit,
            "credit": credit,
        })
    return parsed


def scrape_gl():
    print("\n" + "=" * 60)
    print("  GENERAL LEDGER SCRAPER")
    print(f"  Cutover date: {CUTOVER_DATE}")
    print("=" * 60)

    os.makedirs(GL_DIR, exist_ok=True)
    init_db()

    session = get_session()
    conn = get_conn()

    # ── Step 1: Chart of Accounts ──────────────────────────────────────────
    print("\n[1/4] Fetching Chart of Accounts (GLAccounts.php) ...")
    try:
        gl_html = session.get("/GLAccounts.php")
        # Save raw HTML
        with open(os.path.join(GL_DIR, "gl_accounts_raw.html"), "w", encoding="utf-8") as f:
            f.write(gl_html)

        # Extract account rows from table
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', gl_html, re.DOTALL)
        accounts = []
        for row in rows:
            tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            if len(tds) < 2:
                continue
            vals = [clean(td) for td in tds]
            # webERP account rows: account code | account name | (section/type...)
            acc_code = vals[0].strip()
            acc_name = vals[1].strip() if len(vals) > 1 else ""
            if not acc_code or not re.match(r'^[\dA-Za-z\-\.]+$', acc_code):
                continue
            if len(acc_code) < 2 or len(acc_code) > 20:
                continue

            acc_type = vals[2].strip() if len(vals) > 2 else ""
            acc_group = vals[3].strip() if len(vals) > 3 else ""
            balance = vals[-1] if len(vals) > 4 else "0.00"

            accounts.append({
                "account_code": acc_code,
                "account_name": acc_name,
                "account_type": acc_type,
                "account_group": acc_group,
                "balance": balance,
            })

            conn.execute("""
                INSERT OR REPLACE INTO gl_accounts
                  (account_code, account_name, account_type, account_group, balance)
                VALUES (?, ?, ?, ?, ?)
            """, (acc_code, acc_name, acc_type, acc_group, balance))

        conn.commit()
        print(f"  Found {len(accounts)} GL accounts")

        # Save CSV
        with open(os.path.join(GL_DIR, "chart_of_accounts.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["account_code", "account_name", "account_type", "account_group", "balance"])
            w.writeheader()
            w.writerows(accounts)

    except Exception as e:
        print(f"  ✗ GLAccounts.php error: {e}")

    # ── Step 2: Trial Balance ──────────────────────────────────────────────
    print("\n[2/4] Fetching Trial Balance (GLTrialBalance.php) ...")
    try:
        tb_html = session.get("/GLTrialBalance.php")
        tb_form_id = session.get_form_id(tb_html)

        tb_result = safe_post(session, "/GLTrialBalance.php", {
            "FormID": tb_form_id,
            "PeriodFrom": TB_PERIOD_FROM_CUTOVER,
            "PeriodTo": TB_PERIOD_TO_LATEST,
            "ShowTB": "Show Details",
        })
        with open(os.path.join(GL_DIR, "trial_balance.html"), "w", encoding="utf-8") as f:
            f.write(tb_result)

        # Parse trial balance rows
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', tb_result, re.DOTALL)
        tb_rows = []
        for row in rows:
            tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            if len(tds) >= 3:
                vals = [clean(td) for td in tds]
                if vals[0] and re.match(r'^[\dA-Za-z\-\.]{2,20}$', vals[0]):
                    tb_rows.append({"account_code": vals[0], "account_name": vals[1],
                                    "debit": vals[2] if len(vals) > 2 else "0.00",
                                    "credit": vals[3] if len(vals) > 3 else "0.00"})

        with open(os.path.join(GL_DIR, "trial_balance.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["account_code", "account_name", "debit", "credit"])
            w.writeheader()
            w.writerows(tb_rows)
        print(f"  Trial Balance: {len(tb_rows)} account rows saved")

    except Exception as e:
        print(f"  ✗ Trial Balance error: {e}")

    # ── Step 3: Journal Inquiry (all transaction types) ───────────────────
    print("\n[3/4] Fetching GL lines (GLJournalInquiry.php, all types) ...")
    try:
        conn.execute("DELETE FROM gl_transactions")
        conn.commit()

        journal_rows = []
        total_saved = 0
        for type_code, type_label in JOURNAL_TRANS_TYPES.items():
            ji_html = session.get("/GLJournalInquiry.php")
            ji_form_id = session.get_form_id(ji_html)
            ji_result = safe_post(session, "/GLJournalInquiry.php", {
                "FormID": ji_form_id,
                "TransType": type_code,
                "NumberFrom": "1",
                "NumberTo": "99999",
                "FromTransDate": CUTOVER_DATE,
                "ToTransDate": "2026-12-31",
                "Show": "Show transactions",
            })
            if is_login_page(ji_result) or is_form_verification_error(ji_result):
                print(f"  ✗ {type_label}: invalid page, skipped")
                continue

            batch = parse_journal_rows(ji_result)
            for row in batch:
                acc = row["account_code"]
                if acc:
                    conn.execute(
                        "INSERT OR IGNORE INTO gl_accounts (account_code, account_name) VALUES (?, ?)",
                        (acc, acc),
                    )
                conn.execute("""
                    INSERT INTO gl_transactions
                      (account_code, trans_date, trans_no, trans_type, narrative, debit, credit)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    row["account_code"],
                    row["trans_date"],
                    row["trans_no"],
                    type_label,
                    row["narrative"],
                    row["debit"],
                    row["credit"],
                ))
                journal_rows.append({**row, "trans_type": type_label})
            conn.commit()
            total_saved += len(batch)
            print(f"  {type_label}: {len(batch)} rows")
            time.sleep(0.5)

        with open(os.path.join(GL_DIR, "journal_inquiry_last.html"), "w", encoding="utf-8") as f:
            f.write(ji_result)
        with open(os.path.join(GL_DIR, "journal_entries.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(
                f,
                fieldnames=["trans_date", "trans_no", "account_code", "trans_type", "narrative", "debit", "credit"],
            )
            w.writeheader()
            w.writerows(journal_rows)
        print(f"  GL lines saved: {total_saved} rows")

    except Exception as e:
        print(f"  ✗ Journal Inquiry error: {e}")

    # ── Step 4: Per-account report (not available on this tenant) ───────────
    print("\n[4/4] GLAccountReport.php — skipped (Happifoam form has no date/account inquiry UI)")

    conn.close()
    print("\n  GL scrape complete!")


if __name__ == "__main__":
    scrape_gl()
