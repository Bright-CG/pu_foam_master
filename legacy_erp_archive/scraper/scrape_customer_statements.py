"""
scrape_customer_statements.py — Customer statements from CustomerStatementBalances.php

Columns (matches ERP print layout):
  S/N | CustomerID | Type | Trans No. | Narration | Trans Date | Reference | Debit | Credit | Balances

Does not modify customer_transactions (CustomerInquiry scrape); writes to customer_statement_lines.
"""

import argparse
import csv
import os
import re
import time
from typing import List, Optional, Tuple

from db import get_conn, init_db
from login import get_session, CUTOVER_DATE
from statement_fetch import DEFAULT_TO_DATE, fetch_customer_statement

REQUEST_DELAY = 0.25
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
STMT_DIR = os.path.join(DATA_DIR, "customer_statements")


def clean(text):
    text = re.sub(r"<[^>]+>", "", str(text))
    return re.sub(r"\s+", " ", text).strip()


def extract_debtor_list(html: str) -> List[Tuple[str, str]]:
    m = re.search(
        r'<select[^>]*name=["\']DebtorNo["\'][^>]*>(.*?)</select>',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    if not m:
        return []
    opts = re.findall(
        r'<option[^>]*value=["\']([^"\']+)["\'][^>]*>(.*?)</option>',
        m.group(1),
        re.DOTALL,
    )
    debtors = []
    seen = set()
    for val, label in opts:
        val = val.strip()
        label = clean(label)
        if not val or val in ("0", ""):
            continue
        if val in seen:
            continue
        seen.add(val)
        debtors.append((val, label))
    return debtors


def extract_customer_name(html: str) -> str:
    m = re.search(r"Customer Name:\s*([^<]+?)\s*<br\s*/?>", html, re.IGNORECASE)
    return clean(m.group(1)) if m else ""


def parse_statement_rows(html: str, debtor_no: str) -> List[dict]:
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.DOTALL)
        if len(tds) != 10:
            continue
        vals = [clean(td) for td in tds]
        trans_date = vals[5]
        if not re.match(r"\d{4}-\d{2}-\d{2}", trans_date):
            continue

        line_no = vals[0]
        cust_id = vals[1] or debtor_no
        trans_type = vals[2]
        if not trans_type and vals[6].lower() == "opening balance":
            trans_type = "Opening Balance"

        rows.append(
            {
                "line_no": line_no,
                "customer_id": cust_id or debtor_no,
                "trans_type": trans_type,
                "trans_no": vals[3],
                "narration": vals[4],
                "trans_date": trans_date,
                "reference": vals[6],
                "debit": vals[7] if vals[7] != "-" else "",
                "credit": vals[8] if vals[8] != "-" else "",
                "balance": vals[9],
            }
        )
    return rows


def save_statement(
    conn,
    debtor_no: str,
    customer_name: str,
    from_date: str,
    to_date: str,
    lines: List[dict],
):
    if customer_name:
        conn.execute(
            """
            INSERT INTO customers (id, name)
            VALUES (?, ?)
            ON CONFLICT(id) DO UPDATE SET name = excluded.name
            """,
            (debtor_no, customer_name),
        )

    conn.execute("DELETE FROM customer_statement_lines WHERE customer_id = ?", (debtor_no,))
    for line in lines:
        conn.execute(
            """
            INSERT INTO customer_statement_lines
              (customer_id, line_no, trans_type, trans_no, narration, trans_date,
               reference, debit, credit, balance, report_from_date, report_to_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                debtor_no,
                line["line_no"],
                line["trans_type"],
                line["trans_no"],
                line["narration"],
                line["trans_date"],
                line["reference"],
                line["debit"],
                line["credit"],
                line["balance"],
                from_date,
                to_date,
            ),
        )
    conn.commit()


def write_csv(debtor_no: str, lines: List[dict]):
    os.makedirs(STMT_DIR, exist_ok=True)
    path = os.path.join(STMT_DIR, f"{debtor_no}.csv")
    fields = [
        "line_no",
        "customer_id",
        "trans_type",
        "trans_no",
        "narration",
        "trans_date",
        "reference",
        "debit",
        "credit",
        "balance",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(lines)


def scrape_one(session, conn, debtor_no: str, debtor_label: str, from_date: str, to_date: str) -> int:
    html = fetch_customer_statement(session, debtor_no, from_date, to_date)
    name = extract_customer_name(html) or debtor_label
    lines = parse_statement_rows(html, debtor_no)
    if not lines:
        conn.execute(
            """
            INSERT INTO scrape_log (module, entity_id, status, message)
            VALUES ('customer_statement', ?, 'empty', 'No statement rows parsed')
            """,
            (debtor_no,),
        )
        conn.commit()
        return 0

    save_statement(conn, debtor_no, name, from_date, to_date, lines)
    write_csv(debtor_no, lines)
    conn.execute(
        """
        INSERT INTO scrape_log (module, entity_id, status, message)
        VALUES ('customer_statement', ?, 'ok', ?)
        """,
        (debtor_no, f"{len(lines)} lines"),
    )
    conn.commit()
    return len(lines)


def scrape_customer_statements(
    customer_filter: Optional[List[str]] = None,
    from_date: str = CUTOVER_DATE,
    to_date: str = DEFAULT_TO_DATE,
    limit: Optional[int] = None,
):
    print("\n" + "=" * 60)
    print("  CUSTOMER STATEMENT SCRAPER (CustomerStatementBalances.php)")
    print(f"  Period: {from_date} → {to_date}")
    print("=" * 60)

    os.makedirs(STMT_DIR, exist_ok=True)
    init_db()
    conn = get_conn()
    session = get_session()

    list_html = session.get("/CustomerStatementBalances.php")
    debtors = extract_debtor_list(list_html)
    if customer_filter:
        filt = set(customer_filter)
        debtors = [(i, n) for i, n in debtors if i in filt]
    if limit:
        debtors = debtors[:limit]

    total = len(debtors)
    print(f"  Debtors to scrape: {total}")

    ok = 0
    empty = 0
    failed = 0
    line_count = 0

    for idx, (debtor_no, label) in enumerate(debtors, 1):
        prefix = f"  [{idx:04d}/{total}] {debtor_no}"
        try:
            n = scrape_one(session, conn, debtor_no, label, from_date, to_date)
            line_count += n
            if n:
                ok += 1
                print(f"{prefix} — {label[:45]:<45} {n:>4} lines")
            else:
                empty += 1
                print(f"{prefix} — {label[:45]:<45} (empty)")
        except Exception as e:
            failed += 1
            print(f"{prefix} — ERROR: {e}")
            conn.execute(
                """
                INSERT INTO scrape_log (module, entity_id, status, message)
                VALUES ('customer_statement', ?, 'error', ?)
                """,
                (debtor_no, str(e)[:500]),
            )
            conn.commit()
        time.sleep(REQUEST_DELAY)

    conn.close()
    print(f"\n  Done: {ok} with data, {empty} empty, {failed} errors, {line_count} total lines")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-date", default=CUTOVER_DATE)
    parser.add_argument("--to-date", default=DEFAULT_TO_DATE)
    parser.add_argument("--customer", action="append", help="Only these debtor IDs (repeatable)")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    scrape_customer_statements(
        customer_filter=args.customer,
        from_date=args.from_date,
        to_date=args.to_date,
        limit=args.limit,
    )
