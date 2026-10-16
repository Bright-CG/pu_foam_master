"""
login.py — Shared authenticated session helper for the Happifoam Legacy ERP Scraper.

Uses `requests` (keep-alive, retries) instead of urllib for stability after network changes.
"""

import os
import re
import time

import requests

from env_loader import load_scraper_env
from erp_html import is_login_page

load_scraper_env()

BASE_URL = os.environ.get(
    "ERP_BASE_URL", "https://happifoam.leadingedgecloud.com"
).rstrip("/")
CUTOVER_DATE = os.environ.get("ERP_CUTOVER_DATE", "2021-10-18")

USERNAME = os.environ.get("ERP_USERNAME", "JOSHUA")
PASSWORD = os.environ.get("ERP_PASSWORD", "12345678")
COMPANY_ID = os.environ.get("ERP_COMPANY_ID", "0")

DEFAULT_TIMEOUT = 60
MAX_RETRIES = 4
RETRY_DELAY = 2


class ERPSession:
    """Manages an authenticated session against the LeadingEdge Cloud ERP."""

    def __init__(self, verbose=True):
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "HappifoamLegacyArchive/1.1",
                "Accept": "text/html,application/xhtml+xml",
            }
        )
        self._logged_in = False
        self._form_id = None

    def log(self, msg):
        if self.verbose:
            print(f"  [SESSION] {msg}")

    def login(self, max_retries=MAX_RETRIES, retry_delay=RETRY_DELAY):
        """Authenticate and return the session. Retries on network errors."""
        for attempt in range(1, max_retries + 1):
            try:
                self.log(f"Login attempt {attempt}/{max_retries} ...")
                res = self.session.get(f"{BASE_URL}/", timeout=DEFAULT_TIMEOUT)
                res.raise_for_status()
                html = res.text

                m = re.search(
                    r'name=["\']FormID["\']\s+value=["\']([^"\']+)["\']', html
                )
                if not m:
                    raise ValueError("FormID not found on login page")
                form_id = m.group(1)

                post_data = {
                    "FormID": form_id,
                    "CompanyNameField": COMPANY_ID,
                    "UserNameEntryField": USERNAME,
                    "Password": PASSWORD,
                    "SubmitUser": "Login",
                }

                res2 = self.session.post(
                    f"{BASE_URL}/index.php",
                    data=post_data,
                    timeout=DEFAULT_TIMEOUT,
                    allow_redirects=True,
                )
                res2.raise_for_status()
                html2 = res2.text

                if "Dashboard.php" in (res2.url or "") or "Logout" in html2:
                    self._logged_in = True
                    m2 = re.search(
                        r'name=["\']FormID["\']\s+value=["\']([^"\']+)["\']', html2
                    )
                    self._form_id = m2.group(1) if m2 else form_id
                    self.log(f"Login successful! FormID: {self._form_id[:12]}...")
                    return self

                raise ValueError(f"Login failed — ended at: {res2.url}")

            except Exception as e:
                self.log(f"Attempt {attempt} failed: {e}")
                if attempt < max_retries:
                    time.sleep(retry_delay)
                else:
                    raise RuntimeError(
                        f"Could not login after {max_retries} attempts"
                    ) from e

    def get(self, path, timeout=DEFAULT_TIMEOUT):
        """HTTP GET with retry."""
        url = f"{BASE_URL}{path}" if path.startswith("/") else f"{BASE_URL}/{path}"
        for attempt in range(1, MAX_RETRIES + 1):
            if not self._logged_in:
                self.login()
            try:
                res = self.session.get(url, timeout=timeout)
                res.raise_for_status()
                if is_login_page(res.text):
                    self.log("GET returned login page — re-authenticating")
                    self._logged_in = False
                    continue
                return res.text
            except Exception as e:
                self.log(f"GET {path} attempt {attempt} failed: {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                else:
                    raise

    def post(self, path, fields: dict, timeout=DEFAULT_TIMEOUT):
        """HTTP POST with retry."""
        url = f"{BASE_URL}{path}" if path.startswith("/") else f"{BASE_URL}/{path}"
        for attempt in range(1, MAX_RETRIES + 1):
            if not self._logged_in:
                self.login()
            try:
                res = self.session.post(url, data=fields, timeout=timeout)
                res.raise_for_status()
                if is_login_page(res.text):
                    self.log("POST returned login page — re-authenticating")
                    self._logged_in = False
                    continue
                return res.text
            except Exception as e:
                self.log(f"POST {path} attempt {attempt} failed: {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                else:
                    raise

    def get_form_id(self, html):
        """Extract FormID from any page's HTML."""
        if not html:
            return self._form_id
        m = re.search(r'name=["\']FormID["\']\s+value=["\']([^"\']+)["\']', html)
        return m.group(1) if m else self._form_id

    @property
    def form_id(self):
        return self._form_id


def get_session() -> ERPSession:
    """Convenience function: create and return an authenticated session."""
    session = ERPSession()
    session.login()
    return session
