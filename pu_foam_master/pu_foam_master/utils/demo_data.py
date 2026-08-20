# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

"""Manual demo / test master-data helpers.

NOT wired into after_install / after_migrate. Run explicitly, e.g.:

    bench --site <site> execute pu_foam_master.utils.demo_data.seed_test_items
    bench --site <site> execute pu_foam_master.utils.demo_data.seed_e2e_test_stock
    bench --site <site> execute pu_foam_master.utils.demo_data.seed_raw_materials_stock \\
        --kwargs '{"company":null,"target_warehouse":null}'
"""

from __future__ import annotations

import frappe
from frappe.utils import cint, flt, nowdate, nowtime

from pu_foam_master.pufm_manufacturing.utils.density_bom import get_preferred_company

# E2E inject quantities / default valuation rates (NGN)
E2E_CHEMICALS = (
	{"item_code": "POLYOL", "aliases": ("Polyol",), "qty": 50000, "uom": "Kg", "rate": 1800},
	{"item_code": "TDI", "aliases": ("TDI",), "qty": 25000, "uom": "Kg", "rate": 4500},
	{"item_code": "MDI-BINDER", "aliases": ("MDI", "MDI Binder"), "qty": 10000, "uom": "Kg", "rate": 4000},
)
E2E_CONSUMABLES = (
	{"item_code": "Tape Edge", "aliases": ("Tape Edge",), "qty": 10000, "uom": "Meter", "rate": 50, "settings_field": "default_tape_edge_item"},
	{"item_code": "PVC Nylon", "aliases": ("PVC Nylon", "PVC/Nylon", "PVC-NYLON"), "qty": 5000, "uom": "Sqm", "rate": 350, "settings_field": "default_pvc_nylon_item"},
	{"item_code": "Thread", "aliases": ("Thread",), "qty": 5000, "uom": "Nos", "rate": 25, "settings_field": "default_thread_item"},
	{"item_code": "Labels", "aliases": ("Labels", "Label"), "qty": 5000, "uom": "Nos", "rate": 15, "settings_field": "default_label_item"},
)
E2E_SCRAP = {"item_code": "SCRAP-FOAM", "aliases": ("SCRAP-FOAM", "Scrap Foam"), "qty": 20000, "uom": "Kg", "rate": 80}


def seed_test_items():
	"""Create continuous/test Items used in local QA. Idempotent."""
	_ensure_uom("Meter")
	_ensure_uom("Kg")
	_ensure_uom("Nos")
	_ensure_item_group("Sub Assembly", parent="All Item Groups", is_group=0)
	_ensure_item_group("Quilted Fabric", parent="All Item Groups", is_group=0)
	_ensure_item_group("Raw Material", parent="All Item Groups", is_group=0)
	_ensure_item_group("Products", parent="All Item Groups", is_group=0)

	# Rename legacy non-Roll foam sheet names if present
	renames = {
		"Foam Sheet - 0.5 Inch": "Foam Sheet Roll - 0.5 Inch",
		"Foam Sheet - 1.0 Inch": "Foam Sheet Roll - 1.0 Inch",
	}
	for old_code, new_code in renames.items():
		if frappe.db.exists("Item", old_code) and not frappe.db.exists("Item", new_code):
			frappe.rename_doc("Item", old_code, new_code, force=True, merge=False)

	items = [
		{
			"item_code": "QUILTED-DAMASK-FLORA",
			"item_name": "Quilted Damask - Flora",
			"item_group": "Quilted Fabric",
			"stock_uom": "Meter",
			"is_stock_item": 1,
			"has_batch_no": 1,
			"create_new_batch": 1,
			"has_serial_no": 0,
			"custom_width": 84.0,
			"custom_length": 39.37,
			"custom_height": 0.5,
			"custom_cbm_value": 0.02709,
		},
		{
			"item_code": "Foam Sheet Roll - 0.5 Inch",
			"item_name": "Foam Sheet Roll - 0.5 Inch",
			"item_group": "Sub Assembly",
			"stock_uom": "Meter",
			"is_stock_item": 1,
			"include_item_in_manufacturing": 1,
			"has_batch_no": 1,
			"create_new_batch": 1,
			"has_serial_no": 0,
			"serial_no_series": "",
			"custom_width": 84.0,
			"custom_length": 39.37,
			"custom_height": 0.5,
			"custom_cbm_value": 0.02709,
		},
		{
			"item_code": "Foam Sheet Roll - 1.0 Inch",
			"item_name": "Foam Sheet Roll - 1.0 Inch",
			"item_group": "Sub Assembly",
			"stock_uom": "Meter",
			"is_stock_item": 1,
			"include_item_in_manufacturing": 1,
			"has_batch_no": 1,
			"create_new_batch": 1,
			"has_serial_no": 0,
			"serial_no_series": "",
			"custom_width": 84.0,
			"custom_length": 39.37,
			"custom_height": 1.0,
			"custom_cbm_value": 0.05419,
		},
		# Rebound Foam masters
		{
			"item_code": "SCRAP-FOAM",
			"item_name": "Scrap Foam",
			"item_group": "Raw Material",
			"stock_uom": "Kg",
			"is_stock_item": 1,
			"has_batch_no": 0,
			"has_serial_no": 0,
		},
		{
			"item_code": "MDI-BINDER",
			"item_name": "MDI Binder",
			"item_group": "Raw Material",
			"stock_uom": "Kg",
			"is_stock_item": 1,
			"has_batch_no": 1,
			"create_new_batch": 1,
			"has_serial_no": 0,
		},
		{
			"item_code": "REB-70-BLOCK-84x75x20",
			"item_name": "Rebound Block 70 - 84x75x20",
			"item_group": "Products",
			"stock_uom": "Nos",
			"is_stock_item": 1,
			"include_item_in_manufacturing": 1,
			"has_batch_no": 1,
			"create_new_batch": 1,
			"has_serial_no": 0,
			"custom_length": 84.0,
			"custom_width": 75.0,
			"custom_height": 20.0,
			"custom_cbm_value": (84.0 * 75.0 * 20.0) / 61023.74,
		},
	]

	count = 0
	for data in items:
		item_code = data["item_code"]
		if frappe.db.exists("Item", item_code):
			continue
		doc = frappe.new_doc("Item")
		doc.update(data)
		doc.insert(ignore_permissions=True)
		count += 1

	_link_rebound_settings_items()
	frappe.db.commit()
	print(f"Successfully generated {count} test items.")
	return count


def seed_e2e_test_stock():
	"""Inject chemicals, mattress consumables, and scrap for End-to-End testing.

	Creates/ensures stock Items (maintain_stock / is_stock_item = 1), links Settings,
	and submits Material Receipt Stock Entries into Settings warehouses.

	Manual only — not wired into install/migrate hooks.
	"""
	company = get_preferred_company()
	if not company:
		frappe.throw("No Company found. Set Default Company in Global Defaults or PUFM Settings.")

	settings = frappe.get_single("Pufm Manufacturing Settings")
	if not settings.default_company:
		settings.default_company = company

	rm_wh = settings.default_raw_material_warehouse or _resolve_warehouse(
		company, ("Stores", "Raw Material")
	)
	wip_wh = settings.default_wip_warehouse or _resolve_warehouse(
		company, ("Goods In Transit", "Work In Progress", "WIP")
	)
	scrap_wh = settings.default_scrap_warehouse or _resolve_warehouse(
		company, ("Scrap", "Stores")
	)
	if not rm_wh:
		frappe.throw(
			"Could not resolve Raw Material Warehouse. Set Default Raw Material Warehouse "
			"in Pufm Manufacturing Settings."
		)
	if not wip_wh:
		frappe.throw(
			"Could not resolve WIP warehouse. Set Default WIP Warehouse "
			"in Pufm Manufacturing Settings (typically Goods In Transit)."
		)
	if not scrap_wh:
		frappe.throw(
			"Could not resolve Scrap Warehouse. Set Default Scrap Warehouse "
			"in Pufm Manufacturing Settings."
		)

	settings.default_raw_material_warehouse = rm_wh
	settings.default_wip_warehouse = wip_wh
	settings.default_scrap_warehouse = scrap_wh

	_ensure_uom("Kg")
	_ensure_uom("Meter")
	_ensure_uom("Sqm")
	_ensure_uom("Nos")
	_ensure_item_group("Raw Material", parent="All Item Groups", is_group=0)

	# Ensure stocked masters + valuation rates (local copies — do not mutate module constants)
	chemicals = [dict(s) for s in E2E_CHEMICALS]
	consumables = [dict(s) for s in E2E_CONSUMABLES]
	scrap = dict(E2E_SCRAP)

	for spec in chemicals + consumables + [scrap]:
		item_code = _ensure_stock_item(spec)
		spec["resolved_code"] = item_code
		# Prefer Item stock UOM for receipt rows
		spec["uom"] = frappe.db.get_value("Item", item_code, "stock_uom") or spec["uom"]

	for spec in consumables:
		field = spec.get("settings_field")
		if field:
			setattr(settings, field, spec["resolved_code"])

	settings.scrap_item = scrap.get("resolved_code") or "SCRAP-FOAM"
	settings.mdi_item = next(
		(s["resolved_code"] for s in chemicals if s["item_code"] == "MDI-BINDER"),
		settings.mdi_item,
	)
	settings.flags.ignore_validate = True
	settings.save(ignore_permissions=True)

	# Pouring chemicals → WIP / Goods In Transit (Production Batch source warehouse)
	chem_rows = [
		{
			"item_code": spec["resolved_code"],
			"qty": spec["qty"],
			"uom": spec["uom"],
			"rate": spec["rate"],
		}
		for spec in chemicals
	]
	chem_se = _submit_material_receipt(
		company, wip_wh, chem_rows, remarks="E2E pouring chemicals into WIP"
	)

	# Mattress consumables → Raw Material Warehouse (Mattress Production backflush)
	rm_rows = [
		{
			"item_code": spec["resolved_code"],
			"qty": spec["qty"],
			"uom": spec["uom"],
			"rate": spec["rate"],
		}
		for spec in consumables
	]
	rm_se = _submit_material_receipt(
		company, rm_wh, rm_rows, remarks="E2E mattress consumables"
	)

	# Scrap → Scrap Warehouse
	scrap_se = _submit_material_receipt(
		company,
		scrap_wh,
		[
			{
				"item_code": scrap["resolved_code"],
				"qty": scrap["qty"],
				"uom": scrap["uom"],
				"rate": scrap["rate"],
			}
		],
		remarks="E2E scrap foam",
	)

	frappe.db.commit()
	result = {
		"company": company,
		"wip_warehouse": wip_wh,
		"raw_material_warehouse": rm_wh,
		"scrap_warehouse": scrap_wh,
		"chemicals_stock_entry": chem_se.name,
		"consumables_stock_entry": rm_se.name,
		"scrap_stock_entry": scrap_se.name,
		"injected": {
			**{s["resolved_code"]: s["qty"] for s in chemicals + consumables},
			scrap["resolved_code"]: scrap["qty"],
		},
	}
	print("E2E stock seeding complete:")
	for key, value in result.items():
		print(f"  {key}: {value}")
	return result


def seed_raw_materials_stock(
	company=None,
	target_warehouse=None,
	qty=10000,
):
	"""
	Material Receipt of mattress + Rebound raw materials into a WIP warehouse.

	Uses live posting_date / posting_time to avoid Stock Ledger backdate errors.
	Manual only — not wired into install/migrate hooks.
	"""
	company = company or get_preferred_company()
	if not company:
		frappe.throw("company is required")
	if not target_warehouse:
		target_warehouse = frappe.db.get_single_value(
			"Pufm Manufacturing Settings", "default_wip_warehouse"
		) or _resolve_warehouse(company, ("Work In Progress", "Stores"))
	if not target_warehouse:
		frappe.throw("target_warehouse is required")
	if not frappe.db.exists("Company", company):
		frappe.throw(f"Company not found: {company}")
	if not frappe.db.exists("Warehouse", target_warehouse):
		frappe.throw(f"Warehouse not found: {target_warehouse}")

	wh_company = frappe.db.get_value("Warehouse", target_warehouse, "company")
	if wh_company and wh_company != company:
		frappe.throw(
			f"Warehouse {target_warehouse} belongs to {wh_company}, not {company}."
		)

	# Ensure item masters exist first
	seed_test_items()

	_ensure_uom("Meter")
	_ensure_uom("Kg")
	_ensure_item_group("Raw Material", parent="All Item Groups", is_group=0)

	items_to_ensure = [
		{
			"item_code": "Tape Edge",
			"stock_uom": "Meter",
			"has_batch_no": 0,
			"basic_rate": 50,
		},
		{
			"item_code": "Raw Damask Fabric",
			"stock_uom": "Meter",
			"has_batch_no": 1,
			"create_new_batch": 1,
			"basic_rate": 1200,
		},
	]

	for spec in items_to_ensure:
		_ensure_raw_item(spec)

	# Ensure Damask is batch-tracked if it already existed without batches
	if frappe.db.exists("Item", "Raw Damask Fabric"):
		flags = frappe.db.get_value(
			"Item",
			"Raw Damask Fabric",
			["has_batch_no", "create_new_batch"],
			as_dict=True,
		)
		if flags and not flags.has_batch_no:
			try:
				item = frappe.get_doc("Item", "Raw Damask Fabric")
				item.has_batch_no = 1
				item.create_new_batch = 1
				item.has_serial_no = 0
				item.save(ignore_permissions=True)
			except Exception:
				frappe.db.set_value(
					"Item",
					"Raw Damask Fabric",
					{"has_batch_no": 1, "create_new_batch": 1, "has_serial_no": 0},
					update_modified=True,
				)

	fabric_batch = f"BATCH-DAMASK-{nowdate().replace('-', '')}"
	if not frappe.db.exists("Batch", fabric_batch):
		b = frappe.new_doc("Batch")
		b.batch_id = fabric_batch
		b.item = "Raw Damask Fabric"
		b.insert(ignore_permissions=True)

	mdi_batch = f"BATCH-MDI-{nowdate().replace('-', '')}"
	if not frappe.db.exists("Batch", mdi_batch):
		b = frappe.new_doc("Batch")
		b.batch_id = mdi_batch
		b.item = "MDI-BINDER"
		b.insert(ignore_permissions=True)

	se = frappe.new_doc("Stock Entry")
	se.stock_entry_type = "Material Receipt"
	se.purpose = "Material Receipt"
	se.company = company
	# CRITICAL: live server clock — avoids backdated SLE timestamp errors
	se.posting_date = nowdate()
	se.posting_time = nowtime()
	se.set_posting_time = 1

	# Mattress consumables
	se.append(
		"items",
		{
			"item_code": "Tape Edge",
			"t_warehouse": target_warehouse,
			"qty": qty,
			"uom": "Meter",
			"stock_uom": "Meter",
			"conversion_factor": 1,
			"basic_rate": 50,
			"valuation_rate": 50,
			"allow_zero_valuation_rate": 0,
		},
	)
	se.append(
		"items",
		{
			"item_code": "Raw Damask Fabric",
			"t_warehouse": target_warehouse,
			"qty": qty,
			"uom": "Meter",
			"stock_uom": "Meter",
			"conversion_factor": 1,
			"basic_rate": 1200,
			"valuation_rate": 1200,
			"batch_no": fabric_batch,
			"use_serial_batch_fields": 1,
			"allow_zero_valuation_rate": 0,
		},
	)

	# Rebound inputs
	se.append(
		"items",
		{
			"item_code": "SCRAP-FOAM",
			"t_warehouse": target_warehouse,
			"qty": 5000,
			"uom": "Kg",
			"stock_uom": "Kg",
			"conversion_factor": 1,
			"basic_rate": 80,
			"valuation_rate": 80,
			"allow_zero_valuation_rate": 0,
		},
	)
	se.append(
		"items",
		{
			"item_code": "MDI-BINDER",
			"t_warehouse": target_warehouse,
			"qty": 1000,
			"uom": "Kg",
			"stock_uom": "Kg",
			"conversion_factor": 1,
			"basic_rate": 4000,
			"valuation_rate": 4000,
			"batch_no": mdi_batch,
			"use_serial_batch_fields": 1,
			"allow_zero_valuation_rate": 0,
		},
	)

	se.insert(ignore_permissions=True)
	se.submit()
	_link_rebound_settings_items()
	frappe.db.commit()

	msg = (
		f"Successfully received stock into {target_warehouse}. "
		f"Stock Entry: {se.name}. Fabric Batch: {fabric_batch}. MDI Batch: {mdi_batch}"
	)
	print(msg)
	return {
		"stock_entry": se.name,
		"warehouse": target_warehouse,
		"company": company,
		"fabric_batch": fabric_batch,
		"mdi_batch": mdi_batch,
		"qty": qty,
		"scrap_qty": 5000,
		"mdi_qty": 1000,
	}


def seed_standard_mattress_sizes():
	"""Optional: seed Standard Mattress Size rows for local QA. Idempotent."""
	sizes = [
		("7x6x10", 75, 84, 10),
		("6x6x10", 72, 84, 10),
		("5x6x10", 60, 84, 10),
		("4.5x6x10", 54, 84, 10),
		("3.5x6x8", 42, 84, 8),
		("3x6x6", 36, 84, 6),
	]

	count = 0
	for size_name, width, length, height in sizes:
		if frappe.db.exists("Standard Mattress Size", size_name):
			continue
		frappe.get_doc(
			{
				"doctype": "Standard Mattress Size",
				"size_name": size_name,
				"width_inches": width,
				"length_inches": length,
				"height_inches": height,
			}
		).insert(ignore_permissions=True)
		count += 1

	frappe.db.commit()
	print(f"Successfully generated {count} standard mattress sizes.")
	return count


def _link_rebound_settings_items():
	"""Point Manufacturing Settings at Rebound demo items when blank."""
	if not frappe.db.exists("DocType", "Pufm Manufacturing Settings"):
		return
	if frappe.db.exists("Item", "SCRAP-FOAM") and not frappe.db.get_single_value(
		"Pufm Manufacturing Settings", "scrap_item"
	):
		frappe.db.set_single_value("Pufm Manufacturing Settings", "scrap_item", "SCRAP-FOAM")
	if frappe.db.exists("Item", "MDI-BINDER") and not frappe.db.get_single_value(
		"Pufm Manufacturing Settings", "mdi_item"
	):
		frappe.db.set_single_value("Pufm Manufacturing Settings", "mdi_item", "MDI-BINDER")


def _resolve_warehouse(company, name_hints):
	"""Pick a warehouse for company whose name contains any hint (case-insensitive)."""
	warehouses = frappe.get_all(
		"Warehouse",
		filters={"company": company, "is_group": 0, "disabled": 0},
		fields=["name"],
		order_by="name asc",
	)
	lower_hints = [h.lower() for h in name_hints]
	for hint in lower_hints:
		for wh in warehouses:
			if hint in (wh.name or "").lower():
				return wh.name
	return warehouses[0].name if warehouses else None


def _resolve_existing_item(preferred_code, aliases=()):
	candidates = [preferred_code, *(aliases or ())]
	for code in candidates:
		if code and frappe.db.exists("Item", code):
			return code
	# Fuzzy: item_name / item_code contains preferred label
	for code in candidates:
		if not code:
			continue
		match = frappe.db.get_value("Item", {"item_name": code}, "name")
		if match:
			return match
	return None


def _ensure_stock_item(spec):
	"""Ensure Item exists with is_stock_item=1 and a default valuation_rate."""
	preferred = spec["item_code"]
	desired_uom = spec.get("uom") or "Nos"
	rate = flt(spec.get("rate"))
	_ensure_uom(desired_uom)

	# Prefer exact preferred code
	item_code = preferred if frappe.db.exists("Item", preferred) else None
	if not item_code:
		# Only reuse an alias when stock UOM matches the desired UOM
		for alias in spec.get("aliases") or ():
			if alias and frappe.db.exists("Item", alias):
				alias_uom = frappe.db.get_value("Item", alias, "stock_uom")
				if not desired_uom or alias_uom == desired_uom:
					item_code = alias
					break

	if item_code:
		doc = frappe.get_doc("Item", item_code)
		changed = False
		if not cint(doc.is_stock_item):
			doc.is_stock_item = 1
			changed = True
		if rate > 0 and flt(doc.valuation_rate) <= 0:
			doc.valuation_rate = rate
			changed = True
		if changed:
			doc.save(ignore_permissions=True)
		return item_code

	doc = frappe.new_doc("Item")
	doc.item_code = preferred
	doc.item_name = preferred
	doc.item_group = "Raw Material"
	doc.stock_uom = desired_uom
	doc.is_stock_item = 1
	doc.valuation_rate = rate
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
			batch_id = _ensure_receipt_batch(item_code)
			line["batch_no"] = batch_id
			line["use_serial_batch_fields"] = 1
		se.append("items", line)

	se.insert(ignore_permissions=True)
	se.submit()
	return se


def _ensure_receipt_batch(item_code):
	batch_id = f"E2E-{item_code}-{nowdate().replace('-', '')}"
	# Batch.name may differ from batch_id depending on naming
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


def _ensure_raw_item(spec):
	item_code = spec["item_code"]
	if frappe.db.exists("Item", item_code):
		# Enforce stocked + valuation when used by seeders
		doc = frappe.get_doc("Item", item_code)
		changed = False
		if not cint(doc.is_stock_item):
			doc.is_stock_item = 1
			changed = True
		rate = flt(spec.get("basic_rate"))
		if rate > 0 and flt(doc.valuation_rate) <= 0:
			doc.valuation_rate = rate
			changed = True
		if changed:
			doc.save(ignore_permissions=True)
		return item_code

	doc = frappe.new_doc("Item")
	doc.item_code = item_code
	doc.item_name = item_code
	doc.item_group = "Raw Material"
	doc.stock_uom = spec.get("stock_uom") or "Meter"
	doc.is_stock_item = 1
	doc.valuation_rate = flt(spec.get("basic_rate"))
	doc.has_batch_no = 1 if spec.get("has_batch_no") else 0
	doc.create_new_batch = 1 if spec.get("has_batch_no") else 0
	doc.has_serial_no = 0
	doc.insert(ignore_permissions=True)
	return item_code


def _ensure_item_group(group_name, parent="All Item Groups", is_group=0):
	if frappe.db.exists("Item Group", group_name):
		return group_name
	if parent and not frappe.db.exists("Item Group", parent):
		frappe.get_doc(
			{
				"doctype": "Item Group",
				"item_group_name": parent,
				"is_group": 1,
			}
		).insert(ignore_permissions=True, ignore_if_duplicate=True)
	frappe.get_doc(
		{
			"doctype": "Item Group",
			"item_group_name": group_name,
			"parent_item_group": parent,
			"is_group": is_group,
		}
	).insert(ignore_permissions=True, ignore_if_duplicate=True)
	return group_name


def _ensure_uom(uom):
	if frappe.db.exists("UOM", uom):
		return
	frappe.get_doc({"doctype": "UOM", "uom_name": uom}).insert(
		ignore_permissions=True, ignore_if_duplicate=True
	)
