"""Reliable Customer/Supplier inquiry fetch with session + FormID recovery."""

import time
from urllib.parse import quote

from erp_html import classify_response
from login import CUTOVER_DATE


def fetch_customer_inquiry(session, customer_id: str, max_attempts: int = 6) -> str:
    path = f"/CustomerInquiry.php?CustomerID={customer_id}"
    last_reason = "unknown"

    for attempt in range(1, max_attempts + 1):
        inq_html = session.get(path)
        get_reason = classify_response(inq_html, customer_id, "customer")
        if get_reason == "login_required":
            session.login()
            continue
        if get_reason != "ok":
            last_reason = f"get:{get_reason}"
            time.sleep(0.4 * attempt)
            continue

        form_id = session.get_form_id(inq_html)
        if not form_id:
            last_reason = "missing_form_id"
            time.sleep(0.4 * attempt)
            continue

        result_html = session.post(
            path,
            fields={
                "FormID": form_id,
                "CustomerID": customer_id,
                "TransAfterDate": CUTOVER_DATE,
                "Status": "",
                "Refresh Inquiry": "Refresh Inquiry",
            },
        )
        post_reason = classify_response(result_html, customer_id, "customer")
        if post_reason == "ok":
            return result_html

        last_reason = f"post:{post_reason}"
        if post_reason in ("form_verification_error", "unexpected_page"):
            # Stale FormID / partial page — fresh GET on next attempt
            time.sleep(0.5 * attempt)
            continue
        if post_reason == "login_required":
            session.login()
            continue

    raise RuntimeError(
        f"Customer inquiry failed for {customer_id} after {max_attempts} tries ({last_reason})"
    )


def fetch_supplier_inquiry(session, supplier_id: str, max_attempts: int = 6) -> str:
    """Supplier account inquiry (SupplierInquiry.php on this tenant)."""
    path = f"/SupplierInquiry.php?SupplierID={quote(supplier_id)}"
    last_reason = "unknown"

    for attempt in range(1, max_attempts + 1):
        inq_html = session.get(path)
        get_reason = classify_response(inq_html, supplier_id, "supplier")
        if get_reason == "login_required":
            session.login()
            continue
        if get_reason != "ok":
            last_reason = f"get:{get_reason}"
            time.sleep(0.4 * attempt)
            continue

        form_id = session.get_form_id(inq_html)
        if not form_id:
            last_reason = "missing_form_id"
            time.sleep(0.4 * attempt)
            continue

        result_html = session.post(
            path,
            fields={
                "FormID": form_id,
                "SupplierID": supplier_id,
                "TransAfterDate": CUTOVER_DATE,
                "Refresh Inquiry": "Refresh Inquiry",
            },
        )
        post_reason = classify_response(result_html, supplier_id, "supplier")
        if post_reason == "ok":
            return result_html

        last_reason = f"post:{post_reason}"
        if post_reason in ("form_verification_error", "unexpected_page"):
            time.sleep(0.5 * attempt)
            continue
        if post_reason == "login_required":
            session.login()
            continue

    raise RuntimeError(
        f"Supplier inquiry failed for {supplier_id} after {max_attempts} tries ({last_reason})"
    )
