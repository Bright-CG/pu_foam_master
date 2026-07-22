"""
One-off local force-inject for FILLER into the Production Batch source warehouse.

Run:
  bench --site pu_foam.localhost execute pu_foam_master.scripts.force_inject_filler.force_inject_filler
"""

from __future__ import annotations

import frappe
from frappe.utils import flt, nowdate


def force_inject_filler(qty=10000, rate=1500):
	item_code = "FILLER"
	if not frappe.db.exists("Item", item_code):
		frappe.throw(f"Item {item_code} does not exist.")

	item = frappe.get_doc("Item", item_code)
	changed = False
	if not item.is_stock_item:
		item.is_stock_item = 1
		changed = True
	if item.has_batch_no:
		item.has_batch_no = 0
		changed = True
	if flt(item.valuation_rate) <= 0:
		item.valuation_rate = flt(rate)
		changed = True
	if changed:
		item.save(ignore_permissions=True)
		frappe.db.commit()

	settings = frappe.get_single("Pufm Manufacturing Settings")
	# Production Batch Material Issue pulls chemicals from default_wip_warehouse
	source_warehouse = settings.default_wip_warehouse
	if not source_warehouse:
		frappe.throw(
			"Pufm Manufacturing Settings.default_wip_warehouse is not set. "
			"That is the source warehouse used when completing a Production Batch."
		)

	company = frappe.db.get_value("Warehouse", source_warehouse, "company")
	if not company:
		frappe.throw(f"Warehouse {source_warehouse} has no company.")

	expense_account = _resolve_stock_adjustment_account(company)
	if not expense_account:
		frappe.throw(f"Could not resolve Stock Adjustment account for {company}.")

	before = frappe.db.get_value(
		"Bin",
		{"item_code": item_code, "warehouse": source_warehouse},
		["actual_qty", "valuation_rate"],
		as_dict=True,
	)

	sr = frappe.new_doc("Stock Reconciliation")
	sr.company = company
	sr.purpose = "Stock Reconciliation"
	sr.posting_date = nowdate()
	sr.set_posting_time = 1
	sr.expense_account = expense_account
	sr.append(
		"items",
		{
			"item_code": item_code,
			"warehouse": source_warehouse,
			"qty": flt(qty),
			"valuation_rate": flt(rate),
			"allow_zero_valuation_rate": 0,
		},
	)
	sr.insert(ignore_permissions=True)
	sr.submit()
	frappe.db.commit()

	after = frappe.db.get_value(
		"Bin",
		{"item_code": item_code, "warehouse": source_warehouse},
		["actual_qty", "valuation_rate"],
		as_dict=True,
	)
	all_bins = frappe.get_all(
		"Bin",
		filters={"item_code": item_code},
		fields=["warehouse", "actual_qty", "valuation_rate", "stock_uom"],
	)

	result = {
		"item_code": item_code,
		"is_stock_item": item.is_stock_item,
		"has_batch_no": item.has_batch_no,
		"item_valuation_rate": flt(frappe.db.get_value("Item", item_code, "valuation_rate")),
		"source_warehouse_used_by_batch": source_warehouse,
		"company": company,
		"expense_account": expense_account,
		"stock_reconciliation": sr.name,
		"before_bin": before,
		"after_bin": after,
		"all_filler_bins": all_bins,
	}
	print("[force_inject_filler]", result)
	return result


def _resolve_stock_adjustment_account(company):
	abbr = frappe.db.get_value("Company", company, "abbr") or ""
	for name in (f"5119 - Stock Adjustment - {abbr}", f"Stock Adjustment - {abbr}"):
		if frappe.db.exists("Account", name):
			return name
	rows = frappe.get_all(
		"Account",
		filters={
			"company": company,
			"is_group": 0,
			"account_name": ["like", "%Stock Adjustment%"],
		},
		pluck="name",
		limit=1,
	)
	return rows[0] if rows else None
