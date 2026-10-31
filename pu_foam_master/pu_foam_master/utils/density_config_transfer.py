# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

"""Export / import Density Configuration recipes between sites (always as Draft on import).

BOMs and virtual Items are created only on Submit — import with submit=0 (default).

Demo site (export):
  bench --site demo.site execute pu_foam_master.utils.density_config_transfer.export_json \\
    --kwargs "{'json_path': '/tmp/density_configs.json'}"

Live site (check Items first):
  bench --site live.site execute pu_foam_master.utils.density_config_transfer.list_prerequisites \\
    --kwargs "{'json_path': '/tmp/density_configs.json'}"

Live site (import drafts):
  bench --site live.site execute pu_foam_master.utils.density_config_transfer.import_json \\
    --kwargs "{'json_path': '/tmp/density_configs.json', 'company': 'Happifoam', 'submit': 0}"
"""

from __future__ import annotations

import json
from pathlib import Path

import frappe
from frappe.utils import cint, flt


def export_json(json_path=None, include_cancelled=0):
	"""Write all Density Configuration recipes to a JSON file."""
	frappe.connect()
	if not json_path:
		frappe.throw("json_path is required (absolute path on the server).")
	path = Path(json_path)
	filters = {}
	if not cint(include_cancelled):
		filters["docstatus"] = ("!=", 2)

	names = frappe.get_all(
		"Density Configuration",
		filters=filters,
		pluck="name",
		order_by="density_name asc",
	)
	records = []
	for name in names:
		doc = frappe.get_doc("Density Configuration", name)
		records.append(_serialize_density(doc))

	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(json.dumps(records, indent=2, default=str), encoding="utf-8")
	summary = {
		"exported": len(records),
		"json_path": str(path),
		"docstatus_note": "Includes submitted and draft; cancelled excluded unless include_cancelled=1.",
	}
	print(json.dumps(summary, indent=2))
	return summary


def list_prerequisites(json_path=None):
	"""Print Items, Operations, Workstations, and Brands required by an export file."""
	frappe.connect()
	records = _load_json(json_path)
	items = set()
	operations = set()
	workstations = set()
	brands = set()
	for rec in records:
		if rec.get("brand"):
			brands.add(rec["brand"])
		for row in rec.get("production_inputs") or []:
			code = (row.get("item_code") or "").strip()
			if code:
				items.add(code)
		for row in rec.get("bom_operations") or []:
			op = (row.get("operation") or "").strip()
			if op:
				operations.add(op)
			ws = (row.get("workstation") or "").strip()
			if ws:
				workstations.add(ws)

	missing_items = sorted(i for i in items if not frappe.db.exists("Item", i))
	missing_ops = sorted(o for o in operations if not frappe.db.exists("Operation", o))
	missing_ws = sorted(w for w in workstations if not frappe.db.exists("Workstation", w))
	missing_brands = sorted(b for b in brands if not frappe.db.exists("Brand", b))

	report = {
		"densities_in_file": len(records),
		"density_names": [r.get("density_name") for r in records],
		"items_required": sorted(items),
		"operations_required": sorted(operations),
		"workstations_required": sorted(workstations),
		"brands_required": sorted(brands),
		"missing_on_this_site": {
			"items": missing_items,
			"operations": missing_ops,
			"workstations": missing_ws,
			"brands": missing_brands,
		},
	}
	print(json.dumps(report, indent=2))
	return report


def import_json(
	json_path=None,
	company=None,
	submit=0,
	skip_existing=1,
	update_draft=0,
):
	"""Import recipes from export JSON. Default: Draft only (no BOM / virtual Item)."""
	frappe.connect()
	frappe.set_user("Administrator")

	records = _load_json(json_path)
	company = (company or "").strip() or frappe.db.get_single_value(
		"Pufm Manufacturing Settings", "default_company"
	)
	if not company or not frappe.db.exists("Company", company):
		frappe.throw("Valid company is required (pass company='Your Company').")

	created = updated = skipped = submitted = errors = 0
	for rec in records:
		density_name = (rec.get("density_name") or rec.get("name") or "").strip()
		if not density_name:
			errors += 1
			continue
		try:
			if frappe.db.exists("Density Configuration", density_name):
				existing_status = cint(
					frappe.db.get_value("Density Configuration", density_name, "docstatus")
				)
				if existing_status == 1 and not cint(update_draft):
					print("SKIP (submitted exists): {0}".format(density_name))
					skipped += 1
					continue
				if existing_status == 0 and cint(update_draft):
					doc = frappe.get_doc("Density Configuration", density_name)
					_apply_density_payload(doc, rec, company)
					doc.save(ignore_permissions=True)
					updated += 1
					print("UPDATED draft: {0}".format(density_name))
				elif cint(skip_existing):
					print("SKIP (exists): {0}".format(density_name))
					skipped += 1
					continue
				else:
					frappe.throw("Density {0} already exists.".format(density_name))

			if not frappe.db.exists("Density Configuration", density_name):
				doc = frappe.new_doc("Density Configuration")
				_apply_density_payload(doc, rec, company)
				doc.insert(ignore_permissions=True)
				created += 1
				print("CREATED draft: {0}".format(doc.name))

			if cint(submit):
				doc = frappe.get_doc("Density Configuration", density_name)
				if doc.docstatus == 0:
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
			frappe.log_error(title="Density JSON import failed: {0}".format(density_name))
			print("ERROR {0}: {1}".format(density_name, e))

	frappe.db.commit()
	summary = {
		"created": created,
		"updated": updated,
		"skipped": skipped,
		"submitted": submitted,
		"errors": errors,
		"records_in_file": len(records),
	}
	print("DONE", summary)
	return summary


def _load_json(json_path):
	if not json_path:
		frappe.throw("json_path is required.")
	path = Path(json_path)
	if not path.is_file():
		frappe.throw("JSON not found: {0}".format(json_path))
	data = json.loads(path.read_text(encoding="utf-8"))
	if isinstance(data, dict) and "records" in data:
		return data["records"]
	if isinstance(data, list):
		return data
	frappe.throw("JSON must be a list of density records or {records: [...]}.")


def _serialize_density(doc):
	return {
		"density_name": doc.density_name,
		"brand": doc.brand,
		"width_inches": flt(doc.width_inches),
		"height_inches": flt(doc.height_inches),
		"conveyor_speed": flt(doc.conveyor_speed),
		"calibration_factor": flt(doc.calibration_factor or 1),
		"blow_index": flt(doc.blow_index),
		"target_block_lengths": doc.target_block_lengths,
		"production_inputs": [
			{
				"item_code": row.item_code,
				"flow_factor": flt(row.flow_factor),
				"set_at": flt(row.set_at),
			}
			for row in doc.get("production_inputs") or []
			if row.item_code
		],
		"bom_operations": [
			{
				"operation": row.operation,
				"workstation": row.workstation,
				"hour_rate": flt(row.get("hour_rate")),
			}
			for row in doc.get("bom_operations") or []
			if row.operation
		],
		"_source_docstatus": cint(doc.docstatus),
		"_source_virtual_item": doc.virtual_item,
		"_source_active_bom": doc.active_bom,
	}


def _apply_density_payload(doc, rec, company):
	doc.density_name = rec.get("density_name") or doc.density_name
	doc.company = company
	doc.brand = rec.get("brand")
	doc.width_inches = flt(rec.get("width_inches"))
	doc.height_inches = flt(rec.get("height_inches"))
	doc.conveyor_speed = flt(rec.get("conveyor_speed"))
	doc.calibration_factor = flt(rec.get("calibration_factor") or 1)
	doc.blow_index = flt(rec.get("blow_index"))
	doc.target_block_lengths = rec.get("target_block_lengths")

	doc.set("production_inputs", [])
	for row in rec.get("production_inputs") or []:
		code = (row.get("item_code") or "").strip()
		if not code:
			continue
		if not frappe.db.exists("Item", code):
			frappe.throw(
				"Item {0} missing on site (create it before import).".format(code)
			)
		doc.append(
			"production_inputs",
			{
				"item_code": code,
				"flow_factor": flt(row.get("flow_factor")),
				"set_at": flt(row.get("set_at")),
			},
		)

	doc.set("bom_operations", [])
	for row in rec.get("bom_operations") or []:
		op = (row.get("operation") or "").strip()
		if not op:
			continue
		if not frappe.db.exists("Operation", op):
			frappe.new_doc("Operation").update({"operation": op}).insert(
				ignore_permissions=True
			)
		op_row = {"operation": op, "hour_rate": flt(row.get("hour_rate"))}
		ws = (row.get("workstation") or "").strip()
		if ws and frappe.db.exists("Workstation", ws):
			op_row["workstation"] = ws
		doc.append("bom_operations", op_row)
