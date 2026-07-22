"""
Local-only stock injection for PU Foam Master testing.

NOT wired into hooks.py / after_install / after_migrate.
Run manually via bench execute when you need demo inventory.

Example:
  bench --site pu_foam.localhost execute pu_foam_master.scripts.local_stock_setup.run_local_stock_setup
"""

from __future__ import annotations

import frappe
from frappe.utils import cint, flt, nowdate

# Realistic NGN market rates + test quantities (local demo only)
demo_stock_data = {
	# Main Chemicals (Kg)
	"TDI": {"qty": 5000, "rate": 4500},
	"15_POLYMERIC": {"qty": 10000, "rate": 3500},
	"POLYOL II": {"qty": 10000, "rate": 3500},
	"MDI": {"qty": 5000, "rate": 4000},
	"MC": {"qty": 2000, "rate": 1500},
	"FILLER": {"qty": 10000, "rate": 1500},
	# Catalysts & Additives (Kg)
	"SILICON": {"qty": 500, "rate": 10000},
	"STANNOUS": {"qty": 200, "rate": 25000},
	"A33": {"qty": 200, "rate": 15000},
	"HARDNER": {"qty": 200, "rate": 15000},
	"SMP": {"qty": 200, "rate": 15000},
	# Pigments & Scraps (Kg)
	"FOAM SCRAPS": {"qty": 20000, "rate": 1200},
	"PIGMENT - BLACK": {"qty": 100, "rate": 6000},
	"PIGMENT - BLUE": {"qty": 100, "rate": 6000},
	"PIGMENT - YELLOW": {"qty": 100, "rate": 6000},
	"PIGMENT - RED": {"qty": 100, "rate": 6000},
	# Paper & Nylon
	"BASE PAPER": {"qty": 5000, "rate": 500},
	"SIDE NYLON": {"qty": 5000, "rate": 400},
	"RS NYLON": {"qty": 5000, "rate": 400},
	# Mattress Consumables
	"Raw Damask Fabric": {"qty": 5000, "rate": 2500},
	"Peeling Foam Roll": {"qty": 5000, "rate": 1500},
	# Tracked in meters (rolls vary; consume by meter in production)
	"Tape Edge": {"qty": 50000, "rate": 100},
}

# Map demo dictionary keys -> actual Item codes on this site (when names differ)
ITEM_ALIASES = {
	"FOAM SCRAPS": "SCRAP-FOAM",
	"PIGMENT - BLUE": "Pigment Blue",
}

# Items ensured before stock injection (create if missing)
ITEMS_TO_ENSURE = [
	{"item_code": "FILLER", "stock_uom": "Kg", "uom_fallbacks": ["Kg"]},
	{"item_code": "Raw Damask Fabric", "stock_uom": "Meter", "uom_fallbacks": ["Metre", "m", "Nos"]},
	{"item_code": "Peeling Foam Roll", "stock_uom": "Meter", "uom_fallbacks": ["Metre", "m", "Nos"]},
	{"item_code": "Tape Edge", "stock_uom": "Meter", "uom_fallbacks": ["Metre", "m"]},
]

# Backwards-compatible alias
MATTRESS_ITEMS = ITEMS_TO_ENSURE

TAPE_EDGE_ITEM = "Tape Edge"


def run_local_stock_setup():
	"""Sequential local setup: cleanup SFD -> create items -> inject SF stock."""
	cleanup = cleanup_sfd_stock()
	items = create_missing_items()
	uom_fix = ensure_tape_edge_meter_uom()
	injection = inject_sf_stock()

	result = {
		"cleanup": cleanup,
		"items_created": items,
		"tape_edge_uom": uom_fix,
		"injection": injection,
	}
	print(
		f"[local_stock_setup] DONE. Items created: {items.get('created') or []}. "
		f"SF Stock Reconciliation: {injection.get('stock_reconciliation')}"
	)
	return result


def cleanup_sfd_stock():
	"""
	Cancel + delete Stock Reconciliations that targeted the SFD / demo company
	so the ledger is not polluted with the earlier misfire.
	"""
	sfd_company = _resolve_sfd_company()
	cancelled = []
	deleted = []
	errors = []

	names = set()
	if sfd_company:
		for row in frappe.get_all(
			"Stock Reconciliation",
			filters={"company": sfd_company},
			pluck="name",
		):
			names.add(row)

	for row in frappe.get_all(
		"Stock Reconciliation",
		filters={"name": ["like", "%"]},
		fields=["name", "company"],
	):
		# Warehouse child rows may reference SFD stores even if company filter missed
		has_sfd_wh = frappe.db.exists(
			"Stock Reconciliation Item",
			{"parent": row.name, "warehouse": ["like", "%SFD%"]},
		)
		if has_sfd_wh or (sfd_company and row.company == sfd_company):
			names.add(row.name)

	for name in sorted(names):
		try:
			doc = frappe.get_doc("Stock Reconciliation", name)
			if doc.docstatus == 1:
				doc.cancel()
				cancelled.append(name)
				doc.reload()
			# After cancel, delete cancelled/draft docs
			frappe.delete_doc(
				"Stock Reconciliation",
				name,
				force=1,
				ignore_permissions=True,
			)
			deleted.append(name)
			frappe.db.commit()
		except Exception as exc:
			frappe.db.rollback()
			errors.append({"name": name, "error": str(exc)})

	message = (
		f"[local_stock_setup] cleanup_sfd_stock: cancelled={len(cancelled)}, "
		f"deleted={len(deleted)}, errors={len(errors)}"
	)
	print(message)
	if cancelled:
		print(f"[local_stock_setup] Cancelled: {', '.join(cancelled)}")
	if deleted:
		print(f"[local_stock_setup] Deleted: {', '.join(deleted)}")
	if errors:
		print(f"[local_stock_setup] Cleanup errors: {errors}")

	return {
		"sfd_company": sfd_company,
		"cancelled": cancelled,
		"deleted": deleted,
		"errors": errors,
		"message": message,
	}


def create_missing_items():
	"""Create demo Raw Material items if they do not already exist."""
	_ensure_item_group("Raw Material")
	created = []
	existing = []

	for spec in ITEMS_TO_ENSURE:
		item_code = spec["item_code"]
		if frappe.db.exists("Item", item_code):
			existing.append(item_code)
			continue

		uom = _resolve_uom(spec["stock_uom"], spec.get("uom_fallbacks") or [])
		doc = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_code,
				"item_name": item_code,
				"item_group": "Raw Material",
				"stock_uom": uom,
				"is_stock_item": 1,
				"include_item_in_manufacturing": 1,
				"valuation_method": "FIFO",
			}
		)
		doc.insert(ignore_permissions=True)
		created.append(item_code)

	frappe.db.commit()
	message = (
		f"[local_stock_setup] create_missing_items: created={created}, already_existed={existing}"
	)
	print(message)
	return {"created": created, "existing": existing, "message": message}


def ensure_tape_edge_meter_uom():
	"""
	Force Tape Edge base UOM to Meter.

	ERPNext blocks stock_uom changes after any Stock Ledger Entry exists,
	even at zero qty. For this local-only script we clear Tape Edge SLE/Bin
	rows, change the UOM, then let inject_sf_stock repost stock in meters.
	"""
	item_code = TAPE_EDGE_ITEM
	if not frappe.db.exists("Item", item_code):
		message = f"[local_stock_setup] {item_code} does not exist yet; skip UOM fix."
		print(message)
		return {"item_code": item_code, "changed": False, "message": message}

	item = frappe.get_doc("Item", item_code)
	target_uom = _resolve_uom("Meter", ["Metre", "m"])
	if item.stock_uom == target_uom:
		message = f"[local_stock_setup] {item_code} already uses stock_uom={target_uom}."
		print(message)
		return {"item_code": item_code, "changed": False, "stock_uom": target_uom, "message": message}

	# Soft zero first (best-effort), then hard-clear local ledger rows
	zeroed = _zero_item_stock(item_code)
	sle_count = frappe.db.count("Stock Ledger Entry", {"item_code": item_code})
	bin_count = frappe.db.count("Bin", {"item_code": item_code})
	frappe.db.delete("Stock Ledger Entry", {"item_code": item_code})
	frappe.db.delete("Bin", {"item_code": item_code})
	frappe.db.commit()

	item.reload()
	item.stock_uom = target_uom
	item.set("uoms", [])
	item.append("uoms", {"uom": target_uom, "conversion_factor": 1})
	item.save(ignore_permissions=True)
	frappe.db.commit()

	message = (
		f"[local_stock_setup] {item_code} stock_uom changed to {target_uom} "
		f"(cleared {sle_count} SLE / {bin_count} Bin; zeroed warehouses={zeroed})."
	)
	print(message)
	return {
		"item_code": item_code,
		"changed": True,
		"stock_uom": target_uom,
		"cleared_sle": sle_count,
		"cleared_bins": bin_count,
		"zeroed_warehouses": zeroed,
		"message": message,
	}


def _zero_item_stock(item_code):
	"""Set actual qty to 0 via Stock Reconciliation so stock_uom can change."""
	zeroed = []
	bins = frappe.get_all(
		"Bin",
		filters={"item_code": item_code, "actual_qty": [">", 0]},
		fields=["warehouse", "actual_qty", "valuation_rate"],
	)
	if not bins:
		return zeroed

	# Group by company via warehouse
	by_company = {}
	for row in bins:
		company = frappe.db.get_value("Warehouse", row.warehouse, "company")
		by_company.setdefault(company, []).append(row)

	for company, rows in by_company.items():
		expense_account = _resolve_stock_adjustment_account(company)
		if not expense_account:
			frappe.throw(f"No Stock Adjustment account for company {company} (needed to zero {item_code}).")

		sr = frappe.new_doc("Stock Reconciliation")
		sr.company = company
		sr.purpose = "Stock Reconciliation"
		sr.posting_date = nowdate()
		sr.set_posting_time = 1
		sr.expense_account = expense_account
		for row in rows:
			sr.append(
				"items",
				{
					"item_code": item_code,
					"warehouse": row.warehouse,
					"qty": 0,
					"valuation_rate": flt(row.valuation_rate) or 1,
					"allow_zero_valuation_rate": 0,
				},
			)
			zeroed.append(row.warehouse)
		sr.insert(ignore_permissions=True)
		sr.submit()
		frappe.db.commit()

	return zeroed


def inject_sf_stock(force=0):
	"""Inject demo stock into Company SF Stores warehouse via Stock Reconciliation."""
	company = _resolve_sf_company()
	warehouse = _resolve_sf_stores_warehouse(company)
	expense_account = _resolve_stock_adjustment_account(company)

	if not company:
		frappe.throw("Could not resolve Company SF (e.g. Solarfoam / abbr SF).")
	if not warehouse:
		frappe.throw(f"Could not resolve Stores warehouse for company {company}.")
	if not expense_account:
		frappe.throw(f"Could not resolve Stock Adjustment account for company {company}.")

	return _inject_stock(
		company=company,
		warehouse=warehouse,
		expense_account=expense_account,
		force=force,
	)


def inject_test_stock(warehouse=None, expense_account=None, force=0):
	"""
	Backwards-compatible entry point.
	Prefer run_local_stock_setup() for the full SF fix flow.
	"""
	return run_local_stock_setup() if warehouse is None and expense_account is None else _inject_stock(
		company=_resolve_sf_company(),
		warehouse=warehouse or _resolve_sf_stores_warehouse(_resolve_sf_company()),
		expense_account=expense_account
		or _resolve_stock_adjustment_account(_resolve_sf_company()),
		force=force,
	)


def _inject_stock(company, warehouse, expense_account, force=0):
	reconciliation = frappe.new_doc("Stock Reconciliation")
	reconciliation.company = company
	reconciliation.purpose = "Stock Reconciliation"
	reconciliation.posting_date = nowdate()
	reconciliation.set_posting_time = 1
	reconciliation.expense_account = expense_account

	stocked = []
	already_ok = []
	skipped_missing = []
	skipped_errors = []

	for demo_code, values in demo_stock_data.items():
		item_code = _resolve_item_code(demo_code)
		if not item_code:
			skipped_missing.append(demo_code)
			continue

		target_qty = flt(values["qty"])
		target_rate = flt(values["rate"])
		current_qty, current_rate = _get_bin_qty_rate(item_code, warehouse)

		if not cint(force) and flt(current_qty) == target_qty and flt(current_rate) == target_rate:
			already_ok.append(item_code)
			continue

		try:
			reconciliation.append(
				"items",
				{
					"item_code": item_code,
					"warehouse": warehouse,
					"qty": target_qty,
					"valuation_rate": target_rate,
					"allow_zero_valuation_rate": 0,
				},
			)
			stocked.append(
				{
					"demo_key": demo_code,
					"item_code": item_code,
					"qty": target_qty,
					"rate": target_rate,
					"previous_qty": current_qty,
					"previous_rate": current_rate,
				}
			)
		except Exception as exc:
			skipped_errors.append({"item": demo_code, "error": str(exc)})

	if not reconciliation.items:
		message = (
			f"[local_stock_setup] No Stock Reconciliation needed. "
			f"{len(already_ok)} item(s) already match target qty/rate in {warehouse}."
		)
		print(message)
		if skipped_missing:
			print(f"[local_stock_setup] Skipped (Item not found): {', '.join(skipped_missing)}")
		return {
			"stock_reconciliation": None,
			"warehouse": warehouse,
			"expense_account": expense_account,
			"company": company,
			"stocked_count": 0,
			"already_ok": already_ok,
			"skipped_missing": skipped_missing,
			"skipped_errors": skipped_errors,
			"message": message,
		}

	reconciliation.insert(ignore_permissions=True)
	reconciliation.submit()
	frappe.db.commit()

	message = (
		f"[local_stock_setup] Stock Reconciliation {reconciliation.name} submitted. "
		f"Stocked/valued {len(stocked)} item(s) in {warehouse} ({company})."
	)
	print(message)
	if already_ok:
		print(f"[local_stock_setup] Already OK (unchanged): {', '.join(already_ok)}")
	if skipped_missing:
		print(f"[local_stock_setup] Skipped (Item not found): {', '.join(skipped_missing)}")
	if skipped_errors:
		print(f"[local_stock_setup] Skipped (errors): {skipped_errors}")

	return {
		"stock_reconciliation": reconciliation.name,
		"warehouse": warehouse,
		"expense_account": expense_account,
		"company": company,
		"stocked_count": len(stocked),
		"stocked": stocked,
		"already_ok": already_ok,
		"skipped_missing": skipped_missing,
		"skipped_errors": skipped_errors,
		"message": message,
	}


def _ensure_item_group(group_name):
	if frappe.db.exists("Item Group", group_name):
		return group_name

	parent = "All Item Groups"
	if not frappe.db.exists("Item Group", parent):
		parents = frappe.get_all("Item Group", filters={"is_group": 1}, pluck="name", limit=1)
		parent = parents[0] if parents else None

	doc = frappe.get_doc(
		{
			"doctype": "Item Group",
			"item_group_name": group_name,
			"parent_item_group": parent,
			"is_group": 0,
		}
	)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return group_name


def _resolve_uom(preferred, fallbacks):
	for name in [preferred, *(fallbacks or [])]:
		if name and frappe.db.exists("UOM", name):
			return name
	# Create preferred UOM if nothing exists
	if preferred and not frappe.db.exists("UOM", preferred):
		frappe.get_doc({"doctype": "UOM", "uom_name": preferred}).insert(ignore_permissions=True)
		frappe.db.commit()
		return preferred
	frappe.throw(f"Could not resolve UOM for {preferred}")


def _get_bin_qty_rate(item_code, warehouse):
	row = frappe.db.get_value(
		"Bin",
		{"item_code": item_code, "warehouse": warehouse},
		["actual_qty", "valuation_rate"],
		as_dict=True,
	)
	if not row:
		return 0.0, 0.0
	return flt(row.actual_qty), flt(row.valuation_rate)


def _resolve_item_code(demo_code):
	candidate = ITEM_ALIASES.get(demo_code, demo_code)
	if frappe.db.exists("Item", candidate):
		return candidate
	by_name = frappe.db.get_value("Item", {"item_name": demo_code}, "name")
	if by_name:
		return by_name
	if frappe.db.exists("Item", demo_code):
		return demo_code
	return None


def _resolve_sf_company():
	# Prefer exact primary company
	if frappe.db.exists("Company", "Solarfoam"):
		return "Solarfoam"
	by_abbr = frappe.db.get_value("Company", {"abbr": "SF"}, "name")
	if by_abbr:
		return by_abbr
	# Name contains Solarfoam but not Demo
	for row in frappe.get_all("Company", fields=["name", "abbr"]):
		if row.abbr == "SF" or (row.name.endswith("SF") and "Demo" not in row.name):
			return row.name
		if "Solarfoam" in row.name and "Demo" not in row.name:
			return row.name
	return None


def _resolve_sfd_company():
	if frappe.db.exists("Company", "Solarfoam (Demo)"):
		return "Solarfoam (Demo)"
	by_abbr = frappe.db.get_value("Company", {"abbr": "SFD"}, "name")
	if by_abbr:
		return by_abbr
	for row in frappe.get_all("Company", fields=["name", "abbr"]):
		if row.abbr == "SFD" or "Demo" in row.name:
			return row.name
	return None


def _resolve_sf_stores_warehouse(company):
	for name in (f"Stores - {_company_abbr(company)}", "Stores - SF"):
		if frappe.db.exists("Warehouse", name):
			wh_company = frappe.db.get_value("Warehouse", name, "company")
			if not wh_company or wh_company == company:
				return name
	rows = frappe.get_all(
		"Warehouse",
		filters={"company": company, "disabled": 0, "name": ["like", "%Stores%"]},
		pluck="name",
		limit=1,
	)
	return rows[0] if rows else None


def _resolve_stock_adjustment_account(company):
	abbr = _company_abbr(company)
	for name in (
		f"5119 - Stock Adjustment - {abbr}",
		f"Stock Adjustment - {abbr}",
	):
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


def _company_abbr(company):
	return frappe.db.get_value("Company", company, "abbr") or ""
