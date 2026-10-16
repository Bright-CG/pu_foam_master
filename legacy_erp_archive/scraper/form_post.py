"""Safe form POST with FormID / session recovery (webERP)."""

import time

from erp_html import is_form_verification_error, is_login_page


def safe_post(session, path: str, fields: dict, max_attempts: int = 6, timeout=60) -> str:
    last_error = "unknown"
    for attempt in range(1, max_attempts + 1):
        if not session._logged_in:
            session.login()

        html = session.post(path, fields, timeout=timeout)
        if is_login_page(html):
            session.log("POST returned login page — re-authenticating")
            session._logged_in = False
            continue
        if is_form_verification_error(html):
            last_error = "form_verification_error"
            time.sleep(0.5 * attempt)
            continue
        return html

    raise RuntimeError(f"POST {path} failed after {max_attempts} tries ({last_error})")
