# Copyright (c) 2026, Happifoam and contributors
# For license information, please see license.txt

"""Manual demo / test master-data helpers.

NOT wired into after_install / after_migrate. Run explicitly, e.g.:

    bench --site <site> execute pu_foam_master.utils.demo_data.seed_test_items
    bench --site <site> execute pu_foam_master.utils.demo_data.seed_raw_materials_stock \\
        --kwargs '{"company":"Solarfoam","target_warehouse":"Work In Progress - SF"}'
"""

from __future__ import annotations

import frappe
from frappe.utils import nowdate, nowtime


def seed_test_items():
	"""Create continuous/test Items used in local QA. Idempotent."""
	_ensure_uom("Meter")
	_ensure_item_group("Sub Assembly", parent="All Item Groups", is_group=0)
	_ensure_item_group("Quilted Fabric", parent="All Item Groups", is_group=0)

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

	frappe.db.commit()
	print(f"Successfully generated {count} test items.")
	return count


def seed_raw_materials_stock(
	company="Solarfoam",
	target_warehouse="Work In Progress - SF",
	qty=10000,
):
	"""
	Material Receipt of Tape Edge + Raw Damask Fabric into a WIP warehouse.

	Uses live posting_date / posting_time to avoid Stock Ledger backdate errors.
	Manual only — not wired into install/migrate hooks.
	"""
	if not company:
		frappe.throw("company is required")
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

	_ensure_uom("Meter")
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

	se = frappe.new_doc("Stock Entry")
	se.stock_entry_type = "Material Receipt"
	se.purpose = "Material Receipt"
	se.company = company
	# CRITICAL: live server clock — avoids backdated SLE timestamp errors
	se.posting_date = nowdate()
	se.posting_time = nowtime()
	se.set_posting_time = 1

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

	se.insert(ignore_permissions=True)
	se.submit()
	frappe.db.commit()

	msg = (
		f"Successfully received stock into {target_warehouse}. "
		f"Stock Entry: {se.name}. Fabric Batch: {fabric_batch}"
	)
	print(msg)
	return {
		"stock_entry": se.name,
		"warehouse": target_warehouse,
		"company": company,
		"fabric_batch": fabric_batch,
		"qty": qty,
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


def _ensure_raw_item(spec):
	item_code = spec["item_code"]
	if frappe.db.exists("Item", item_code):
		return item_code

	doc = frappe.new_doc("Item")
	doc.item_code = item_code
	doc.item_name = item_code
	doc.item_group = "Raw Material"
	doc.stock_uom = spec.get("stock_uom") or "Meter"
	doc.is_stock_item = 1
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
