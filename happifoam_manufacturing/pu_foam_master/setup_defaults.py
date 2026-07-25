import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def ensure_default_item_groups():
	"""Manual helper only — not wired into install/migrate hooks."""
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
	"""Manual helper only — prefer pu_foam_master.utils.demo_data.seed_standard_mattress_sizes."""
	from pu_foam_master.utils.demo_data import seed_standard_mattress_sizes

	seed_standard_mattress_sizes()


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


def ensure_customer_rebate_field():
	ensure_customer_rebate_fields()
