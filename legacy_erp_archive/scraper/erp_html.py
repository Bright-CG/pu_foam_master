"""HTML validation helpers for LeadingEdge / webERP scrape responses."""

import re


def clean(text):
    text = re.sub(r"<[^>]+>", "", str(text))
    return re.sub(r"\s+", " ", text).strip()


def is_login_page(html: str) -> bool:
    if not html:
        return True
    return (
        "UserNameEntryField" in html
        or "Please sign in to your account" in html
        or "<title>Login - LeadingEdge Cloud ERP</title>" in html
    )


def is_form_verification_error(html: str) -> bool:
    return "Error in form verification" in html


def is_customer_inquiry_page(html: str, customer_id: str) -> bool:
    if is_login_page(html) or is_form_verification_error(html):
        return False
    # Stable marker on a successful CustomerInquiry refresh
    if f"Customer: {customer_id} -" in html:
        return True
    if f"CustomerInquiry.php?CustomerID={customer_id}" in html and "TransAfterDate" in html:
        return True
    return False


def is_supplier_inquiry_page(html: str, supplier_id: str) -> bool:
    if is_login_page(html) or is_form_verification_error(html):
        return False
    if f"Supplier: {supplier_id} -" in html:
        return True
    if f"Supplier: {supplier_id} –" in html:
        return True
    if f"Supplier: {supplier_id} -" in html and "TransAfterDate" in html:
        return True
    if f"Supplier: {supplier_id} –" in html and "TransAfterDate" in html:
        return True
    return False


def classify_response(html: str, entity_id: str, kind: str = "customer") -> str:
    if is_login_page(html):
        return "login_required"
    if is_form_verification_error(html):
        return "form_verification_error"
    if kind == "customer":
        return "ok" if is_customer_inquiry_page(html, entity_id) else "unexpected_page"
    if kind == "supplier":
        return "ok" if is_supplier_inquiry_page(html, entity_id) else "unexpected_page"
    return "unexpected_page"
