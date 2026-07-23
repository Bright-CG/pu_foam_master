"""
Massive WIP refill for Production Batch testing.

Run:
  bench --site pu_foam.localhost execute pu_foam_master.scripts.refill_wip_chemicals.refill_primary_chemicals
"""

from __future__ import annotations

import frappe
from frappe.utils import flt, nowdate

from pu_foam_master.scripts.local_stock_setup import (
	ITEM_ALIASES,
	_resolve_item_code,
	_resolve_stock_adjustment_account,
	demo_stock_data,
)

PRIMARY_CHEMICALS = [
	"15_POLYMERIC",
	"TDI",
	"POLYOL II",
	"MDI",
	"MC",
	"SILICON",
	"STANNOUS",
	"A33",
	"HARDNER",
	"FILLER",
	"PIGMENT - BLACK",
]

DEFAULT_FALLBACK_RATE = 3500
TARGET_QTY = 50000


def refill_primary_chemicals(qty=None, warehouse=None):
	"""Inject qty (default 50,000) of primary chemicals into WIP warehouse for SF."""
	qty = flt(qty if qty is not None else TARGET_QTY)
	settings = frappe.get_single("Pufm Manufacturing Settings")
	wip_warehouse = warehouse or settings.default_wip_warehouse or "Goods In Transit - SF"

	if not frappe.db.exists("Warehouse", wip_warehouse):
		frappe.throw(f"Warehouse {wip_warehouse} does not exist.")

	company = frappe.db.get_value("Warehouse", wip_warehouse, "company")
	if not company:
		frappe.throw(f"Warehouse {wip_warehouse} has no company.")

	# Prefer Solarfoam if WIP is SF
	if company != "Solarfoam" and frappe.db.exists("Warehouse", "Goods In Transit - SF"):
		wip_warehouse = "Goods In Transit - SF"
		company = frappe.db.get_value("Warehouse", wip_warehouse, "company")

	expense_account = _resolve_stock_adjustment_account(company)
	if not expense_account:
		frappe.throw(f"Could not resolve Stock Adjustment account for {company}.")

	sr = frappe.new_doc("Stock Reconciliation")
	sr.company = company
	sr.purpose = "Stock Reconciliation"
	sr.posting_date = nowdate()
	sr.set_posting_time = 1
	sr.expense_account = expense_account

	stocked = []
	skipped = []

	for demo_key in PRIMARY_CHEMICALS:
		item_code = _resolve_item_code(demo_key) or ITEM_ALIASES.get(demo_key, demo_key)
		if not item_code or not frappe.db.exists("Item", item_code):
			skipped.append(demo_key)
			continue

		rate = _resolve_rate(item_code, wip_warehouse, demo_key)
		item = frappe.get_doc("Item", item_code)
		changed = False
		if not item.is_stock_item:
			item.is_stock_item = 1
			changed = True
		if flt(item.valuation_rate) <= 0:
			item.valuation_rate = rate
			changed = True
		if changed:
			item.save(ignore_permissions=True)

		sr.append(
			"items",
			{
				"item_code": item_code,
				"warehouse": wip_warehouse,
				"qty": qty,
				"valuation_rate": rate,
				"allow_zero_valuation_rate": 0,
			},
		)
		stocked.append({"item_code": item_code, "qty": qty, "rate": rate})

	frappe.db.commit()

	if not sr.items:
		frappe.throw(f"No items to stock. Skipped: {skipped}")

	sr.insert(ignore_permissions=True)
	sr.submit()
	frappe.db.commit()

	spot = {}
	for code in ("15_POLYMERIC", "TDI", "FILLER"):
		if frappe.db.exists("Item", code):
			row = frappe.db.get_value(
				"Bin",
				{"item_code": code, "warehouse": wip_warehouse},
				["actual_qty", "valuation_rate"],
				as_dict=True,
			)
			spot[code] = row

	message = (
		f"[refill_wip_chemicals] {sr.name} submitted. "
		f"Stocked {len(stocked)} item(s) @ {qty} in {wip_warehouse} ({company})."
	)
	print(message)
	if skipped:
		print(f"[refill_wip_chemicals] Skipped missing: {skipped}")
	print(f"[refill_wip_chemicals] Spot check: {spot}")

	return {
		"stock_reconciliation": sr.name,
		"warehouse": wip_warehouse,
		"company": company,
		"qty": qty,
		"stocked": stocked,
		"skipped": skipped,
		"spot_check": spot,
		"message": message,
	}


def _resolve_rate(item_code, warehouse, demo_key):
	bin_rate = flt(
		frappe.db.get_value(
			"Bin", {"item_code": item_code, "warehouse": warehouse}, "valuation_rate"
		)
	)
	if bin_rate > 0:
		return bin_rate

	item_rate = flt(frappe.db.get_value("Item", item_code, "valuation_rate"))
	if item_rate > 0:
		return item_rate

	demo = demo_stock_data.get(demo_key) or {}
	if flt(demo.get("rate")) > 0:
		return flt(demo["rate"])

	return flt(DEFAULT_FALLBACK_RATE)
