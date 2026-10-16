"""
scrape_gl_account_inquiry.py — GL ledger via SelectGLAccount → GLAccountInquiry.

Resumable per account + per period; optional parallel workers.
"""

import argparse
import csv
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Tuple

from db import get_conn, init_db
from erp_html import is_login_page
from login import get_session, CUTOVER_DATE
from scrape_customers import clean as html_clean

REQUEST_DELAY = 0.15
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
GL_INQ_DIR = os.path.join(DATA_DIR, "gl_inquiry")

PERIOD_ID_FROM = "12"
PERIOD_ID_TO = "73"
EXPECTED_PERIOD_COUNT = int(PERIOD_ID_TO) - int(PERIOD_ID_FROM) + 1

_db_lock = threading.Lock()
_print_lock = threading.Lock()


def clean(text):
    return html_clean(text)


def is_valid_inquiry_html(html: str) -> bool:
    low = html.lower()
    if is_login_page(html) or "form verification" in low:
        return False
    return "Debit" in html and "Credit" in html and "Balance" in html


def extract_gl_codes(session) -> List[str]:
    html = session.get("/SelectGLAccount.php")
    m = re.search(
        r'<select[^>]*name=["\']GLCode["\'][^>]*>(.*?)</select>',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    codes: List[str] = []
    seen = set()
    if m:
        for val, _label in re.findall(
            r'<option[^>]*value=["\']([^"\']+)["\'][^>]*>(.*?)</option>',
            m.group(1),
            re.DOTALL,
        ):
            val = val.strip()
            if not val or val in seen:
                continue
            if not re.match(r"^[\dA-Za-z][\dA-Za-z\-\.]*$", val):
                continue
            seen.add(val)
            codes.append(val)

    conn = get_conn()
    for row in conn.execute("SELECT account_code FROM gl_accounts ORDER BY account_code"):
        c = row["account_code"]
        if c and c not in seen:
            seen.add(c)
            codes.append(c)
    conn.close()
    return sorted(codes)


def extract_periods(html: str) -> List[Tuple[str, str]]:
    m = re.search(
        r'<select[^>]*name=["\']Period\[\]["\'][^>]*>(.*?)</select>',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    if not m:
        return []
    periods = []
    for pid, label in re.findall(
        r'<option[^>]*value=["\'](\d+)["\'][^>]*>([^<]*)</option>',
        m.group(1),
    ):
        label = clean(label)
        try:
            pid_int = int(pid)
        except ValueError:
            continue
        if pid_int < int(PERIOD_ID_FROM) or pid_int > int(PERIOD_ID_TO):
            continue
        periods.append((pid, label))
    periods.sort(key=lambda x: int(x[0]))
    return periods


def parse_inquiry_rows(html: str) -> List[dict]:
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.DOTALL)
        if len(tds) < 7:
            continue
        vals = [clean(td) for td in tds]
        trans_date = vals[2] if len(vals) > 2 else ""
        if not re.match(r"\d{4}-\d{2}-\d{2}", trans_date):
            continue
        rows.append(
            {
                "trans_type": vals[0],
                "trans_no": vals[1],
                "trans_date": trans_date,
                "narrative": vals[3] if len(vals) > 3 else "",
                "debit": vals[4] if len(vals) > 4 and vals[4] != "" else "",
                "credit": vals[5] if len(vals) > 5 and vals[5] != "" else "",
                "balance": vals[6] if len(vals) > 6 else "",
                "tag": vals[7] if len(vals) > 7 else "",
            }
        )
    return rows


def fetch_account_period(session, account_code: str, period_id: str, max_attempts: int = 8) -> str:
    last_err = "unknown"
    for attempt in range(1, max_attempts + 1):
        try:
            path = f"/GLAccountInquiry.php?Account={account_code}&Show=Yes"
            page = session.get(path, timeout=120)
            if is_login_page(page):
                session._logged_in = False
                session.login()
                last_err = "login_page_on_get"
                time.sleep(1.5 * attempt)
                continue
            form_id = session.get_form_id(page)
            if not form_id:
                last_err = "missing_form_id"
                time.sleep(1.0 * attempt)
                continue

            html = session.post(
                "/GLAccountInquiry.php",
                {
                    "FormID": form_id,
                    "Account": account_code,
                    "Period[]": period_id,
                    "Show": "Show Account Transactions",
                },
                timeout=120,
            )
            if is_valid_inquiry_html(html):
                return html
            if is_login_page(html):
                session._logged_in = False
                session.login()
            last_err = "invalid_inquiry_html"
        except Exception as e:
            last_err = str(e)[:200]
        time.sleep(1.5 * attempt)

    raise RuntimeError(f"period {period_id} failed after {max_attempts} tries ({last_err})")


def periods_done_for_account(conn, account_code: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM gl_account_inquiry_periods WHERE account_code = ?",
        (account_code,),
    ).fetchone()
    return int(row[0]) if row else 0


def account_fully_scraped(conn, account_code: str, expected: int) -> bool:
    return periods_done_for_account(conn, account_code) >= expected


def save_period(
    conn,
    account_code: str,
    period_id: str,
    period_label: str,
    lines: List[dict],
):
    conn.execute(
        "DELETE FROM gl_account_inquiry_lines WHERE account_code = ? AND period_id = ?",
        (account_code, period_id),
    )
    for line in lines:
        conn.execute(
            """
            INSERT INTO gl_account_inquiry_lines
              (account_code, period_id, period_label, trans_type, trans_no, trans_date,
               narrative, debit, credit, balance, tag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                account_code,
                period_id,
                period_label,
                line["trans_type"],
                line["trans_no"],
                line["trans_date"],
                line.get("narration") or line.get("narrative") or "",
                line["debit"],
                line["credit"],
                line["balance"],
                line["tag"],
            ),
        )
    conn.execute(
        """
        INSERT OR REPLACE INTO gl_account_inquiry_periods
          (account_code, period_id, period_label, line_count, scraped_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (account_code, period_id, period_label, len(lines)),
    )


def rebuild_account_csv(conn, account_code: str):
    rows = conn.execute(
        """
        SELECT period_id, period_label, trans_type, trans_no, trans_date,
               narrative, debit, credit, balance, tag
        FROM gl_account_inquiry_lines
        WHERE account_code = ?
        ORDER BY CAST(period_id AS INTEGER), trans_date, trans_no
        """,
        (account_code,),
    ).fetchall()
    if not rows:
        return
    os.makedirs(GL_INQ_DIR, exist_ok=True)
    path = os.path.join(GL_INQ_DIR, f"{account_code.replace('/', '_')}.csv")
    fields = [
        "period_id",
        "period_label",
        "trans_type",
        "trans_no",
        "trans_date",
        "narrative",
        "debit",
        "credit",
        "balance",
        "tag",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(
                {
                    "period_id": r["period_id"],
                    "period_label": r["period_label"],
                    "trans_type": r["trans_type"],
                    "trans_no": r["trans_no"],
                    "trans_date": r["trans_date"],
                    "narrative": r["narrative"],
                    "debit": r["debit"],
                    "credit": r["credit"],
                    "balance": r["balance"],
                    "tag": r["tag"],
                }
            )


def scrape_account(session, conn, account_code: str, force: bool = False) -> int:
    intro = session.get(f"/GLAccountInquiry.php?Account={account_code}&Show=Yes", timeout=120)
    periods = extract_periods(intro)
    if not periods:
        raise RuntimeError("no periods on GLAccountInquiry page")

    expected = len(periods)
    if not force and account_fully_scraped(conn, account_code, expected):
        row = conn.execute(
            "SELECT COUNT(*) FROM gl_account_inquiry_lines WHERE account_code = ?",
            (account_code,),
        ).fetchone()
        return int(row[0])

    if force:
        with _db_lock:
            conn.execute("DELETE FROM gl_account_inquiry_lines WHERE account_code = ?", (account_code,))
            conn.execute("DELETE FROM gl_account_inquiry_periods WHERE account_code = ?", (account_code,))
            conn.commit()

    done_periods = set()
    if not force:
        for row in conn.execute(
            "SELECT period_id FROM gl_account_inquiry_periods WHERE account_code = ?",
            (account_code,),
        ):
            done_periods.add(row["period_id"])

    total_new = 0
    for period_id, period_label in periods:
        if period_id in done_periods:
            continue
        html = fetch_account_period(session, account_code, period_id)
        lines = parse_inquiry_rows(html)
        with _db_lock:
            save_period(conn, account_code, period_id, period_label, lines)
            conn.commit()
        total_new += len(lines)
        time.sleep(REQUEST_DELAY)

    with _db_lock:
        line_count = conn.execute(
            "SELECT COUNT(*) FROM gl_account_inquiry_lines WHERE account_code = ?",
            (account_code,),
        ).fetchone()[0]
        periods_done = periods_done_for_account(conn, account_code)
        rebuild_account_csv(conn, account_code)
        status = "ok" if periods_done >= expected else "partial"
        conn.execute(
            """
            INSERT INTO scrape_log (module, entity_id, status, message)
            VALUES ('gl_account_inquiry', ?, ?, ?)
            """,
            (
                account_code,
                status,
                f"{line_count} lines, periods {periods_done}/{expected}",
            ),
        )
        conn.commit()

    if periods_done < expected:
        raise RuntimeError(f"incomplete: only {periods_done}/{expected} periods")
    return int(line_count)


def _worker_scrape(code: str, force: bool) -> Tuple[str, int, Optional[str]]:
    session = get_session()
    conn = get_conn()
    conn.execute("PRAGMA busy_timeout = 60000")
    try:
        n = scrape_account(session, conn, code, force=force)
        return code, n, None
    except Exception as e:
        with _db_lock:
            conn.execute(
                """
                INSERT INTO scrape_log (module, entity_id, status, message)
                VALUES ('gl_account_inquiry', ?, 'error', ?)
                """,
                (code, str(e)[:500]),
            )
            conn.commit()
        return code, -1, str(e)
    finally:
        conn.close()


def backfill_period_markers(conn):
    """Mark periods already in DB from earlier scraper versions."""
    conn.execute(
        """
        INSERT OR IGNORE INTO gl_account_inquiry_periods
          (account_code, period_id, period_label, line_count)
        SELECT account_code, period_id, MAX(period_label), COUNT(*)
        FROM gl_account_inquiry_lines
        GROUP BY account_code, period_id
        """
    )
    for row in conn.execute(
        """
        SELECT entity_id, message FROM scrape_log
        WHERE module = 'gl_account_inquiry' AND status = 'ok'
        """
    ):
        acct = row["entity_id"]
        msg = row["message"] or ""
        m_new = re.search(r"periods (\d+)/(\d+)", msg)
        m_old = re.search(r"(\d+) lines, (\d+) periods", msg)
        complete = False
        if m_new and int(m_new.group(1)) >= int(m_new.group(2)):
            complete = int(m_new.group(2)) >= EXPECTED_PERIOD_COUNT
        elif m_old and int(m_old.group(2)) >= EXPECTED_PERIOD_COUNT:
            # Do not trust "0 lines, 62 periods" from interrupted runs
            if m_old.group(1) != "0":
                complete = True
        if not complete:
            continue
        for pid in range(int(PERIOD_ID_FROM), int(PERIOD_ID_TO) + 1):
            conn.execute(
                """
                INSERT OR IGNORE INTO gl_account_inquiry_periods
                  (account_code, period_id, line_count)
                VALUES (?, ?, 0)
                """,
                (acct, str(pid)),
            )
    conn.commit()


def filter_resume_codes(conn, codes: List[str], resume: bool) -> List[str]:
    if not resume:
        return codes
    pending = []
    for code in codes:
        done = periods_done_for_account(conn, code)
        if done >= EXPECTED_PERIOD_COUNT:
            continue
        pending.append(code)
    return pending


def scrape_gl_account_inquiry(
    account_filter: Optional[List[str]] = None,
    limit: Optional[int] = None,
    skip_existing: bool = False,
    resume: bool = True,
    force: bool = False,
    workers: int = 1,
):
    print("\n" + "=" * 60)
    print("  GL ACCOUNT INQUIRY SCRAPER (SelectGLAccount / GLAccountInquiry)")
    print(f"  Periods: id {PERIOD_ID_FROM}–{PERIOD_ID_TO} (from cutover {CUTOVER_DATE})")
    print(f"  Workers: {workers}  |  Resume: {resume}  |  Force: {force}")
    print("=" * 60)

    os.makedirs(GL_INQ_DIR, exist_ok=True)
    init_db()
    conn = get_conn()
    backfill_period_markers(conn)
    session = get_session()

    codes = extract_gl_codes(session)
    conn.close()

    if account_filter:
        filt = set(account_filter)
        codes = [c for c in codes if c in filt]

    conn = get_conn()
    if force:
        pass
    elif resume or skip_existing:
        codes = filter_resume_codes(conn, codes, resume=True)
    conn.close()

    if limit:
        codes = codes[:limit]

    total_accounts = len(codes)
    print(f"  Accounts to scrape: {total_accounts}")

    grand_lines = 0
    failed = 0
    # Happifoam ERP: one user session — parallel logins invalidate each other.
    if workers > 1:
        print("  NOTE: ERP allows only one active session; using 1 worker (not parallel logins).")
        workers = 1
    workers = max(1, workers)

    if workers == 1:
        conn = get_conn()
        conn.execute("PRAGMA busy_timeout = 60000")
        session = get_session()
        for idx, code in enumerate(codes, 1):
            try:
                n = scrape_account(session, conn, code, force=force)
                grand_lines += n
                print(f"  [{idx:04d}/{total_accounts}] {code:<12} {n:>6} lines")
            except Exception as e:
                failed += 1
                print(f"  [{idx:04d}/{total_accounts}] {code:<12} ERROR: {e}")
                conn.execute(
                    """
                    INSERT INTO scrape_log (module, entity_id, status, message)
                    VALUES ('gl_account_inquiry', ?, 'error', ?)
                    """,
                    (code, str(e)[:500]),
                )
                conn.commit()
        conn.close()
    else:
        completed = 0
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_worker_scrape, code, force): code for code in codes}
            for fut in as_completed(futures):
                code, n, err = fut.result()
                completed += 1
                with _print_lock:
                    if err:
                        failed += 1
                        print(f"  [{completed:04d}/{total_accounts}] {code:<12} ERROR: {err[:120]}")
                    else:
                        grand_lines += max(n, 0)
                        print(f"  [{completed:04d}/{total_accounts}] {code:<12} {n:>6} lines")

    summary_path = os.path.join(DATA_DIR, "gl_inquiry_last_run.txt")
    summary = (
        f"Finished: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Accounts attempted: {total_accounts}\n"
        f"Errors: {failed}\n"
        f"Lines this run: {grand_lines}\n"
        f"Resume: .venv/bin/python scrape_gl_account_inquiry.py --workers 8\n"
        f"Log: {os.path.join(DATA_DIR, 'gl_inquiry_run.log')}\n"
    )
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary)

    print(f"\n  Done: {total_accounts - failed} ok, {failed} errors, {grand_lines:,} lines this run")
    print(f"  Summary written: {summary_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--account", action="append", help="Only these GL codes")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--skip-existing", action="store_true", help="Same as --resume")
    parser.add_argument("--no-resume", action="store_true", help="Re-run every account (still per-period safe unless --force)")
    parser.add_argument("--force", action="store_true", help="Re-scrape accounts from scratch")
    parser.add_argument("--workers", type=int, default=1, help="Keep at 1 (ERP rejects multiple simultaneous logins)")
    args = parser.parse_args()
    scrape_gl_account_inquiry(
        account_filter=args.account,
        limit=args.limit,
        skip_existing=args.skip_existing,
        resume=not args.no_resume,
        force=args.force,
        workers=args.workers,
    )
