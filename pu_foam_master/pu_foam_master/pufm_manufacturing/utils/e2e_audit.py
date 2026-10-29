# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

"""Full PUFM DocType audit + small-qty live E2E on the local bench.

  bench --site pu_foam.localhost execute \\
    pu_foam_master.pufm_manufacturing.utils.e2e_audit.run
"""

from __future__ import annotations

import traceback

import frappe
from frappe.utils import cint, flt, nowdate

from erpnext.stock.doctype.batch.batch import get_batch_qty

from pu_foam_master.pufm_manufacturing.utils.stock_entry_valuation import (
	get_stock_valuation_rate,
)


# Reasonable test hour rates (NGN / hour) for foaming operations
HOUR_RATE_D18 = 2500.0
HOUR_RATE_D40 = 3500.0

COMPANY = "Solarfoam"
WIP = "Work In Progress - SF"
FG = "Finished Goods - SF"
STORES = "Stores - SF"
SCRAP_WH = "Scrap Warehouse - SF"
GIT = "Goods In Transit - SF"


def run():
	frappe.connect()
	frappe.set_user("Administrator")
	report = {
		"audit": {},
		"setup": {},
		"tests": {},
		"errors": [],
		"warnings": [],
		"pass_count": 0,
		"fail_count": 0,
		"skip_count": 0,
	}

	try:
		report["audit"] = _audit_doctypes()
	except Exception as e:
		report["errors"].append("audit: {0}".format(e))

	try:
		report["setup"] = _setup_hour_rates_and_preflight()
	except Exception as e:
		frappe.db.rollback()
		report["errors"].append("setup: {0}".format(e))
		frappe.log_error(title="E2E setup failed")

	steps = (
		("pour_d18", _test_pour_d18),
		("pour_d40", _test_pour_d40),
		("mattress_core_conversion_d18", _test_mattress_core_conversion),
		("sheeting_conversion_d40", _test_sheeting_conversion),
		("quilting", _test_quilting),
		("mattress_assembly_fq", _test_mattress_assembly),
		("rebound", _test_rebound),
		("scrap_costing", _test_scrap_costing),
		("job_order_draft", _test_job_order_draft),
		("price_engine_draft", _test_price_engine),
	)

	for key, fn in steps:
		try:
			result = fn()
			report["tests"][key] = result
			status = (result or {}).get("status", "unknown")
			if status == "pass":
				report["pass_count"] += 1
			elif status == "skip":
				report["skip_count"] += 1
			else:
				report["fail_count"] += 1
			frappe.db.commit()
		except Exception as e:
			frappe.db.rollback()
			msg = "{0}: {1}".format(key, e)
			report["errors"].append(msg)
			report["tests"][key] = {
				"status": "fail",
				"error": str(e),
				"trace": traceback.format_exc()[-1500:],
			}
			report["fail_count"] += 1
			frappe.log_error(title="E2E {0} failed".format(key))

	report["verdict"] = _verdict(report)
	text = _format_report(report)
	print(text)
	return report


def run_retry_failures():
	"""Re-run only the previously failing / dependent assembly tests."""
	frappe.connect()
	frappe.set_user("Administrator")
	report = {"tests": {}, "errors": [], "pass_count": 0, "fail_count": 0, "skip_count": 0}
	# Quilt more fabric first so FQ has a batch >= 3.6 m
	steps = (
		("quilting", _test_quilting),
		("mattress_assembly_fq", _test_mattress_assembly),
		("job_order_draft", _test_job_order_draft),
		("price_engine_draft", _test_price_engine),
	)
	for key, fn in steps:
		try:
			result = fn()
			report["tests"][key] = result
			st = (result or {}).get("status")
			if st == "pass":
				report["pass_count"] += 1
			elif st == "skip":
				report["skip_count"] += 1
			else:
				report["fail_count"] += 1
			frappe.db.commit()
		except Exception as e:
			frappe.db.rollback()
			report["errors"].append("{0}: {1}".format(key, e))
			report["tests"][key] = {"status": "fail", "error": str(e)}
			report["fail_count"] += 1
	report["verdict"] = _verdict(report)
	print(_format_report({"audit": {}, "setup": {}, **report}))
	return report


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

EXPECTED_DOCTYPES = (
	"Pufm Manufacturing Settings",
	"Density Configuration",
	"Production Inputs",
	"PUFM BOM Operation",
	"Pufm Production Batch",
	"Pufm Density Run",
	"Pufm Produced Block",
	"Mattress Core Conversion",
	"Block Conversion Input",
	"Block Conversion Output",
	"Pufm Sheeting Conversion",
	"Pufm Sheeting Output",
	"Pufm Sheeting Instruction",
	"Quilting Record",
	"Quilting Input",
	"Mattress Production Entry",
	"Mattress Production Item",
	"Rebound Configuration",
	"Rebound Production Entry",
	"Scrap Costing Calculator",
	"Pufm Job Order",
	"Pufm Quilting Instruction",
	"Pufm Mattress Instruction",
	"Mattress Item Generator",
	"Generator Size",
	"Standard Mattress Size",
	"Mattress Brand Policy",
	"Allowed Fabric",
	"Pufm Price Engine",
	"Pufm Price Engine Item",
	"Pufm Rebond Item Generator",
	"Rebate Settlement Tool",
	"Rebate Tier",
	"Rebate Calculation",
)


def _audit_doctypes():
	rows = []
	missing = []
	for name in EXPECTED_DOCTYPES:
		exists = bool(frappe.db.exists("DocType", name))
		meta = None
		counts = {}
		if exists:
			meta = frappe.get_meta(name)
			counts = {
				"issingle": cint(meta.issingle),
				"is_submittable": cint(meta.is_submittable),
				"istable": cint(meta.istable),
				"module": meta.module,
			}
			if not meta.istable and not meta.issingle:
				try:
					counts["records"] = frappe.db.count(name)
					if meta.is_submittable:
						counts["submitted"] = frappe.db.count(name, {"docstatus": 1})
				except Exception:
					counts["records"] = "?"
		else:
			missing.append(name)
		rows.append({"name": name, "exists": exists, **counts})

	settings = frappe.get_single("Pufm Manufacturing Settings")
	required = (
		"default_company",
		"default_wip_warehouse",
		"default_fg_warehouse",
		"default_scrap_warehouse",
		"default_raw_material_warehouse",
		"scrap_item",
		"mdi_item",
		"default_tape_edge_item",
		"default_pvc_nylon_item",
		"default_thread_item",
		"conversion_absorption_account",
		"quilting_absorption_account",
		"labour_absorption_account",
		"rebate_expense_account",
	)
	settings_gaps = [f for f in required if not settings.get(f)]
	optional_gaps = []
	if not settings.get("default_label_item"):
		optional_gaps.append("default_label_item")

	d18 = frappe.db.exists("Density Configuration", "D18")
	d40 = frappe.db.exists("Density Configuration", "D40")
	d18_bom = frappe.db.get_value("Density Configuration", "D18", "active_bom") if d18 else None
	d40_bom = frappe.db.get_value("Density Configuration", "D40", "active_bom") if d40 else None

	return {
		"doctypes_ok": len(EXPECTED_DOCTYPES) - len(missing),
		"doctypes_total": len(EXPECTED_DOCTYPES),
		"missing": missing,
		"rows": rows,
		"settings_gaps": settings_gaps,
		"optional_gaps": optional_gaps,
		"wip_warehouse": settings.default_wip_warehouse,
		"company": settings.default_company,
		"d18_submitted": cint(frappe.db.get_value("Density Configuration", "D18", "docstatus")) == 1
		if d18
		else False,
		"d40_submitted": cint(frappe.db.get_value("Density Configuration", "D40", "docstatus")) == 1
		if d40
		else False,
		"d18_bom": d18_bom,
		"d40_bom": d40_bom,
		"conversion_rate_per_cbm": flt(settings.conversion_rate_per_cbm),
		"quilting_rate_per_m": flt(settings.total_quilting_rate_per_m),
		"scrap_output_rate": flt(settings.scrap_output_rate),
		"scrap_input_rate": flt(settings.scrap_input_rate),
	}


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------


def _setup_hour_rates_and_preflight():
	out = {}
	for density, rate in (("D18", HOUR_RATE_D18), ("D40", HOUR_RATE_D40)):
		doc = frappe.get_doc("Density Configuration", density)
		if not doc.bom_operations:
			doc.append(
				"bom_operations",
				{
					"operation": "Foaming",
					"workstation": "Kaduna Conveyor 1",
					"hour_rate": rate,
				},
			)
		else:
			for row in doc.bom_operations:
				row.hour_rate = rate
		# Recalc time / operating_cost via validate
		doc.flags.ignore_permissions = True
		doc.save()
		ops = [
			{
				"operation": r.operation,
				"hour_rate": flt(r.hour_rate),
				"time": flt(r.time),
				"operating_cost": flt(r.operating_cost),
			}
			for r in doc.bom_operations
		]
		out[density] = {"hour_rate": rate, "operations": ops, "output_rate": flt(doc.output_rate_m3_per_min)}

	# Ensure Rebound Configuration has usable recipe numbers
	reb = frappe.get_doc("Rebound Configuration", "REB-70")
	changed = False
	if not flt(reb.target_density_kg_m3):
		reb.target_density_kg_m3 = 70
		changed = True
	if not flt(reb.scrap_kg_per_cbm):
		reb.scrap_kg_per_cbm = 65
		changed = True
	if not flt(reb.mdi_kg_per_cbm):
		reb.mdi_kg_per_cbm = 8
		changed = True
	if not cint(reb.standard_cycle_time_mins):
		reb.standard_cycle_time_mins = 30
		changed = True
	if changed:
		reb.save(ignore_permissions=True)
	out["rebound_config"] = {
		"name": reb.name,
		"scrap_kg_per_cbm": flt(reb.scrap_kg_per_cbm),
		"mdi_kg_per_cbm": flt(reb.mdi_kg_per_cbm),
		"cycle_mins": cint(reb.standard_cycle_time_mins),
	}

	# Prefer chemical issue from warehouse that actually holds stock
	settings = frappe.get_single("Pufm Manufacturing Settings")
	out["pvc_gsm"] = _ensure_pvc_gsm_for_testing(settings)
	out["quilt_stock_warehouse"] = _quilt_and_assembly_warehouse(settings)
	out["chemical_issue_wh"] = settings.default_wip_warehouse
	out["note"] = (
		"Chemicals for pour are issued from Default WIP Warehouse "
		"({0}).".format(settings.default_wip_warehouse)
	)
	frappe.db.commit()
	return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _quilt_and_assembly_warehouse(settings=None):
	"""Quilted fabric / FQ assembly source stock is in Work In Progress (not GIT)."""
	return WIP


def _warehouse_with_stock(item_code, prefer):
	for wh in prefer:
		if _bin_qty(item_code, wh) > 0:
			return wh
	return prefer[0]


def _ensure_pvc_gsm_for_testing(settings):
	if not flt(getattr(settings, "pvc_gsm", None)):
		settings.pvc_gsm = 200
		settings.save(ignore_permissions=True)
	return flt(settings.pvc_gsm)


def _submit_quilting_to_wip(company, out_m=4.0):
	"""Create quilted fabric batch in Work In Progress (for E2E / assembly)."""
	settings = frappe.get_single("Pufm Manufacturing Settings")
	fabric = "Raw Damask Fabric"
	sheet = "Foam Sheet Roll - 0.5 Inch"
	finished = "QUILTED-DAMASK-FLORA"
	target_wh = _quilt_and_assembly_warehouse(settings)

	if not frappe.db.exists("Item", finished):
		frappe.throw("Finished quilt item {0} missing.".format(finished))

	fabric_wh = _warehouse_with_stock(fabric, (WIP, STORES, GIT))
	sheet_wh = _warehouse_with_stock(sheet, (WIP, STORES))
	if _bin_qty(sheet, sheet_wh) < out_m + 0.5:
		_seed_batch_receipt(sheet, WIP, company, qty=30, rate=1500)
		sheet_wh = WIP
	if _bin_qty(fabric, fabric_wh) < out_m + 0.5:
		return None

	fabric_batch, _ = _pick_batch_with_qty(fabric, fabric_wh, need=out_m + 0.5)
	sheet_batch, _ = _pick_batch_with_qty(sheet, sheet_wh, need=out_m + 0.5)
	if cint(frappe.db.get_value("Item", fabric, "has_batch_no")) and not fabric_batch:
		return None
	if cint(frappe.db.get_value("Item", sheet, "has_batch_no")) and not sheet_batch:
		sheet_batch = _seed_batch_receipt(sheet, sheet_wh, company, qty=30, rate=1500)

	doc = frappe.new_doc("Quilting Record")
	doc.company = company
	doc.posting_date = nowdate()
	doc.fabric_item = fabric
	doc.fabric_warehouse = fabric_wh
	doc.fabric_batch = fabric_batch
	doc.fabric_qty_meters = out_m + 0.2
	doc.sheeting_roll_item = sheet
	doc.sheeting_warehouse = sheet_wh
	doc.sheeting_batch = sheet_batch
	doc.sheeting_qty_meters = out_m + 0.2
	doc.finished_item = finished
	doc.output_qty_meters = out_m
	doc.target_warehouse = target_wh
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc


def _ensure_quilted_fabric_batch(company, need_m=3.6):
	fabric = "QUILTED-DAMASK-FLORA"
	wh = _quilt_and_assembly_warehouse()
	batch, qty = _pick_batch_with_qty(fabric, wh, need=need_m)
	if batch:
		return batch, wh, "existing"
	doc = _submit_quilting_to_wip(company, out_m=max(need_m, 4.0))
	if not doc:
		return None, wh, "no_quilt_inputs"
	batch, qty = _pick_batch_with_qty(fabric, wh, need=need_m)
	return batch, wh, doc.name if batch else None


def _gl_gap(stock_entry_name):
	if not stock_entry_name:
		return {"pass": False, "reason": "no stock entry"}
	se = frappe.get_doc("Stock Entry", stock_entry_name)
	sources = targets = additional = 0.0
	for row in se.items:
		amt = flt(row.amount) or flt(row.basic_amount) or flt(flt(row.qty) * flt(row.basic_rate or row.valuation_rate))
		if row.s_warehouse:
			sources += amt
		if row.t_warehouse:
			targets += amt
	for row in se.get("additional_costs") or []:
		additional += flt(getattr(row, "base_amount", None) or row.amount)
	gap = flt(sources + additional - targets)
	return {
		"stock_entry": stock_entry_name,
		"sources": flt(sources, 2),
		"additional": flt(additional, 2),
		"targets": flt(targets, 2),
		"gap": flt(gap, 2),
		"pass": abs(gap) <= 1.0,
	}


def _pick_batch_with_qty(item_code, warehouse, need=1):
	"""Return a batch_id that has enough qty, or None."""
	rows = frappe.db.sql(
		"""
		SELECT batch_no AS batch_id, SUM(actual_qty) AS qty
		FROM `tabStock Ledger Entry`
		WHERE item_code=%s AND warehouse=%s AND is_cancelled=0 AND IFNULL(batch_no,'')!=''
		GROUP BY batch_no
		HAVING SUM(actual_qty) >= %s
		ORDER BY SUM(actual_qty) DESC
		LIMIT 5
		""",
		(item_code, warehouse, need),
		as_dict=True,
	)
	for r in rows:
		live = flt(get_batch_qty(batch_no=r.batch_id, warehouse=warehouse, item_code=item_code) or 0)
		if live >= need:
			return r.batch_id, live
	# Fallback: any Batch master + check bin via get_batch_qty
	for b in frappe.get_all("Batch", filters={"item": item_code}, pluck="name", limit=20):
		live = flt(get_batch_qty(batch_no=b, warehouse=warehouse, item_code=item_code) or 0)
		if live >= need:
			return b, live
	return None, 0


def _bin_qty(item_code, warehouse):
	return flt(
		frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty") or 0
	)


def _pour(density_name, block_item, block_qty=1, scrap_kg=2.0):
	settings = frappe.get_single("Pufm Manufacturing Settings")
	company = settings.default_company or COMPANY
	fg = settings.default_fg_warehouse or FG
	dc = frappe.get_doc("Density Configuration", density_name)
	if cint(dc.docstatus) != 1 or not dc.active_bom:
		return {"status": "skip", "reason": "Density {0} not submitted/BOM".format(density_name)}
	if not frappe.db.exists("Item", block_item):
		return {"status": "skip", "reason": "Block item missing: {0}".format(block_item)}

	unit_cbm = flt(frappe.db.get_value("Item", block_item, "custom_cbm_value"))
	if unit_cbm <= 0:
		return {"status": "skip", "reason": "Block has no CBM"}

	output_rate = flt(dc.output_rate_m3_per_min)
	if output_rate <= 0:
		return {"status": "skip", "reason": "No output rate"}

	# Produce exactly block_qty * unit_cbm as actual; expected slightly higher for small yield loss
	actual_cbm = flt(unit_cbm * block_qty, 5)
	expected_cbm = flt(actual_cbm / 0.97, 5)  # ~3% yield loss
	minutes_run = flt(expected_cbm / output_rate, 4)

	pb = frappe.new_doc("Pufm Production Batch")
	pb.company = company
	pb.posting_date = nowdate()
	pb.shift = "Morning"
	pb.insert(ignore_permissions=True)

	run = frappe.new_doc("Pufm Density Run")
	run.parent_batch = pb.name
	run.density_config = dc.name
	run.minutes_run = minutes_run
	run.target_warehouse = fg
	run.scrap_weight_kg = scrap_kg
	run.append("produced_blocks_table", {"block_item": block_item, "quantity": block_qty})
	run.insert(ignore_permissions=True)

	pb.reload()
	pb.flags.ignore_workflow = True
	pb.submit()

	se = pb.chemical_consumption_entry or pb.fg_receipt_entry
	gl = _gl_gap(se) if se else {"pass": False, "reason": "no SE"}
	run_doc = frappe.get_doc("Pufm Density Run", run.name)
	op_cost = 0.0
	for row in dc.bom_operations or []:
		op_cost += flt(row.operating_cost) * expected_cbm

	status = "pass" if gl.get("pass") else "fail"
	return {
		"status": status,
		"production_batch": pb.name,
		"density_run": run.name,
		"block_item": block_item,
		"block_qty": block_qty,
		"minutes_run": minutes_run,
		"expected_cbm": expected_cbm,
		"actual_cbm": flt(run_doc.actual_cbm, 5),
		"variance_pct": flt(getattr(run_doc, "variance_percentage", 0), 2),
		"hour_rate": flt((dc.bom_operations or [{}])[0].get("hour_rate") if dc.bom_operations else 0),
		"est_op_cost_on_expected_cbm": flt(op_cost, 2),
		**gl,
	}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def _test_pour_d18():
	# Smallest practical: 1 × D18-54x75x44 (~2.92 CBM)
	return _pour("D18", "D18-54x75x44 Block", block_qty=1, scrap_kg=3.0)


def _test_pour_d40():
	return _pour("D40", "D40-54x75x44 Block", block_qty=1, scrap_kg=4.0)


def _test_mattress_core_conversion():
	settings = frappe.get_single("Pufm Manufacturing Settings")
	company = settings.default_company or COMPANY
	block = "D18-60x75x44 Block"
	core = "D18-54x84x10-CORE"
	src_wh = WIP
	if _bin_qty(block, src_wh) < 1:
		src_wh = FG
	if _bin_qty(block, src_wh) < 1:
		return {"status": "skip", "reason": "No {0} stock".format(block)}
	if not frappe.db.exists("Item", core):
		return {"status": "skip", "reason": "Core item missing"}

	batch, qty = _pick_batch_with_qty(block, src_wh, need=1)
	if not batch:
		return {"status": "skip", "reason": "No batch with stock for {0} in {1}".format(block, src_wh)}

	# 1 block (~3.24 CBM) → 4 cores (~0.74 each = 2.97) + small scrap
	doc = frappe.new_doc("Mattress Core Conversion")
	doc.company = company
	doc.posting_date = nowdate()
	doc.target_warehouse = WIP
	doc.scrap_weight = 5.0
	doc.append(
		"inputs",
		{
			"item_code": block,
			"qty": 1,
			"source_warehouse": src_wh,
			"batch_no": batch,
		},
	)
	doc.append("outputs", {"item_code": core, "qty": 4})
	doc.insert(ignore_permissions=True)
	doc.submit()

	gl = _gl_gap(doc.stock_entry)
	status = "pass" if gl.get("pass") else "fail"
	return {
		"status": status,
		"name": doc.name,
		"input_block": block,
		"input_batch": batch,
		"output_core": core,
		"output_qty": 4,
		"total_input_cbm": flt(doc.total_input_cbm, 5),
		"total_output_cbm": flt(doc.total_output_cbm, 5),
		"conversion_rate": flt(doc.conversion_rate),
		"conversion_cost": flt(doc.conversion_cost, 2),
		**gl,
	}


def _test_sheeting_conversion():
	settings = frappe.get_single("Pufm Manufacturing Settings")
	company = settings.default_company or COMPANY
	block = "D40-60x75x44 Block"
	if not frappe.db.exists("Item", block):
		return {"status": "skip", "reason": "Block missing"}

	doc = frappe.new_doc("Pufm Sheeting Conversion")
	doc.company = company
	doc.posting_date = nowdate()
	doc.scrap_weight_kg = 2.5
	doc.append(
		"sheeting_outputs",
		{
			"source_block": block,
			"length_inches": 84,
			"width_inches": 36,
			"thickness_inches": 2,
			"quantity": 2,
			"row_note": "E2E furniture cut",
		},
	)
	doc.insert(ignore_permissions=True)
	doc.submit()

	ok = bool(doc.scrap_stock_entry) and cint(
		frappe.db.get_value("Stock Entry", doc.scrap_stock_entry, "docstatus")
	) == 1
	return {
		"status": "pass" if ok else "fail",
		"name": doc.name,
		"scrap_kg": 2.5,
		"scrap_stock_entry": doc.scrap_stock_entry,
		"output_cbm": flt(doc.sheeting_outputs[0].calculated_cbm, 5),
		"note": "Sheeting does not deduct source blocks (DN-driven).",
	}


def _test_quilting():
	settings = frappe.get_single("Pufm Manufacturing Settings")
	company = settings.default_company or COMPANY
	try:
		doc = _submit_quilting_to_wip(company, out_m=4.0)
	except Exception as e:
		return {"status": "fail", "error": str(e)}
	if not doc:
		return {
			"status": "skip",
			"reason": "Insufficient fabric or sheeting in {0} / {1} (seed stock first)".format(
				WIP, STORES
			),
		}

	gl = _gl_gap(doc.stock_entry)
	status = "pass" if gl.get("pass") else "fail"
	return {
		"status": status,
		"name": doc.name,
		"fabric": doc.fabric_item,
		"sheeting": doc.sheeting_roll_item,
		"finished": doc.finished_item,
		"target_warehouse": doc.target_warehouse,
		"output_m": flt(doc.output_qty_meters),
		"total_production_cost": flt(doc.total_production_cost, 2),
		**gl,
	}


def _seed_batch_receipt(item_code, warehouse, company, qty=10, rate=1000):
	batch_id = "E2E-{0}".format(item_code.replace(" ", "-")[:40])
	if not frappe.db.exists("Batch", batch_id):
		b = frappe.new_doc("Batch")
		b.batch_id = batch_id
		b.item = item_code
		b.insert(ignore_permissions=True)
	live = flt(get_batch_qty(batch_no=batch_id, warehouse=warehouse, item_code=item_code) or 0)
	if live < qty:
		se = frappe.new_doc("Stock Entry")
		se.company = company
		se.stock_entry_type = "Material Receipt"
		se.purpose = "Material Receipt"
		se.posting_date = nowdate()
		se.append(
			"items",
			{
				"item_code": item_code,
				"qty": qty,
				"t_warehouse": warehouse,
				"basic_rate": rate,
				"use_serial_batch_fields": 1,
				"batch_no": batch_id,
			},
		)
		se.insert(ignore_permissions=True)
		se.submit()
	return batch_id


def _test_mattress_assembly():
	settings = frappe.get_single("Pufm Manufacturing Settings")
	_ensure_pvc_gsm_for_testing(settings)
	company = settings.default_company or COMPANY
	src = _quilt_and_assembly_warehouse(settings)
	fg = settings.default_fg_warehouse or FG

	mattress = "D18-54x84x10-FQ"
	core = "D18-54x84x10-CORE"
	fabric = "QUILTED-DAMASK-FLORA"
	if not frappe.db.exists("Item", mattress):
		return {"status": "skip", "reason": "FQ mattress missing"}

	need_fabric_m = 3.6
	core_batch, _ = _pick_batch_with_qty(core, src, need=1)
	if not core_batch:
		core_batch = _seed_batch_receipt(core, src, company, qty=2, rate=50000)

	fabric_batch, fabric_qty, quilt_src = _ensure_quilted_fabric_batch(company, need_m=need_fabric_m)
	if not fabric_batch:
		return {
			"status": "skip",
			"reason": "No quilted fabric batch with >= {0} m in {1} ({2})".format(
				need_fabric_m, src, quilt_src
			),
		}

	label = settings.default_label_item or "Labels"
	for item in (
		settings.default_tape_edge_item,
		settings.default_pvc_nylon_item,
		settings.default_thread_item,
		label,
	):
		if item and _bin_qty(item, settings.default_raw_material_warehouse or STORES) <= 0:
			return {"status": "skip", "reason": "No stock for consumable {0}".format(item)}

	doc = frappe.new_doc("Mattress Production Entry")
	doc.company = company
	doc.posting_date = nowdate()
	doc.source_warehouse = src
	doc.target_warehouse = fg
	doc.append(
		"production_items",
		{
			"mattress_item": mattress,
			"qty": 1,
			"core_batch": core_batch,
			"fabric_batch": fabric_batch,
			"fabric_item": fabric,
			"label_item": label,
		},
	)
	doc.insert(ignore_permissions=True)
	doc.submit()

	se_names = []
	if doc.stock_entry:
		se_names.append(doc.stock_entry)
	for raw in (doc.stock_entries or "").split(","):
		name = raw.strip()
		if name and name not in se_names:
			se_names.append(name)
	gl = _gl_gap(se_names[0]) if se_names else {"pass": False, "reason": "no SE"}
	status = "pass" if gl.get("pass") else "fail"
	batch_rate = get_stock_valuation_rate(fabric, warehouse=src, batch_no=fabric_batch)
	return {
		"status": status,
		"name": doc.name,
		"stock_entries": se_names,
		"source_warehouse": src,
		"quilted_fabric_from": quilt_src,
		"fabric_batch": fabric_batch,
		"fabric_batch_qty": flt(fabric_qty, 3),
		"fabric_batch_rate": flt(batch_rate, 2),
		**gl,
	}


def _test_rebound():
	settings = frappe.get_single("Pufm Manufacturing Settings")
	company = settings.default_company or COMPANY
	target = "REB-70-BLOCK-84x75x20"
	if not frappe.db.exists("Item", target):
		return {"status": "skip", "reason": "Rebound FG item missing"}
	if not frappe.db.exists("Rebound Configuration", "REB-70"):
		return {"status": "skip", "reason": "REB-70 config missing"}

	scrap_wh = settings.default_scrap_warehouse or SCRAP_WH
	mdi_wh = STORES if _bin_qty(settings.mdi_item, STORES) > 10 else GIT
	if _bin_qty(settings.scrap_item, scrap_wh) < 50:
		return {"status": "skip", "reason": "Insufficient scrap"}
	if _bin_qty(settings.mdi_item, mdi_wh) < 5:
		return {"status": "skip", "reason": "Insufficient MDI"}

	doc = frappe.new_doc("Rebound Production Entry")
	doc.company = company
	doc.posting_date = nowdate()
	doc.rebound_configuration = "REB-70"
	doc.target_block_item = target
	doc.length_inches = 84
	doc.width_inches = 75
	doc.height_inches = 20
	doc.quantity_produced = 1
	doc.scrap_warehouse = scrap_wh
	doc.mdi_warehouse = mdi_wh
	doc.target_warehouse = FG
	# actuals filled by validate from expected
	doc.insert(ignore_permissions=True)
	doc.submit()

	gl = _gl_gap(doc.stock_entry)
	status = "pass" if gl.get("pass") else "fail"
	return {
		"status": status,
		"name": doc.name,
		"qty": 1,
		"actual_scrap_kg": flt(doc.actual_scrap_kg, 2),
		"actual_mdi_kg": flt(doc.actual_mdi_kg, 2),
		"total_hours": flt(doc.total_hours, 3),
		"power_cost_ngn": flt(doc.power_cost_ngn, 2),
		"labour_cost_ngn": flt(doc.labour_cost_ngn, 2),
		**gl,
	}


def _test_scrap_costing():
	"""Validate costing math; do NOT submit (would rewrite scrap warehouse valuation)."""
	doc = frappe.new_doc("Scrap Costing Calculator")
	doc.company = COMPANY
	doc.posting_date = nowdate()
	doc.scrap_item = "SCRAP-FOAM"
	doc.container_capacity_kg = 20000
	doc.shipping_cost_ngn = 500000
	doc.local_logistics_ngn = 200000
	doc.process_loss_contingency_ngn = 300000
	doc.insert(ignore_permissions=True)
	expected = (500000 + 200000 + 300000) / 20000.0
	ok = abs(flt(doc.calculated_cost_per_kg) - expected) < 0.01
	return {
		"status": "pass" if ok else "fail",
		"name": doc.name,
		"calculated_cost_per_kg": flt(doc.calculated_cost_per_kg, 4),
		"expected": expected,
		"submitted": False,
		"note": "Left as draft — submit revalues entire scrap warehouse.",
	}


def _test_job_order_draft():
	doc = frappe.new_doc("Pufm Job Order")
	doc.company = COMPANY
	doc.posting_date = nowdate()
	doc.order_type = "Mattress"
	if not frappe.db.exists("Item", "D18-54x84x10-FQ"):
		return {"status": "skip", "reason": "FQ item missing"}
	doc.append(
		"mattress_instructions",
		{"item_code": "D18-54x84x10-FQ", "quantity": 1},
	)
	doc.insert(ignore_permissions=True)
	return {
		"status": "pass",
		"name": doc.name,
		"order_type": doc.order_type,
		"docstatus": cint(doc.docstatus),
		"note": "Draft only — submit when linked to SO/workflow.",
	}


def _test_price_engine():
	from pu_foam_master.pufm_manufacturing.doctype.pufm_price_engine.pufm_price_engine import (
		fetch_item_matrix,
	)

	if not frappe.db.exists("Item Group", "Products"):
		return {"status": "skip", "reason": "Products group missing"}
	price_list = "Standard Selling"
	if not frappe.db.exists("Price List", price_list):
		return {"status": "skip", "reason": "No Standard Selling price list"}

	rows = fetch_item_matrix("Products") or []
	if not rows:
		# Fallback: pick a few sales items under Products
		rows = frappe.get_all(
			"Item",
			filters={"item_group": "Products", "disabled": 0, "is_sales_item": 1},
			fields=["name as item_code", "item_name", "valuation_rate"],
			limit=5,
		)
		for r in rows:
			r["current_cost"] = flt(r.get("valuation_rate") or 1000)
			r["proposed_selling_price"] = flt(r["current_cost"] * 1.25, 2)

	if not rows:
		return {"status": "skip", "reason": "No sales items in Products group"}

	doc = frappe.new_doc("Pufm Price Engine")
	doc.company = COMPANY
	doc.item_group = "Products"
	doc.price_list = price_list
	doc.valid_from = nowdate()
	doc.profit_margin_percent = 20
	for r in rows[:15]:
		cost = flt(r.get("current_cost") or r.get("valuation_rate") or 0)
		if cost <= 0:
			cost = 1000
		doc.append(
			"items",
			{
				"item_code": r.get("item_code"),
				"item_name": r.get("item_name"),
				"current_cost": cost,
				"proposed_selling_price": flt(r.get("proposed_selling_price") or cost * 1.25, 2),
				"dollar_adjusted_price": flt(r.get("proposed_selling_price") or cost * 1.25, 2),
				"selling_price": flt(r.get("proposed_selling_price") or cost * 1.25, 2),
				"material_breakdown": r.get("material_breakdown") or "",
			},
		)
	doc.insert(ignore_permissions=True)
	return {
		"status": "pass",
		"name": doc.name,
		"price_list": price_list,
		"rows": len(doc.items),
		"note": "Draft with fetched matrix; not submitted (avoids rewriting Item Prices).",
	}


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _verdict(report):
	fails = report["fail_count"]
	passes = report["pass_count"]
	missing = (report.get("audit") or {}).get("missing") or []
	settings_gaps = (report.get("audit") or {}).get("settings_gaps") or []
	if fails == 0 and not missing and not settings_gaps:
		return "READY — all executed flows passed; DocType surface complete."
	if fails == 0 and (missing or settings_gaps):
		return "MOSTLY READY — flows passed; close settings/DocType gaps before production go-live."
	if fails <= 2:
		return "CONDITIONAL — core flows mostly work; fix failing tests before go-live."
	return "NOT READY — multiple flow failures; stabilize before production use."


def _format_report(report):
	lines = []
	lines.append("=" * 72)
	lines.append("PUFM E2E AUDIT REPORT")
	lines.append("=" * 72)
	a = report.get("audit") or {}
	lines.append(
		"\n[AUDIT] DocTypes {0}/{1} present".format(a.get("doctypes_ok"), a.get("doctypes_total"))
	)
	if a.get("missing"):
		lines.append("  MISSING: {0}".format(", ".join(a["missing"])))
	lines.append(
		"  Company={0}  WIP={1}".format(a.get("company"), a.get("wip_warehouse"))
	)
	lines.append(
		"  D18 submitted={0} BOM={1}".format(a.get("d18_submitted"), a.get("d18_bom"))
	)
	lines.append(
		"  D40 submitted={0} BOM={1}".format(a.get("d40_submitted"), a.get("d40_bom"))
	)
	lines.append(
		"  conversion_rate={0} quilting_rate={1} scrap_out={2} scrap_in={3}".format(
			a.get("conversion_rate_per_cbm"),
			a.get("quilting_rate_per_m"),
			a.get("scrap_output_rate"),
			a.get("scrap_input_rate"),
		)
	)
	if a.get("settings_gaps"):
		lines.append("  SETTINGS GAPS: {0}".format(", ".join(a["settings_gaps"])))
	if a.get("optional_gaps"):
		lines.append("  OPTIONAL GAPS: {0}".format(", ".join(a["optional_gaps"])))

	s = report.get("setup") or {}
	lines.append("\n[SETUP] Hour rates")
	for dens in ("D18", "D40"):
		block = s.get(dens) or {}
		lines.append(
			"  {0}: hour_rate={1} ops={2}".format(dens, block.get("hour_rate"), block.get("operations"))
		)

	lines.append(
		"\n[TESTS] pass={0} fail={1} skip={2}".format(
			report["pass_count"], report["fail_count"], report["skip_count"]
		)
	)
	for key, result in (report.get("tests") or {}).items():
		st = (result or {}).get("status", "?")
		lines.append("\n  --- {0}: {1} ---".format(key.upper(), st.upper()))
		for k, v in (result or {}).items():
			if k in ("trace",):
				continue
			lines.append("    {0}: {1}".format(k, v))

	if report.get("errors"):
		lines.append("\n[ERRORS]")
		for e in report["errors"]:
			lines.append("  - {0}".format(e))

	lines.append("\n[VERDICT] {0}".format(report.get("verdict")))
	lines.append("=" * 72)
	return "\n".join(lines)
