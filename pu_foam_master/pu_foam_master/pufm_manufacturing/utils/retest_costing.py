# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

"""Live retest helpers for FQ assembly + pour yield capitalization.

  bench --site pu_foam.localhost execute \\
    pu_foam_master.pufm_manufacturing.utils.retest_costing.run
"""

from __future__ import annotations

import frappe
from frappe.utils import flt, nowdate

from erpnext.stock.doctype.batch.batch import get_batch_qty

from pu_foam_master.pufm_manufacturing.utils.stock_entry_valuation import (
	get_stock_valuation_rate,
)


def run():
	frappe.connect()
	frappe.set_user("Administrator")
	results = {"fq": None, "pour": None, "errors": []}

	try:
		results["fq"] = _retest_fq_assembly()
	except Exception as e:
		frappe.db.rollback()
		results["errors"].append("FQ: {0}".format(e))
		frappe.log_error(title="FQ retest failed")

	try:
		results["pour"] = _retest_pour()
	except Exception as e:
		frappe.db.rollback()
		results["errors"].append("Pour: {0}".format(e))
		frappe.log_error(title="Pour retest failed")

	frappe.db.commit()
	print(_format_results(results))
	return results


def _format_results(results):
	lines = ["=== PUFM Costing Retest ==="]
	for key in ("fq", "pour"):
		block = results.get(key)
		if not block:
			lines.append("{0}: SKIPPED / FAILED".format(key.upper()))
			continue
		lines.append("\n{0}:".format(key.upper()))
		for k, v in block.items():
			lines.append("  {0}: {1}".format(k, v))
	if results["errors"]:
		lines.append("\nERRORS:")
		for e in results["errors"]:
			lines.append("  - {0}".format(e))
	return "\n".join(lines)


def _gl_stock_adjustment_gap(stock_entry_name):
	if not stock_entry_name:
		return None
	rows = frappe.db.sql(
		"""
		SELECT account, SUM(debit) AS debit, SUM(credit) AS credit
		FROM `tabGL Entry`
		WHERE voucher_type = 'Stock Entry'
			AND voucher_no = %s
			AND is_cancelled = 0
		GROUP BY account
		""",
		stock_entry_name,
		as_dict=True,
	)
	adj_account = _stock_adjustment_account(stock_entry_name)
	adj_net = 0.0
	for r in rows:
		if adj_account and r.account == adj_account:
			adj_net = flt(r.debit) - flt(r.credit)
		elif not adj_account and r.account and "stock adjustment" in r.account.lower():
			adj_account = r.account
			adj_net = flt(r.debit) - flt(r.credit)

	src = _se_amounts(stock_entry_name)
	gap = flt(src["sources"] + src["additional"] - src["targets"])

	# If additional costs are booked to Stock Adjustment (common demo settings),
	# that credit is intentional overhead absorption — not a materials yield leak.
	overhead_on_adj = 0.0
	if adj_account:
		for row in frappe.get_all(
			"Landed Cost Taxes and Charges",
			filters={"parent": stock_entry_name, "parenttype": "Stock Entry"},
			fields=["expense_account", "amount", "base_amount"],
		):
			if row.expense_account == adj_account:
				overhead_on_adj += flt(row.base_amount or row.amount)
	# Cr Stock Adjustment from overhead → adj_net is negative
	unexplained_adj = flt(adj_net + overhead_on_adj)

	return {
		"stock_entry": stock_entry_name,
		"sources": src["sources"],
		"additional": src["additional"],
		"targets": src["targets"],
		"gap_sources_vs_targets": gap,
		"stock_adjustment_net": adj_net,
		"overhead_on_stock_adjustment": overhead_on_adj,
		"unexplained_stock_adjustment": unexplained_adj,
		"pass": abs(gap) <= 0.10 and abs(unexplained_adj) <= 100,
	}


def _stock_adjustment_account(stock_entry_name):
	company = frappe.db.get_value("Stock Entry", stock_entry_name, "company")
	if not company:
		return None
	return frappe.get_cached_value("Company", company, "stock_adjustment_account")


def _se_amounts(se_name):
	se = frappe.get_doc("Stock Entry", se_name)
	sources = additional = targets = 0.0
	for row in se.items:
		qty = flt(row.qty)
		rate = flt(row.basic_rate or row.valuation_rate)
		amt = flt(row.amount) or flt(row.basic_amount) or flt(qty * rate)
		if row.s_warehouse:
			sources += amt
		if row.t_warehouse:
			targets += amt
	for row in se.get("additional_costs") or []:
		additional += flt(getattr(row, "base_amount", None) or row.amount)
	return {
		"sources": flt(sources, 2),
		"additional": flt(additional, 2),
		"targets": flt(targets, 2),
	}


def _ensure_core_batch(core_item, warehouse, company, rate=50000):
	batch_id = "RETEST-CORE-{0}".format(core_item)
	if not frappe.db.exists("Batch", batch_id):
		b = frappe.new_doc("Batch")
		b.batch_id = batch_id
		b.item = core_item
		b.insert(ignore_permissions=True)

	qty = flt(get_batch_qty(batch_no=batch_id, warehouse=warehouse, item_code=core_item) or 0)
	if qty < 1:
		se = frappe.new_doc("Stock Entry")
		se.company = company
		se.stock_entry_type = "Material Receipt"
		se.purpose = "Material Receipt"
		se.posting_date = nowdate()
		se.append(
			"items",
			{
				"item_code": core_item,
				"qty": 2,
				"t_warehouse": warehouse,
				"basic_rate": rate,
				"use_serial_batch_fields": 1,
				"batch_no": batch_id,
			},
		)
		se.insert(ignore_permissions=True)
		se.submit()
	return batch_id


def _retest_fq_assembly():
	settings = frappe.get_single("Pufm Manufacturing Settings")
	wip = "Work In Progress - SF"
	fg_wh = settings.default_fg_warehouse or "Finished Goods - SF"
	company = settings.default_company or "Solarfoam"

	fabric_batch = "QUILT-2026-08-00001-QUILTED-DAMASK-FLORA"
	fabric_item = "QUILTED-DAMASK-FLORA"
	if flt(get_batch_qty(batch_no=fabric_batch, warehouse=wip, item_code=fabric_item) or 0) <= 0:
		return {"status": "skipped", "reason": "No quilted fabric stock in WIP"}

	batch_rate = get_stock_valuation_rate(fabric_item, warehouse=wip, batch_no=fabric_batch)
	bin_rate = flt(
		frappe.db.get_value("Bin", {"item_code": fabric_item, "warehouse": wip}, "valuation_rate")
	)

	# Prefer an FQ mattress that has a real CORE item; seed stock if needed
	mattress = "D18-54x84x10-FQ"
	core_item = "D18-54x84x10-CORE"
	if not frappe.db.exists("Item", mattress) or not frappe.db.exists("Item", core_item):
		return {"status": "skipped", "reason": "FQ/CORE items missing"}

	core_batch = _ensure_core_batch(core_item, wip, company)

	label = frappe.db.sql(
		"""
		SELECT label_item FROM `tabMattress Production Item`
		WHERE label_item IS NOT NULL AND label_item != ''
		ORDER BY creation DESC LIMIT 1
		"""
	)
	label = label[0][0] if label else None
	if not label:
		return {"status": "skipped", "reason": "No label item on prior mattress rows"}

	doc = frappe.new_doc("Mattress Production Entry")
	doc.company = company
	doc.posting_date = nowdate()
	doc.source_warehouse = wip
	doc.target_warehouse = fg_wh
	doc.append(
		"production_items",
		{
			"mattress_item": mattress,
			"qty": 1,
			"core_batch": core_batch,
			"fabric_batch": fabric_batch,
			"fabric_item": fabric_item,
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

	main_gl = _gl_stock_adjustment_gap(se_names[0]) if se_names else {}
	return {
		"status": "submitted",
		"mpe": doc.name,
		"stock_entries": se_names,
		"fabric_batch": fabric_batch,
		"batch_rate_used": batch_rate,
		"bin_rate": bin_rate,
		"batch_beats_bin": batch_rate > 0 and abs(batch_rate - bin_rate) > 1,
		**(main_gl or {}),
	}


def _retest_pour():
	settings = frappe.get_single("Pufm Manufacturing Settings")
	fg_wh = settings.default_fg_warehouse or "Finished Goods - SF"
	company = settings.default_company or "Solarfoam"

	density = frappe.db.sql(
		"""
		SELECT dc.name, dc.density_name, dc.output_rate_m3_per_min
		FROM `tabDensity Configuration` dc
		WHERE dc.docstatus = 1 AND dc.active_bom IS NOT NULL
			AND dc.density_name IN ('D18', 'D13', 'D16', 'D14')
		ORDER BY FIELD(dc.density_name, 'D18', 'D13', 'D16', 'D14')
		LIMIT 1
		""",
		as_dict=True,
	)
	if not density:
		return {"status": "skipped", "reason": "No submitted Density Configuration"}

	dc = density[0]
	output_rate = flt(dc.output_rate_m3_per_min)
	if output_rate <= 0:
		return {"status": "skipped", "reason": "No output rate on {0}".format(dc.name)}

	block = frappe.db.sql(
		"""
		SELECT name, custom_cbm_value FROM `tabItem`
		WHERE name LIKE %s AND disabled = 0
		ORDER BY creation DESC LIMIT 1
		""",
		("{0}-% Block".format(dc.density_name),),
		as_dict=True,
	)
	if not block:
		return {"status": "skipped", "reason": "No block item for {0}".format(dc.density_name)}

	unit_cbm = flt(block[0].custom_cbm_value)
	if unit_cbm <= 0:
		return {"status": "skipped", "reason": "Block has no CBM"}

	minutes_run = flt(55 / output_rate, 2)
	expected_cbm = flt(minutes_run * output_rate, 5)
	actual_cbm = flt(expected_cbm * 0.95, 5)
	block_qty = max(1, int(actual_cbm / unit_cbm))

	pb = frappe.new_doc("Pufm Production Batch")
	pb.company = company
	pb.posting_date = nowdate()
	pb.shift = "Morning"
	pb.workflow_state = "Draft"
	pb.insert(ignore_permissions=True)

	run = frappe.new_doc("Pufm Density Run")
	run.parent_batch = pb.name
	run.density_config = dc.name
	run.minutes_run = minutes_run
	run.target_warehouse = fg_wh
	run.scrap_weight_kg = 0
	run.append("produced_blocks_table", {"block_item": block[0].name, "quantity": block_qty})
	run.insert(ignore_permissions=True)

	pb.reload()
	pb.flags.ignore_workflow = True
	pb.submit()

	se = pb.chemical_consumption_entry or pb.fg_receipt_entry
	gl = _gl_stock_adjustment_gap(se) if se else {}
	run_doc = frappe.get_doc("Pufm Density Run", run.name)
	return {
		"status": "submitted",
		"production_batch": pb.name,
		"density_run": run.name,
		"expected_cbm": expected_cbm,
		"actual_cbm": flt(run_doc.actual_cbm, 5),
		"variance_pct": flt(run_doc.variance_percentage, 2),
		**(gl or {}),
	}
