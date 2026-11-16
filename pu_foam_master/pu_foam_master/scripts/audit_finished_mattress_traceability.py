# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

"""Audit / fix finished-mattress Item traceability (batch-only).

Usage:
  bench --site <site> execute \\
    pu_foam_master.scripts.audit_finished_mattress_traceability.run

  bench --site <site> execute \\
    pu_foam_master.scripts.audit_finished_mattress_traceability.run \\
    --kwargs '{"csv_path": "/path/to/Item.csv", "apply_fix": true}'
"""

from __future__ import annotations

import csv
from pathlib import Path

import frappe
from frappe.utils import cint

from pu_foam_master.pufm_manufacturing.utils.item_traceability import (
	list_finished_mattress_item_codes,
)
from pu_foam_master.setup_migrations import disable_finished_mattress_serials


def run(csv_path=None, apply_fix=False):
	"""Report Items that still have serial tracking; optionally run migrate fix."""
	if apply_fix:
		disable_finished_mattress_serials()

	site_codes = list_finished_mattress_item_codes()
	bad = []
	for code in site_codes:
		row = frappe.db.get_value(
			"Item",
			code,
			["has_serial_no", "has_batch_no", "create_new_batch"],
			as_dict=True,
		)
		if not row:
			continue
		if cint(row.has_serial_no) or not cint(row.has_batch_no):
			bad.append({**row, "item_code": code})

	csv_stats = None
	if csv_path:
		csv_stats = _audit_csv(Path(csv_path))

	result = {
		"finished_mattress_count": len(site_codes),
		"still_serial_or_not_batch": bad,
		"csv_audit": csv_stats,
	}
	print(frappe.as_json(result, indent=1))
	return result


def _audit_csv(path: Path):
	if not path.is_file():
		return {"error": f"File not found: {path}"}

	finished = 0
	serial_on = 0
	missing_in_site = []
	with path.open(encoding="utf-8", newline="") as handle:
		reader = csv.reader(handle)
		started = False
		for row in reader:
			if not started:
				if row and "Start entering data below" in (row[0] or ""):
					started = True
				continue
			if len(row) < 45:
				continue
			item_code = (row[2] or row[1] or "").strip().strip('"')
			if not item_code:
				continue
			finish = (row[12] or "").strip() if len(row) > 12 else ""
			upper = item_code.upper()
			is_finished = finish in (
				"Plain",
				"Side Quilted",
				"Fully Quilted",
			) or any(upper.endswith(s) for s in ("-PLAIN", "-SQ", "-FQ"))
			if not is_finished or upper.endswith("-CORE") or item_code.endswith(" Block"):
				continue
			finished += 1
			has_serial = cint(row[44])
			if has_serial:
				serial_on += 1
			if not frappe.db.exists("Item", item_code):
				missing_in_site.append(item_code)

	return {
		"csv_finished_rows": finished,
		"csv_has_serial_yes": serial_on,
		"missing_on_site": missing_in_site[:20],
		"missing_on_site_count": len(missing_in_site),
	}