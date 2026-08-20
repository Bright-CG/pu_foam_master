# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

"""One-off container-load stock injection for E2E testing.

Run:
    bench --site <site> execute pu_foam_master.utils.seed_massive_stock.run
"""

from __future__ import annotations

import frappe
from frappe.utils import cint, flt, nowdate, nowtime

from pu_foam_master.pufm_manufacturing.utils.density_bom import get_preferred_company

SETTINGS_DOCTYPE = "Pufm Manufacturing Settings"
FALLBACK_RATE = 1000.0
SCRAP_ITEM = "SCRAP-FOAM"

# Full factory list (20 items) — qty in each item's stock UOM
FACTORY_ITEMS = (
	# Heavy chemicals
	{"item_code": "TDI", "qty": 100_000},
	{"item_code": "15_POLYMERIC", "qty": 100_000},
	{"item_code": "FILLER", "qty": 100_000},
	# Additives & catalysts
	{"item_code": "A33", "qty": 20_000},
	{"item_code": "HARDNER", "qty": 20_000},
	{"item_code": "MC", "qty": 20_000},
	{"item_code": "SILICON", "qty": 20_000},
	{"item_code": "SMP", "qty": 20_000},
	{"item_code": "STANNOUS", "qty": 20_000},
	# Papers & nylons
	{"item_code": "BASE PAPER", "qty": 50_000},
	{"item_code": "RS NYLON", "qty": 50_000},
	{"item_code": "SIDE NYLON", "qty": 50_000},
	# Pigments
	{"item_code": "PIGMENT - BLACK", "qty": 5_000},
	{"item_code": "PIGMENT - RED", "qty": 5_000},
	{"item_code": "PIGMENT - YELLOW", "qty": 5_000},
	{"item_code": "Pigment Blue", "qty": 5_000},
	# Mattress consumables
	{"item_code": "Tape Edge", "qty": 100_000},
	{"item_code": "PVC Nylon", "qty": 100_000},
	{"item_code": "Thread", "qty": 100_000},
	{"item_code": "Labels", "qty": 100_000},
)

SCRAP_QTY = 100_000


def run():
	"""Ensure Settings + inject full 20-item receipts into GIT & RM, scrap into scrap WH."""
	_ensure_settings_single()
	company = _resolve_company()
	rm_wh, git_wh, scrap_wh = _resolve_warehouses(company)
	_persist_warehouse_defaults(company, rm_wh, git_wh, scrap_wh)

	_ensure_uom("Kg")
	_ensure_uom("Meter")
	_ensure_uom("Sqm")
	_ensure_uom("Nos")
	_ensure_item_group("Raw Material")

	rate_report = []
	receipt_rows = []
	for spec in FACTORY_ITEMS:
		item_code = _ensure_stock_item(spec["item_code"])
		rate, rate_source = _resolve_valuation_rate(item_code)
		uom = frappe.db.get_value("Item", item_code, "stock_uom") or "Nos"
		receipt_rows.append(
			{"item_code": item_code, "qty": spec["qty"], "uom": uom, "rate": rate}
		)
		rate_report.append(
			{"item_code": item_code, "basic_rate": rate, "rate_source": rate_source, "uom": uom}
		)

	scrap_code = _ensure_scrap_item()
	scrap_rate, scrap_source = _resolve_valuation_rate(scrap_code)
	scrap_uom = frappe.db.get_value("Item", scrap_code, "stock_uom") or "Kg"
	rate_report.append(
		{
			"item_code": scrap_code,
			"basic_rate": scrap_rate,
			"rate_source": scrap_source,
			"uom": scrap_uom,
		}
	)

	git_se = _submit_material_receipt(
		company,
		git_wh,
		receipt_rows,
		remarks="Massive seed: full factory list → Goods In Transit (backup)",
	)
	rm_se = _submit_material_receipt(
		company,
		rm_wh,
		receipt_rows,
		remarks="Massive seed: full factory list → Raw Material warehouse",
	)
	scrap_se = _submit_material_receipt(
		company,
		scrap_wh,
		[{"item_code": scrap_code, "qty": SCRAP_QTY, "uom": scrap_uom, "rate": scrap_rate}],
		remarks="Massive seed: SCRAP-FOAM → Scrap warehouse",
	)

	# Link scrap + consumables on Settings when blank
	settings = frappe.get_single(SETTINGS_DOCTYPE)
	changed = False
	if not settings.scrap_item:
		settings.scrap_item = scrap_code
		changed = True
	for field, code in (
		("default_tape_edge_item", "Tape Edge"),
		("default_pvc_nylon_item", "PVC Nylon"),
		("default_thread_item", "Thread"),
		("default_label_item", "Labels"),
	):
		if not getattr(settings, field, None) and frappe.db.exists("Item", code):
			setattr(settings, field, code)
			changed = True
	if changed:
		settings.flags.ignore_validate = True
		settings.save(ignore_permissions=True)

	frappe.db.commit()

	historical = sum(1 for r in rate_report if r["rate_source"] != "fallback")
	result = {
		"company": company,
		"goods_in_transit_warehouse": git_wh,
		"raw_material_warehouse": rm_wh,
		"scrap_warehouse": scrap_wh,
		"stock_entry_git": git_se.name,
		"stock_entry_raw_material": rm_se.name,
		"stock_entry_scrap": scrap_se.name,
		"factory_items": len(receipt_rows),
		"scrap_item": scrap_code,
		"scrap_qty": SCRAP_QTY,
		"rates_from_history": historical,
		"rates_fallback": len(rate_report) - historical,
		"valuation_rates": rate_report,
	}
	print("=== MASSIVE STOCK SEED COMPLETE ===")
	for key in (
		"company",
		"goods_in_transit_warehouse",
		"raw_material_warehouse",
		"scrap_warehouse",
		"stock_entry_git",
		"stock_entry_raw_material",
		"stock_entry_scrap",
		"factory_items",
		"scrap_item",
		"scrap_qty",
		"rates_from_history",
		"rates_fallback",
	):
		print(f"  {key}: {result[key]}")
	print("  valuation_rates:")
	for row in rate_report:
		print(
			f"    {row['item_code']}: {row['basic_rate']} ({row['rate_source']}) [{row['uom']}]"
		)
	return result


def ensure_settings():
	"""Public helper: migrate-safe ensure of Pufm Manufacturing Settings Single."""
	return _ensure_settings_single()


def _ensure_settings_single():
	if not frappe.db.exists("DocType", SETTINGS_DOCTYPE):
		frappe.throw(
			f"DocType '{SETTINGS_DOCTYPE}' is not registered. "
			"Run `bench migrate` first."
		)
	doc = frappe.get_single(SETTINGS_DOCTYPE)
	# Touch-save so Singles rows exist; skip fail-fast validate during bootstrap
	doc.flags.ignore_validate = True
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	print(f"Ensured Single DocType accessible: {SETTINGS_DOCTYPE}")
	return doc.name


def _resolve_company():
	"""White-label: Settings → User Default → Global Defaults → first Company.

	Never hardcodes a company name. Shared with the rest of the app via
	``get_preferred_company()``.
	"""
	company = get_preferred_company()
	if not company:
		frappe.throw(
			"No Company found. Set Default Company in Global Defaults "
			"(and optionally Default Company in Pufm Manufacturing Settings)."
		)
	return company


def _warehouse_for_company(company, settings_field, name_hints):
	"""Use Settings warehouse only when it belongs to company; else find by name."""
	wh = frappe.db.get_single_value(SETTINGS_DOCTYPE, settings_field)
	if wh and frappe.db.exists("Warehouse", wh):
		wh_company = frappe.db.get_value("Warehouse", wh, "company")
		if wh_company == company:
			return wh
	return _find_warehouse(company, name_hints)


def _resolve_warehouses(company):
	rm_wh = _warehouse_for_company(
		company, "default_raw_material_warehouse", ("Stores", "Raw Material")
	)
	if not rm_wh:
		frappe.throw(
			f"Could not resolve Raw Material warehouse for company {company}. "
			"Set default_raw_material_warehouse in Pufm Manufacturing Settings."
		)

	git_wh = _warehouse_for_company(
		company,
		"default_wip_warehouse",
		("Goods In Transit", "Work In Progress", "WIP"),
	)
	if not git_wh:
		frappe.throw(
			f"Could not resolve Goods In Transit / WIP warehouse for company {company}. "
			"Set default_wip_warehouse in Pufm Manufacturing Settings."
		)

	scrap_wh = _warehouse_for_company(
		company, "default_scrap_warehouse", ("Scrap Warehouse", "Scrap")
	)
	if not scrap_wh:
		frappe.throw(
			f"Could not resolve Scrap warehouse for company {company}. "
			"Set default_scrap_warehouse in Pufm Manufacturing Settings."
		)

	return rm_wh, git_wh, scrap_wh


def _persist_warehouse_defaults(company, rm_wh, git_wh, scrap_wh):
	settings = frappe.get_single(SETTINGS_DOCTYPE)
	settings.default_company = company
	settings.default_raw_material_warehouse = rm_wh
	settings.default_wip_warehouse = git_wh
	settings.default_scrap_warehouse = scrap_wh
	settings.flags.ignore_validate = True
	settings.save(ignore_permissions=True)


def _find_warehouse(company, name_hints):
	warehouses = frappe.get_all(
		"Warehouse",
		filters={"company": company, "is_group": 0, "disabled": 0},
		fields=["name"],
		order_by="name asc",
	)
	for hint in name_hints:
		hint_l = hint.lower()
		for wh in warehouses:
			if hint_l in (wh.name or "").lower():
				return wh.name
	return None


def _resolve_valuation_rate(item_code):
	"""Prefer Item.valuation_rate, then standard_rate; else FALLBACK_RATE."""
	vals = frappe.db.get_value(
		"Item", item_code, ["valuation_rate", "standard_rate"], as_dict=True
	) or {}
	valuation = flt(vals.get("valuation_rate"))
	if valuation > 0:
		return valuation, "valuation_rate"
	standard = flt(vals.get("standard_rate"))
	if standard > 0:
		return standard, "standard_rate"
	return FALLBACK_RATE, "fallback"


def _ensure_stock_item(item_code):
	if frappe.db.exists("Item", item_code):
		doc = frappe.get_doc("Item", item_code)
		if not cint(doc.is_stock_item):
			doc.is_stock_item = 1
			doc.save(ignore_permissions=True)
		return doc.name

	# Sensible UOM defaults for known factory codes
	uom_map = {
		"Tape Edge": "Meter",
		"PVC Nylon": "Sqm",
		"Thread": "Nos",
		"Labels": "Nos",
	}
	doc = frappe.new_doc("Item")
	doc.item_code = item_code
	doc.item_name = item_code
	doc.item_group = "Raw Material"
	doc.stock_uom = uom_map.get(item_code, "Kg")
	doc.is_stock_item = 1
	doc.has_batch_no = 0
	doc.has_serial_no = 0
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_scrap_item():
	if frappe.db.exists("Item", SCRAP_ITEM):
		doc = frappe.get_doc("Item", SCRAP_ITEM)
		if not cint(doc.is_stock_item):
			doc.is_stock_item = 1
			doc.save(ignore_permissions=True)
		return doc.name

	doc = frappe.new_doc("Item")
	doc.item_code = SCRAP_ITEM
	doc.item_name = "Scrap Foam"
	doc.item_group = "Raw Material"
	doc.stock_uom = "Kg"
	doc.is_stock_item = 1
	doc.has_batch_no = 0
	doc.has_serial_no = 0
	doc.insert(ignore_permissions=True)
	return doc.name


def _submit_material_receipt(company, warehouse, rows, remarks=None):
	se = frappe.new_doc("Stock Entry")
	se.stock_entry_type = "Material Receipt"
	se.purpose = "Material Receipt"
	se.company = company
	se.posting_date = nowdate()
	se.posting_time = nowtime()
	se.set_posting_time = 1
	if remarks:
		se.remarks = remarks

	for row in rows:
		item_code = row["item_code"]
		item = frappe.get_cached_doc("Item", item_code)
		uom = item.stock_uom or row.get("uom") or "Nos"
		rate = flt(row.get("rate"))
		line = {
			"item_code": item_code,
			"t_warehouse": warehouse,
			"qty": flt(row["qty"]),
			"uom": uom,
			"stock_uom": uom,
			"conversion_factor": 1,
			"basic_rate": rate,
			"valuation_rate": rate,
			"allow_zero_valuation_rate": 0 if rate > 0 else 1,
		}
		if cint(item.has_batch_no):
			line["batch_no"] = _ensure_receipt_batch(item_code)
			line["use_serial_batch_fields"] = 1
		se.append("items", line)

	se.insert(ignore_permissions=True)
	se.submit()
	return se


def _ensure_receipt_batch(item_code):
	safe = "".join(c if c.isalnum() else "-" for c in item_code)[:40]
	batch_id = f"MASS-{safe}-{nowdate().replace('-', '')}"
	existing = frappe.db.get_value("Batch", {"batch_id": batch_id, "item": item_code}, "name")
	if existing:
		return existing
	if frappe.db.exists("Batch", batch_id):
		return batch_id
	b = frappe.new_doc("Batch")
	b.batch_id = batch_id
	b.item = item_code
	b.insert(ignore_permissions=True)
	return b.name


def _ensure_uom(uom):
	if uom and not frappe.db.exists("UOM", uom):
		frappe.get_doc({"doctype": "UOM", "uom_name": uom}).insert(ignore_permissions=True)


def _ensure_item_group(name, parent="All Item Groups"):
	if frappe.db.exists("Item Group", name):
		return
	frappe.get_doc(
		{
			"doctype": "Item Group",
			"item_group_name": name,
			"parent_item_group": parent,
			"is_group": 0,
		}
	).insert(ignore_permissions=True)
