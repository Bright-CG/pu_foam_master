#!/usr/bin/env python3
"""Export customer/supplier master CSVs for ERPNext data import."""

import csv
import os

from db import get_conn, init_db

EXPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "exports")


def export_customers(conn) -> str:
    rows = conn.execute(
        """
        SELECT id, name, phone, address, area, cust_type, credit_limit,
               credit_status, currency, terms, balance_total,
               bal_current, bal_now_due, bal_30_60, bal_over_60
        FROM customers
        ORDER BY id
        """
    ).fetchall()
    path = os.path.join(EXPORT_DIR, "erpnext_customers.csv")
    fields = [
        "legacy_customer_id",
        "customer_name",
        "phone",
        "address_line1",
        "area",
        "customer_type",
        "credit_limit",
        "credit_status",
        "default_currency",
        "payment_terms",
        "balance_total",
        "balance_current",
        "balance_now_due",
        "balance_30_60",
        "balance_over_60",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(fields)
        for r in rows:
            w.writerow(
                [
                    r["id"],
                    r["name"],
                    r["phone"] or "",
                    r["address"] or "",
                    r["area"] or "",
                    r["cust_type"] or "",
                    r["credit_limit"] or "",
                    r["credit_status"] or "",
                    r["currency"] or "NGN",
                    r["terms"] or "",
                    r["balance_total"] or "",
                    r["bal_current"] or "",
                    r["bal_now_due"] or "",
                    r["bal_30_60"] or "",
                    r["bal_over_60"] or "",
                ]
            )
    return path


def export_suppliers(conn) -> str:
    rows = conn.execute(
        """
        SELECT id, name, phone, address, currency, terms, balance_total
        FROM suppliers
        ORDER BY id
        """
    ).fetchall()
    path = os.path.join(EXPORT_DIR, "erpnext_suppliers.csv")
    fields = [
        "legacy_supplier_id",
        "supplier_name",
        "phone",
        "address_line1",
        "default_currency",
        "payment_terms",
        "balance_total",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(fields)
        for r in rows:
            w.writerow(
                [
                    r["id"],
                    r["name"],
                    r["phone"] or "",
                    r["address"] or "",
                    r["currency"] or "NGN",
                    r["terms"] or "",
                    r["balance_total"] or "",
                ]
            )
    return path


def main():
    init_db()
    os.makedirs(EXPORT_DIR, exist_ok=True)
    conn = get_conn()
    cust = export_customers(conn)
    supp = export_suppliers(conn)
    conn.close()
    print("Exported:")
    print(" ", cust)
    print(" ", supp)


if __name__ == "__main__":
    main()
