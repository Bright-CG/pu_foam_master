#!/usr/bin/env python3
"""
Prepare GL inquiry resume after an interrupted scrape.

Keeps the first N accounts in ERP sort order (default 25 = through 100-510 in the
first successful batch). Clears false "complete" markers (62 periods, 0 lines) for
later accounts so --resume will fetch them again. Partial accounts (some periods only)
are kept and filled in.
"""

import argparse
import sqlite3

from db import DB_PATH, init_db
from scrape_gl_account_inquiry import EXPECTED_PERIOD_COUNT, extract_gl_codes
from login import get_session


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protect-first",
        type=int,
        default=25,
        help="Number of accounts from start of list to leave untouched (default 25)",
    )
    parser.add_argument(
        "--start-at",
        type=int,
        default=None,
        help="Re-fetch from this 1-based queue index (e.g. 39 = 101-140). Sacred first 25 never wiped.",
    )
    args = parser.parse_args()

    init_db()
    session = get_session()
    codes = extract_gl_codes(session)
    session = None

    protect_n = (args.start_at - 1) if args.start_at else args.protect_first
    protected = set(codes[:protect_n])
    # First 25 accounts were completed before the network outage — never wipe them.
    sacred = set(codes[:25])

    conn = sqlite3.connect(DB_PATH)
    wiped = []
    for code in codes:
        if code in sacred:
            continue
        periods = conn.execute(
            "SELECT COUNT(*) FROM gl_account_inquiry_periods WHERE account_code = ?",
            (code,),
        ).fetchone()[0]
        lines = conn.execute(
            "SELECT COUNT(*) FROM gl_account_inquiry_lines WHERE account_code = ?",
            (code,),
        ).fetchone()[0]
        # Wipe fake full completes (0 lines) or bogus backfill; keep real partials
        if periods >= EXPECTED_PERIOD_COUNT and lines == 0:
            conn.execute(
                "DELETE FROM gl_account_inquiry_lines WHERE account_code = ?",
                (code,),
            )
            conn.execute(
                "DELETE FROM gl_account_inquiry_periods WHERE account_code = ?",
                (code,),
            )
            wiped.append((code, "fake-complete"))
        elif periods == 0 and lines == 0:
            pass  # already pending
    conn.commit()

    pending = []
    for code in codes:
        if code in protected:
            continue
        done = conn.execute(
            "SELECT COUNT(*) FROM gl_account_inquiry_periods WHERE account_code = ?",
            (code,),
        ).fetchone()[0]
        if done < EXPECTED_PERIOD_COUNT:
            pending.append(code)

    conn.close()

    print(f"Protected (unchanged): {len(protected)} accounts")
    print(f"Wiped false completes: {len(wiped)}")
    for c, why in wiped[:15]:
        print(f"  - {c} ({why})")
    if len(wiped) > 15:
        print(f"  ... and {len(wiped) - 15} more")
    print(f"Still to finish (resume): {len(pending)} accounts")
    print("\nNext: python scrape_gl_account_inquiry.py --workers 1")


if __name__ == "__main__":
    main()
