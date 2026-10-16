"""
scrape_inventory.py — Extracts all stock items, prices, and valuations.
"""

import re
import os
import csv
import time

from login import get_session, CUTOVER_DATE
from db import get_conn, init_db
from form_post import safe_post

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
INV_DIR = os.path.join(DATA_DIR, "inventory")


def clean(text):
    text = re.sub(r"<[^>]+>", "", str(text))
    return re.sub(r"\s+", " ", text).strip()


def scrape_inventory():
    print("\n" + "=" * 60)
    print("  INVENTORY SCRAPER")
    print("=" * 60)

    os.makedirs(INV_DIR, exist_ok=True)
    init_db()

    session = get_session()
    conn = get_conn()

    print("\n[1/2] Fetching stock item list (SelectProduct.php) ...")
    try:
        html = session.get("/SelectProduct.php")
        form_id = session.get_form_id(html)

        search_html = safe_post(session, "/SelectProduct.php", {
            "FormID": form_id,
            "Keywords": "%",
            "CategoryID": "",
            "Search": "Search Now",
        })

        with open(os.path.join(INV_DIR, "items_raw.html"), "w", encoding="utf-8") as f:
            f.write(search_html)

        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', search_html, re.DOTALL)
        items = []
        for row in rows:
            tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            if len(tds) < 2:
                continue
            vals = [clean(td) for td in tds]
            item_code = vals[0].strip()
            if not item_code or item_code.lower() in ["item", "code", "stock code"]:
                continue

            items.append({
                "item_code": item_code,
                "description": vals[1] if len(vals) > 1 else "",
                "uom": vals[2] if len(vals) > 2 else "",
                "category": vals[3] if len(vals) > 3 else "",
                "stock_qty": vals[4] if len(vals) > 4 else "0",
                "unit_cost": vals[5] if len(vals) > 5 else "0.00",
            })

            conn.execute("""
                INSERT OR REPLACE INTO stock_items
                  (item_code, description, uom, category, stock_qty, unit_cost)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                item_code, vals[1] if len(vals) > 1 else "",
                vals[2] if len(vals) > 2 else "",
                vals[3] if len(vals) > 3 else "",
                vals[4] if len(vals) > 4 else "0",
                vals[5] if len(vals) > 5 else "0.00",
            ))

        conn.commit()

        with open(os.path.join(INV_DIR, "stock_items.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["item_code", "description", "uom", "category", "stock_qty", "unit_cost"])
            w.writeheader()
            w.writerows(items)

        print(f"  {len(items)} stock items saved")

    except Exception as e:
        print(f"  ✗ Inventory error: {e}")

    conn.close()
    print("\n  Inventory scrape complete!")


if __name__ == "__main__":
    scrape_inventory()
