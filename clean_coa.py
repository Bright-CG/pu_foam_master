#!/usr/bin/env python3
"""Clean SolarFoam Chart of Accounts export for ERPNext Data Import.

Reads Account.csv (legacy export), applies the agreed CoA transformations,
and writes Clean_Account.csv with the original ERPNext template header intact.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "Account.csv"
OUTPUT = ROOT / "Clean_Account.csv"

COMPANY = "SOLAR FOAM AND CHEMICAL INDUSTRIES NIGERIA LIMITED"
ABBR = "SolarFoam"

# ERPNext template = notes + DocType/Column rows + "Start entering data..."
# (rows 1-20). Skipping only the first 14 would drop Column Labels/Name,
# which the importer needs.
DATA_START_LINE = 20  # 0-based: first data row

AR_CLONE_NEEDLES = ("200-14", "200-15", "200-16", "200-17")
FG_SKU_NUMBERS = {f"200-24{i}" for i in range(1, 10)}  # 200-241 .. 200-249

ADMIN_PARENT = "900-200 - ADMINISTRATIVE EXPENSES - SolarFoam"
DIRECT_LABOUR_PARENT = "900-120 - Direct Labour - SolarFoam"
FG_GROUP_NUMBER = "200-240"
VAT_NAME = "VAT"

NEW_SYSTEM_ACCOUNTS = [
    {
        "number": "500-127",
        "account_name": "Stock Received But Not Billed",
        "parent": "500-110 - Accounts Payable - SolarFoam",
        "root_type": "Liability",
        "report_type": "Balance Sheet",
        "account_type": "Stock Received But Not Billed",
    },
    {
        "number": "900-101",
        "account_name": "Cost of Goods Sold",
        "parent": "900-100 - DIRECT COST - SolarFoam",
        "root_type": "Expense",
        "report_type": "Profit and Loss",
        "account_type": "Cost of Goods Sold",
    },
    {
        "number": "900-244",
        "account_name": "Round Off",
        "parent": "900-200 - ADMINISTRATIVE EXPENSES - SolarFoam",
        "root_type": "Expense",
        "report_type": "Profit and Loss",
        "account_type": "Round Off",
    },
]

PUFM_ABSORPTION = [
    ("900-053", "Power Absorption"),
    ("900-054", "Diesel Absorption"),
    ("900-055", "Labour Absorption"),
    ("900-056", "Depreciation Absorption"),
    ("900-057", "Conversion Absorption"),
    ("900-058", "Quilting Absorption"),
]
PUFM_PARENT = "900-050 - Production Costs - SolarFoam"
# Live parent ID in the source file (title case, not ALL CAPS).
REBATE_PARENT = "900-400 - Selling and Distribution Expenses - SolarFoam"


def _strip_quotes(value) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return text[1:-1]
    return text


def _make_id(number: str, account_name: str) -> str:
    return f"{number} - {account_name} - {ABBR}"


def _blank_row(columns: list[str]) -> dict:
    return {col: "" for col in columns}


def _ledger_row(columns: list[str], spec: dict) -> dict:
    row = _blank_row(columns)
    number = spec["number"]
    name = spec["account_name"]
    row[""] = ""
    row["ID"] = _make_id(number, name)
    row["Account Name"] = name
    row["Company"] = COMPANY
    row["Parent Account"] = spec["parent"]
    row["Created On"] = ""
    row["Created By"] = "Administrator"
    row["Disable"] = 0
    row["Account Number"] = number
    row["Is Group"] = 0
    row["Root Type"] = spec["root_type"]
    row["Report Type"] = spec["report_type"]
    row["Currency"] = "NGN"
    row["Account Type"] = spec["account_type"]
    row["Tax Rate"] = ""
    row["Frozen"] = "No"
    row["Balance must be"] = ""
    row["Include in gross"] = 0
    return row


def load_source() -> tuple[list[str], pd.DataFrame]:
    raw_lines = SOURCE.read_text(encoding="utf-8").splitlines(keepends=True)
    metadata = raw_lines[:DATA_START_LINE]

    df = pd.read_csv(
        SOURCE,
        skiprows=14,
        header=0,
        dtype=str,
        keep_default_na=False,
    )
    # skiprows=14 makes "Column Labels:" the header row.
    df = df.rename(columns={"Column Labels:": ""})

    # Drop template helper rows that sit between Column Labels and data.
    id_series = df["ID"].map(_strip_quotes)
    drop_ids = {"", "ID", "name", "Yes", "Data"}
    template_mask = id_series.isin(drop_ids) | id_series.str.startswith("One of:")
    start_mask = df.apply(
        lambda r: "Start entering data" in " ".join(str(v) for v in r.values),
        axis=1,
    )
    df = df.loc[~(template_mask | start_mask)].copy()
    df["ID"] = df["ID"].map(_strip_quotes)
    df["Parent Account"] = df["Parent Account"].map(_strip_quotes)
    df["Account Name"] = df["Account Name"].map(_strip_quotes)
    return metadata, df.reset_index(drop=True)


def drop_ar_clones(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    mask = df["ID"].apply(lambda x: any(needle in x for needle in AR_CLONE_NEEDLES))
    deleted = df.loc[mask].copy()
    return df.loc[~mask].copy(), deleted


def rename_admin_payroll_clones(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    direct_names = set(
        df.loc[df["Parent Account"] == DIRECT_LABOUR_PARENT, "Account Name"]
    )
    renamed = []

    def _rename(row):
        if row["Parent Account"] != ADMIN_PARENT:
            return row
        if row["Account Name"] not in direct_names:
            return row
        old_name = row["Account Name"]
        new_name = f"{old_name} - Admin"
        row["Account Name"] = new_name
        row["ID"] = _make_id(row["Account Number"], new_name)
        renamed.append(f"{row['Account Number']} {old_name} -> {new_name}")
        return row

    return df.apply(_rename, axis=1), renamed


def collapse_finished_goods(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    sku_mask = df["Account Number"].isin(FG_SKU_NUMBERS)
    deleted = df.loc[sku_mask].copy()
    df = df.loc[~sku_mask].copy()
    fg_mask = df["Account Number"] == FG_GROUP_NUMBER
    df.loc[fg_mask, "Is Group"] = "0"
    return df, deleted


def fix_vat(df: pd.DataFrame) -> int:
    mask = (df["Account Name"] == VAT_NAME) | df["ID"].str.contains(
        "VAT - SolarFoam", regex=False
    )
    df.loc[mask, "Tax Rate"] = ""
    df.loc[mask, "Account Type"] = "Tax"
    return int(mask.sum())


def append_missing(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    columns = list(df.columns)
    added = []
    new_rows = []

    for spec in NEW_SYSTEM_ACCOUNTS:
        new_rows.append(_ledger_row(columns, spec))
        added.append(_make_id(spec["number"], spec["account_name"]))

    for number, name in PUFM_ABSORPTION:
        spec = {
            "number": number,
            "account_name": name,
            "parent": PUFM_PARENT,
            "root_type": "Expense",
            "report_type": "Profit and Loss",
            "account_type": "Expense Account",
        }
        new_rows.append(_ledger_row(columns, spec))
        added.append(_make_id(number, name))

    rebate = {
        "number": "900-406",
        "account_name": "Customer Volume Rebates",
        "parent": REBATE_PARENT,
        "root_type": "Expense",
        "report_type": "Profit and Loss",
        "account_type": "Expense Account",
    }
    new_rows.append(_ledger_row(columns, rebate))
    added.append(_make_id("900-406", "Customer Volume Rebates"))

    return pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True), added


def write_output(metadata: list[str], df: pd.DataFrame) -> None:
    # Recreate ERPNext import rows: leading blank cell, then field values.
    fieldnames = list(df.columns)
    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        handle.writelines(metadata)
        writer = csv.writer(handle, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        for _, row in df.iterrows():
            writer.writerow([row.get(col, "") for col in fieldnames])


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"Missing source file: {SOURCE}")

    metadata, df = load_source()
    start_count = len(df)

    df, ar_deleted = drop_ar_clones(df)
    df, renamed = rename_admin_payroll_clones(df)
    df, fg_deleted = collapse_finished_goods(df)
    vat_fixed = fix_vat(df)
    df, added = append_missing(df)

    write_output(metadata, df)

    print("=== CoA cleanup summary ===")
    print(f"Source rows:              {start_count}")
    print(f"AR/debtor clones dropped: {len(ar_deleted)}")
    for _, row in ar_deleted.iterrows():
        print(f"  - {row['ID']}")
    print(f"FG SKU ledgers dropped:   {len(fg_deleted)}")
    for _, row in fg_deleted.iterrows():
        print(f"  - {row['ID']}")
    print(f"Admin payroll renamed:    {len(renamed)}")
    for item in renamed:
        print(f"  - {item}")
    print(f"VAT rows updated:         {vat_fixed}")
    print(f"Accounts added:           {len(added)}")
    for item in added:
        print(f"  + {item}")
    print(f"Output rows:              {len(df)}")
    print(f"Wrote:                    {OUTPUT}")


if __name__ == "__main__":
    main()
