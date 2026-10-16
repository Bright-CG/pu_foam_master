"""Fetch CustomerStatementBalances.php with session + FormID recovery."""

import time

from erp_html import classify_response, is_login_page
from form_post import safe_post
from login import CUTOVER_DATE

STATEMENT_PATH = "/CustomerStatementBalances.php"
SUPPLIER_STATEMENT_PATH = "/SupplierStatementBalances.php"
DEFAULT_TO_DATE = "2026-12-31"


def _statement_ok(html: str) -> bool:
    return "S/N" in html and "Debit" in html and "Credit" in html


def fetch_customer_statement(
    session,
    debtor_no: str,
    from_date: str = CUTOVER_DATE,
    to_date: str = DEFAULT_TO_DATE,
    max_attempts: int = 6,
) -> str:
    last_reason = "unknown"

    for attempt in range(1, max_attempts + 1):
        page_html = session.get(STATEMENT_PATH)
        get_reason = classify_response(page_html, debtor_no, "customer")
        if get_reason == "login_required":
            session.login()
            continue
        if get_reason not in ("ok", "unexpected_page"):
            last_reason = f"get:{get_reason}"
            time.sleep(0.4 * attempt)
            continue

        form_id = session.get_form_id(page_html)
        if not form_id:
            last_reason = "missing_form_id"
            time.sleep(0.4 * attempt)
            continue

        result_html = safe_post(
            session,
            STATEMENT_PATH,
            {
                "FormID": form_id,
                "DebtorNo": debtor_no,
                "FromDate": from_date,
                "ToDate": to_date,
                "RunReport": "Show Customer Statement",
            },
        )
        if _statement_ok(result_html):
            return result_html

        post_reason = classify_response(result_html, debtor_no, "customer")

        last_reason = f"post:{post_reason}"
        time.sleep(0.5 * attempt)

    raise RuntimeError(
        f"Customer statement failed for {debtor_no} after {max_attempts} tries ({last_reason})"
    )


def fetch_supplier_statement(
    session,
    supplier_id: str,
    from_date: str = CUTOVER_DATE,
    to_date: str = DEFAULT_TO_DATE,
    max_attempts: int = 6,
) -> str:
    last_reason = "unknown"

    for attempt in range(1, max_attempts + 1):
        page_html = session.get(SUPPLIER_STATEMENT_PATH)
        if is_login_page(page_html):
            session.login()
            continue

        form_id = session.get_form_id(page_html)
        if not form_id:
            last_reason = "missing_form_id"
            time.sleep(0.4 * attempt)
            continue

        result_html = safe_post(
            session,
            SUPPLIER_STATEMENT_PATH,
            {
                "FormID": form_id,
                "SupplierID": supplier_id,
                "FromDate": from_date,
                "ToDate": to_date,
                "RunReport": "Show Supplier Statement",
            },
        )
        if _statement_ok(result_html):
            return result_html

        # Some tenants use alternate button labels
        if not _statement_ok(result_html):
            result_html = safe_post(
                session,
                SUPPLIER_STATEMENT_PATH,
                {
                    "FormID": form_id,
                    "SupplierID": supplier_id,
                    "FromDate": from_date,
                    "ToDate": to_date,
                    "RunReport": "Show Creditors Statement",
                },
            )
        if _statement_ok(result_html):
            return result_html

        last_reason = "post:unexpected_page"
        time.sleep(0.5 * attempt)

    raise RuntimeError(
        f"Supplier statement failed for {supplier_id} after {max_attempts} tries ({last_reason})"
    )
