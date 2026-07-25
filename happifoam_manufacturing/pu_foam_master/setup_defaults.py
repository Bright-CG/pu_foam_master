import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def ensure_default_item_groups():
	if not frappe.db.exists("Item Group", "All Item Groups"):
		frappe.get_doc(
			{
				"doctype": "Item Group",
				"item_group_name": "All Item Groups",
				"is_group": 1,
			}
		).insert(ignore_permissions=True, ignore_if_duplicate=True)

	if not frappe.db.exists("Item Group", "Products"):
		item_group = frappe.get_doc(
			{
				"doctype": "Item Group",
				"item_group_name": "Products",
				"parent_item_group": "All Item Groups",
				"is_group": 1,
			}
		)
		item_group.insert(ignore_permissions=True, ignore_if_duplicate=True)

	frappe.db.commit()


def ensure_standard_mattress_sizes():
	sizes = [
		("7x6x10", 75, 84, 10),
		("6x6x10", 72, 84, 10),
		("5x6x10", 60, 84, 10),
		("4.5x6x10", 54, 84, 10),
		("3.5x6x8", 42, 84, 8),
		("3x6x6", 36, 84, 6),
	]

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

	frappe.db.commit()


def migrate_rebate_expense_account():
	income_account = frappe.db.get_single_value(
		"Pufm Manufacturing Settings", "rebate_income_account"
	)
	expense_account = frappe.db.get_single_value(
		"Pufm Manufacturing Settings", "rebate_expense_account"
	)
	if income_account and not expense_account:
		frappe.db.set_single_value(
			"Pufm Manufacturing Settings",
			"rebate_expense_account",
			income_account,
		)
		frappe.db.commit()


def ensure_customer_rebate_fields():
	custom_fields = {
		"Customer": [
			{
				"fieldname": "custom_rebate_configuration_section",
				"label": "Rebate Configuration",
				"fieldtype": "Section Break",
				"insert_after": "customer_group",
				"permlevel": 1,
			},
			{
				"fieldname": "custom_is_distributor",
				"label": "Is Distributor",
				"fieldtype": "Check",
				"insert_after": "custom_rebate_configuration_section",
				"permlevel": 1,
			},
			{
				"fieldname": "custom_rebate_tier",
				"label": "Rebate Tier",
				"fieldtype": "Select",
				"options": "None\n0-50m (10%)\n50-100m (11%)\nOverride",
				"default": "None",
				"insert_after": "custom_is_distributor",
				"permlevel": 1,
			},
			{
				"fieldname": "custom_rebate_override_percentage",
				"label": "Rebate Override Percentage",
				"fieldtype": "Float",
				"depends_on": "eval:doc.custom_rebate_tier=='Override'",
				"insert_after": "custom_rebate_tier",
				"permlevel": 1,
			},
			{
				"fieldname": "custom_freight_rebate_percentage",
				"label": "Freight Rebate Percentage",
				"fieldtype": "Float",
				"insert_after": "custom_rebate_override_percentage",
				"permlevel": 1,
			},
			{
				"fieldname": "custom_rebate_percentage",
				"label": "Rebate Percentage (Legacy)",
				"fieldtype": "Percent",
				"insert_after": "custom_freight_rebate_percentage",
				"permlevel": 1,
				"read_only": 1,
			},
		]
	}
	create_custom_fields(custom_fields, update=True)
	frappe.db.commit()


def ensure_foam_sheets():
	"""Seed continuous foam sheet roll Items (Meter UOM, batch-only, no serials)."""
	_ensure_item_group("Sub Assembly", parent="All Item Groups", is_group=0)
	_ensure_uom("Meter")

	# Rename legacy non-Roll names if they still exist
	renames = {
		"Foam Sheet - 0.5 Inch": "Foam Sheet Roll - 0.5 Inch",
		"Foam Sheet - 1.0 Inch": "Foam Sheet Roll - 1.0 Inch",
	}
	for old_code, new_code in renames.items():
		if frappe.db.exists("Item", old_code) and not frappe.db.exists("Item", new_code):
			frappe.rename_doc("Item", old_code, new_code, force=True, merge=False)

	sheets = [
		{
			"item_code": "Foam Sheet Roll - 0.5 Inch",
			"custom_height": 0.5,
			"custom_cbm_value": 0.02709,
		},
		{
			"item_code": "Foam Sheet Roll - 1.0 Inch",
			"custom_height": 1.0,
			"custom_cbm_value": 0.05419,
		},
	]

	for sheet in sheets:
		item_code = sheet["item_code"]
		if frappe.db.exists("Item", item_code):
			# Keep continuous rolls non-serialized even if created earlier
			item = frappe.get_doc("Item", item_code)
			changed = False
			if item.item_name != item_code:
				item.item_name = item_code
				changed = True
			if not item.has_batch_no:
				item.has_batch_no = 1
				changed = True
			if item.has_serial_no:
				item.has_serial_no = 0
				item.serial_no_series = ""
				changed = True
			if (item.stock_uom or "") != "Meter":
				# Don't force UOM change if stock already exists; only set when safe
				if not frappe.db.exists("Bin", {"item_code": item_code}):
					item.stock_uom = "Meter"
					changed = True
			if changed:
				item.save(ignore_permissions=True)
			continue

		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_code,
				"item_name": item_code,
				"item_group": "Sub Assembly",
				"stock_uom": "Meter",
				"is_stock_item": 1,
				"include_item_in_manufacturing": 1,
				"has_batch_no": 1,
				"create_new_batch": 1,
				"has_serial_no": 0,
				"serial_no_series": "",
				"custom_width": 84,
				"custom_length": 39.37,
				"custom_height": sheet["custom_height"],
				"custom_cbm_value": sheet["custom_cbm_value"],
			}
		).insert(ignore_permissions=True)

	frappe.db.commit()


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


def ensure_customer_rebate_field():
	ensure_customer_rebate_fields()
