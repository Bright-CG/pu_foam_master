# Copyright (c) 2026, Happifoam and contributors
# For license information, please see license.txt

"""Manual demo / test master-data helpers.

NOT wired into after_install / after_migrate. Run explicitly, e.g.:

    bench --site <site> execute pu_foam_master.utils.demo_data.seed_test_items
"""

from __future__ import annotations

import frappe


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
