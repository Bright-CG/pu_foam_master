# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

"""Import Density Configuration recipes from a Report/Export CSV.

Usage on the VPS (copy CSV onto the server first):

  bench --site erp.happifoam.com execute \\
    pu_foam_master.utils.import_density_configs.run \\
    --kwargs "{'csv_path': '/home/deployuser/Density Config.csv', 'company': 'Solar Foam and Chemical Industries Limited', 'submit': 1}"

Rules:
  - Chemical Items must already exist (exact Item Code match).
  - Imports as Draft, then optionally Submits (Submit creates virtual Item + BOM).
  - Saving alone does NOT create a BOM — only Submit does.
  - Skips densities that already exist.
"""

from __future__ import annotations

import csv
from pathlib import Path

import frappe
from frappe.utils import cint, flt


def run(csv_path=None, company=None, submit=1, create_missing_items=0):
	"""
	:param csv_path: absolute path to Density Config.csv on the server
	:param company: Company name to stamp on every density (required on fresh site)
	:param submit: 1 = submit after insert (creates BOM); 0 = leave Draft
	:param create_missing_items: 1 = auto-create missing chemical Items as Raw Material stock items
	"""
	frappe.connect()
	frappe.set_user("Administrator")

	if not csv_path:
		frappe.throw("csv_path is required (absolute path to Density Config.csv on the server).")
	path = Path(csv_path)
	if not path.is_file():
		frappe.throw("CSV not found: {0}".format(csv_path))

	company = (company or "").strip() or frappe.db.get_single_value(
		"Pufm Manufacturing Settings", "default_company"
	)
	if not company or not frappe.db.exists("Company", company):
		frappe.throw("Valid company is required (pass company=...).")

	densities = _parse_density_csv(path)
	if not densities:
		frappe.throw("No density rows found in CSV.")

	missing_items = sorted(
		{
			row["item_code"]
			for dens in densities.values()
			for row in dens["inputs"]
			if row.get("item_code") and not frappe.db.exists("Item", row["item_code"])
		}
	)
	if missing_items and not cint(create_missing_items):
		frappe.throw(
			"Create these Items first (or pass create_missing_items=1):\n- {0}".format(
				"\n- ".join(missing_items)
			)
		)
	if missing_items and cint(create_missing_items):
		for code in missing_items:
			_ensure_chemical_item(code)
		print("Created {0} missing chemical Item(s).".format(len(missing_items)))

	created = submitted = skipped = errors = 0
	for density_name, payload in densities.items():
		try:
			if frappe.db.exists("Density Configuration", density_name):
				print("SKIP (exists): {0}".format(density_name))
				skipped += 1
				continue

			doc = frappe.new_doc("Density Configuration")
			doc.density_name = density_name
			doc.company = company
			doc.blow_index = payload.get("blow_index")
			doc.conveyor_speed = payload["conveyor_speed"]
			doc.calibration_factor = payload["calibration_factor"]
			doc.width_inches = payload["width_inches"]
			doc.height_inches = payload["height_inches"]

			for row in payload["inputs"]:
				doc.append(
					"production_inputs",
					{
						"item_code": row["item_code"],
						"flow_factor": row["flow_factor"],
						"set_at": row["set_at"],
					},
				)

			for row in payload.get("operations") or []:
				if not row.get("operation"):
					continue
				_ensure_operation(row["operation"])
				op_row = {
					"operation": row["operation"],
					"hour_rate": row.get("hour_rate") or 0,
				}
				if row.get("workstation") and frappe.db.exists("Workstation", row["workstation"]):
					op_row["workstation"] = row["workstation"]
				doc.append("bom_operations", op_row)

			doc.insert(ignore_permissions=True)
			created += 1
			print("CREATED draft: {0}".format(doc.name))

			if cint(submit):
				doc.reload()
				doc.submit()
				submitted += 1
				print(
					"  SUBMITTED → virtual_item={0} active_bom={1}".format(
						doc.virtual_item, doc.active_bom
					)
				)
		except Exception as e:
			errors += 1
			frappe.db.rollback()
			frappe.log_error(title="Density import failed: {0}".format(density_name))
			print("ERROR {0}: {1}".format(density_name, e))

	frappe.db.commit()
	summary = {
		"created": created,
		"submitted": submitted,
		"skipped": skipped,
		"errors": errors,
		"densities_in_csv": len(densities),
	}
	print("DONE", summary)
	return summary


def _parse_density_csv(path: Path):
	with path.open(newline="", encoding="utf-8-sig") as f:
		reader = csv.DictReader(f)
		rows = list(reader)

	densities = {}
	current = None
	for r in rows:
		name = (r.get("Density") or "").strip()
		if name:
			current = name
			densities[current] = {
				"blow_index": flt(r.get("Blow Index")),
				"conveyor_speed": flt(r.get("Conveyor Speed")),
				"calibration_factor": flt(r.get("Calibration Factor") or 1),
				"width_inches": flt(r.get("Width Inches")),
				"height_inches": flt(r.get("Height Inches")),
				"inputs": [],
				"operations": [],
			}

		if not current:
			continue

		item = (r.get("Input (Production Inputs)") or "").strip()
		if item:
			densities[current]["inputs"].append(
				{
					"item_code": item,
					"flow_factor": flt(r.get("Flow Factor (Production Inputs)")),
					"set_at": flt(r.get("Set At (Production Inputs)")),
				}
			)

		operation = (r.get("Operation (Operations)") or "").strip()
		if operation:
			densities[current]["operations"].append(
				{
					"operation": operation,
					"hour_rate": flt(r.get("Hourly Cost (Operations)")),
					"workstation": (r.get("Workstation (Operations)") or "").strip(),
				}
			)

	return densities


def _ensure_chemical_item(item_code):
	if frappe.db.exists("Item", item_code):
		return
	group = "Raw Material"
	if not frappe.db.exists("Item Group", group):
		group = "Products"
	item = frappe.new_doc("Item")
	item.item_code = item_code
	item.item_name = item_code
	item.item_group = group
	item.stock_uom = "Kg"
	item.is_stock_item = 1
	item.include_item_in_manufacturing = 1
	item.insert(ignore_permissions=True)


def _ensure_operation(operation):
	if frappe.db.exists("Operation", operation):
		return
	doc = frappe.new_doc("Operation")
	doc.operation = operation
	doc.insert(ignore_permissions=True)
