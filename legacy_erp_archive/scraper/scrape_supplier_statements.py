"""
scrape_supplier_statements.py — Supplier statements from SupplierStatementBalances.php

Same column layout as customer statements (10 columns with Debit/Credit/Balances).
"""

import argparse
import csv
import os
import re
import time
from typing import List, Optional, Tuple

from db import get_conn, init_db
from login import get_session, CUTOVER_DATE
from scrape_suppliers import extract_all_suppliers
from statement_fetch import DEFAULT_TO_DATE, fetch_supplier_statement

REQUEST_DELAY = 0.25
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
STMT_DIR = os.path.join(DATA_DIR, "supplier_statements")


def clean(text):
    text = re.sub(r"<[^>]+>", "", str(text))
    return re.sub(r"\s+", " ", text).strip()


def extract_supplier_name(html: str) -> str:
    m = re.search(r"Supplier Name:\s*([^<]+?)\s*<br\s*/?>", html, re.IGNORECASE)
    if m:
        return clean(m.group(1))
    m = re.search(r"Supplier:\s*\S+\s*-\s*(.+?)<br", html, re.IGNORECASE)
    return clean(m.group(1)) if m else ""


def parse_statement_rows(html: str, supplier_id: str) -> List[dict]:
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
        supp_id = vals[1] or supplier_id
        trans_type = vals[2]
        if not trans_type and vals[6].lower() == "opening balance":
            trans_type = "Opening Balance"

        rows.append(
            {
                "line_no": line_no,
                "supplier_id": supp_id or supplier_id,
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
    supplier_id: str,
    supplier_name: str,
    from_date: str,
    to_date: str,
    lines: List[dict],
):
    if supplier_name:
        conn.execute(
            """
            INSERT INTO suppliers (id, name)
            VALUES (?, ?)
            ON CONFLICT(id) DO UPDATE SET name = excluded.name
            """,
            (supplier_id, supplier_name),
        )

    conn.execute(
        "DELETE FROM supplier_statement_lines WHERE supplier_id = ?", (supplier_id,)
    )
    for line in lines:
        conn.execute(
            """
            INSERT INTO supplier_statement_lines
              (supplier_id, line_no, trans_type, trans_no, narration, trans_date,
               reference, debit, credit, balance, report_from_date, report_to_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                supplier_id,
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


def write_csv(supplier_id: str, lines: List[dict]):
    os.makedirs(STMT_DIR, exist_ok=True)
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", supplier_id)
    path = os.path.join(STMT_DIR, f"{safe}.csv")
    fields = [
        "line_no",
        "supplier_id",
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


def scrape_supplier_statements(
    supplier_filter: Optional[List[str]] = None,
    from_date: str = CUTOVER_DATE,
    to_date: str = DEFAULT_TO_DATE,
    limit: Optional[int] = None,
):
    print("\n" + "=" * 60)
    print("  SUPPLIER STATEMENT SCRAPER (SupplierStatementBalances.php)")
    print(f"  Period: {from_date} → {to_date}")
    print("=" * 60)

    os.makedirs(STMT_DIR, exist_ok=True)
    init_db()
    conn = get_conn()
    session = get_session()

    list_html = session.get("/SupplierStatementBalances.php")
    suppliers = extract_all_suppliers(list_html)
    if supplier_filter:
        filt = set(supplier_filter)
        suppliers = [(i, n) for i, n in suppliers if i in filt]
    if limit:
        suppliers = suppliers[:limit]

    total = len(suppliers)
    print(f"  Suppliers to scrape: {total}")

    ok = empty = failed = 0
    line_count = 0

    for idx, (supp_id, label) in enumerate(suppliers, 1):
        prefix = f"  [{idx:04d}/{total}] {supp_id}"
        try:
            html = fetch_supplier_statement(session, supp_id, from_date, to_date)
            name = extract_supplier_name(html) or label
            lines = parse_statement_rows(html, supp_id)
            if not lines:
                empty += 1
                conn.execute(
                    """
                    INSERT INTO scrape_log (module, entity_id, status, message)
                    VALUES ('supplier_statement', ?, 'empty', 'No statement rows parsed')
                    """,
                    (supp_id,),
                )
                conn.commit()
                print(f"{prefix} — {label[:45]:<45} (empty)")
                continue

            save_statement(conn, supp_id, name, from_date, to_date, lines)
            write_csv(supp_id, lines)
            conn.execute(
                """
                INSERT INTO scrape_log (module, entity_id, status, message)
                VALUES ('supplier_statement', ?, 'ok', ?)
                """,
                (supp_id, f"{len(lines)} lines"),
            )
            conn.commit()
            ok += 1
            line_count += len(lines)
            print(f"{prefix} — {label[:45]:<45} {len(lines):>4} lines")
        except Exception as e:
            failed += 1
            print(f"{prefix} — ERROR: {e}")
            conn.execute(
                """
                INSERT INTO scrape_log (module, entity_id, status, message)
                VALUES ('supplier_statement', ?, 'error', ?)
                """,
                (supp_id, str(e)[:500]),
            )
            conn.commit()
        time.sleep(REQUEST_DELAY)

    conn.close()
    print(
        f"\n  Done: {ok} with data, {empty} empty, {failed} errors, {line_count} total lines"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-date", default=CUTOVER_DATE)
    parser.add_argument("--to-date", default=DEFAULT_TO_DATE)
    parser.add_argument("--supplier", action="append")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    scrape_supplier_statements(
        supplier_filter=args.supplier,
        from_date=args.from_date,
        to_date=args.to_date,
        limit=args.limit,
    )
