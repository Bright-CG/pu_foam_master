"""
Inject demo chemical stock into the Production Batch WIP warehouse.

Also ensures default_fg_warehouse is set on Pufm Manufacturing Settings.

Run:
  bench --site pu_foam.localhost execute pu_foam_master.scripts.inject_wip_stock.inject_wip_chemicals
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


def inject_wip_chemicals(force=0):
	"""
	Stock Reconciliation of all Density Configuration chemicals (+ demo catalog)
	into settings.default_wip_warehouse, and ensure default_fg_warehouse is set.
	"""
	settings = frappe.get_single("Pufm Manufacturing Settings")
	fg_result = ensure_default_fg_warehouse(settings)
	settings.reload()

	wip_warehouse = settings.default_wip_warehouse
	if not wip_warehouse:
		frappe.throw(
			"Set Default WIP Warehouse in Pufm Manufacturing Settings "
			"(Production Batch Material Issue uses this warehouse)."
		)

	company = frappe.db.get_value("Warehouse", wip_warehouse, "company")
	if not company:
		frappe.throw(f"Warehouse {wip_warehouse} has no company.")

	expense_account = _resolve_stock_adjustment_account(company)
	if not expense_account:
		frappe.throw(f"Could not resolve Stock Adjustment account for {company}.")

	targets = _collect_chemical_targets()
	if not targets:
		frappe.throw("No chemical items found in Density Configurations or demo_stock_data.")

	sr = frappe.new_doc("Stock Reconciliation")
	sr.company = company
	sr.purpose = "Stock Reconciliation"
	sr.posting_date = nowdate()
	sr.set_posting_time = 1
	sr.expense_account = expense_account

	stocked = []
	already_ok = []
	skipped_missing = []

	for item_code, values in sorted(targets.items()):
		if not frappe.db.exists("Item", item_code):
			skipped_missing.append(item_code)
			continue

		# Ensure stock item + valuation rate on Item master
		item = frappe.get_doc("Item", item_code)
		changed = False
		if not item.is_stock_item:
			item.is_stock_item = 1
			changed = True
		if flt(item.valuation_rate) <= 0 and flt(values["rate"]) > 0:
			item.valuation_rate = flt(values["rate"])
			changed = True
		if changed:
			item.save(ignore_permissions=True)

		target_qty = flt(values["qty"])
		target_rate = flt(values["rate"])
		current_qty, current_rate = _bin_qty_rate(item_code, wip_warehouse)

		if not force and flt(current_qty) == target_qty and flt(current_rate) == target_rate:
			already_ok.append(item_code)
			continue

		sr.append(
			"items",
			{
				"item_code": item_code,
				"warehouse": wip_warehouse,
				"qty": target_qty,
				"valuation_rate": target_rate,
				"allow_zero_valuation_rate": 0,
			},
		)
		stocked.append(
			{
				"item_code": item_code,
				"qty": target_qty,
				"rate": target_rate,
				"previous_qty": current_qty,
				"previous_rate": current_rate,
			}
		)

	frappe.db.commit()

	if not sr.items:
		message = (
			f"[inject_wip_stock] No SR needed. {len(already_ok)} item(s) already OK in {wip_warehouse}."
		)
		print(message)
		return {
			"stock_reconciliation": None,
			"wip_warehouse": wip_warehouse,
			"fg_warehouse": settings.default_fg_warehouse,
			"fg_result": fg_result,
			"stocked_count": 0,
			"already_ok": already_ok,
			"skipped_missing": skipped_missing,
			"message": message,
		}

	sr.insert(ignore_permissions=True)
	sr.submit()
	frappe.db.commit()

	message = (
		f"[inject_wip_stock] {sr.name} submitted. "
		f"Stocked {len(stocked)} item(s) in {wip_warehouse} ({company})."
	)
	print(message)
	if already_ok:
		print(f"[inject_wip_stock] Already OK: {', '.join(already_ok)}")
	if skipped_missing:
		print(f"[inject_wip_stock] Missing Items: {', '.join(skipped_missing)}")

	# Confirm a few critical bins
	spot = {}
	for code in ("RS NYLON", "BASE PAPER", "SIDE NYLON", "FILLER", "TDI"):
		if frappe.db.exists("Item", code):
			spot[code] = _bin_qty_rate(code, wip_warehouse)

	return {
		"stock_reconciliation": sr.name,
		"wip_warehouse": wip_warehouse,
		"fg_warehouse": settings.default_fg_warehouse,
		"fg_result": fg_result,
		"company": company,
		"expense_account": expense_account,
		"stocked_count": len(stocked),
		"stocked": stocked,
		"already_ok": already_ok,
		"skipped_missing": skipped_missing,
		"spot_check_bins": spot,
		"message": message,
	}


def ensure_default_fg_warehouse(settings=None):
	settings = settings or frappe.get_single("Pufm Manufacturing Settings")
	if settings.default_fg_warehouse and frappe.db.exists("Warehouse", settings.default_fg_warehouse):
		return {"changed": False, "warehouse": settings.default_fg_warehouse}

	company = None
	if settings.default_wip_warehouse:
		company = frappe.db.get_value("Warehouse", settings.default_wip_warehouse, "company")
	if not company and frappe.db.exists("Company", "Solarfoam"):
		company = "Solarfoam"

	candidates = []
	if company:
		abbr = frappe.db.get_value("Company", company, "abbr") or ""
		candidates.extend(
			[
				f"Finished Goods - {abbr}",
				f"Stores - {abbr}",  # last-resort only if FG missing
			]
		)
	candidates.extend(["Finished Goods - SF", "Stores - SF"])

	chosen = None
	for name in candidates:
		if not frappe.db.exists("Warehouse", name):
			continue
		wh_company = frappe.db.get_value("Warehouse", name, "company")
		if company and wh_company and wh_company != company:
			continue
		# Prefer names that look like FG
		if "Finished" in name or "FG" in name:
			chosen = name
			break
		if not chosen:
			chosen = name

	# Prefer any FG warehouse for the company
	if not chosen and company:
		rows = frappe.get_all(
			"Warehouse",
			filters={"company": company, "disabled": 0, "name": ["like", "%Finished%"]},
			pluck="name",
			limit=1,
		)
		chosen = rows[0] if rows else None

	if not chosen:
		frappe.throw(
			"Could not resolve a Finished Goods warehouse. Create 'Finished Goods - SF' "
			"or set Default FG Warehouse in Pufm Manufacturing Settings."
		)

	settings.db_set("default_fg_warehouse", chosen, update_modified=False)
	frappe.db.commit()
	print(f"[inject_wip_stock] Set default_fg_warehouse -> {chosen}")
	return {"changed": True, "warehouse": chosen}


def _collect_chemical_targets():
	"""Merge demo_stock_data with every Production Inputs item from Density Configs."""
	targets = {}

	for demo_key, values in demo_stock_data.items():
		item_code = _resolve_item_code(demo_key) or ITEM_ALIASES.get(demo_key, demo_key)
		if item_code and frappe.db.exists("Item", item_code):
			targets[item_code] = {"qty": flt(values["qty"]), "rate": flt(values["rate"])}

	# Every chemical actually used on recipes
	rows = frappe.get_all(
		"Production Inputs",
		filters={"parenttype": "Density Configuration"},
		fields=["item_code"],
		distinct=True,
	)
	for row in rows:
		item_code = row.item_code
		if not item_code or not frappe.db.exists("Item", item_code):
			continue
		if item_code in targets:
			continue
		# Fallback qty/rate for recipe-only items not in demo catalog
		rate = flt(frappe.db.get_value("Item", item_code, "valuation_rate")) or 1000
		targets[item_code] = {"qty": 5000, "rate": rate}

	return targets


def _bin_qty_rate(item_code, warehouse):
	row = frappe.db.get_value(
		"Bin",
		{"item_code": item_code, "warehouse": warehouse},
		["actual_qty", "valuation_rate"],
		as_dict=True,
	)
	if not row:
		return 0.0, 0.0
	return flt(row.actual_qty), flt(row.valuation_rate)
