import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def ensure_item_custom_fields():
	item_fields = {
		"Item": [
			{
				"fieldname": "custom_width",
				"label": "Width (Inches)",
				"fieldtype": "Float",
				"insert_after": "stock_uom",
			},
			{
				"fieldname": "custom_height",
				"label": "Height (Inches)",
				"fieldtype": "Float",
				"insert_after": "custom_width",
			},
			{
				"fieldname": "custom_length",
				"label": "Length (Inches)",
				"fieldtype": "Float",
				"insert_after": "custom_height",
			},
			{
				"fieldname": "custom_cbm_value",
				"label": "CBM Value",
				"fieldtype": "Float",
				"read_only": 1,
				"insert_after": "custom_length",
			},
		]
	}
	create_custom_fields(item_fields, update=True)
	frappe.db.commit()


def ensure_sales_invoice_rebate_fields():
	si_fields = {
		"Sales Invoice": [
			{
				"fieldname": "custom_rebate_section",
				"label": "Rebate",
				"fieldtype": "Section Break",
				"insert_after": "customer",
			},
			{
				"fieldname": "custom_apply_instant_rebate",
				"label": "Apply Instant Rebate",
				"fieldtype": "Check",
				"insert_after": "custom_rebate_section",
			},
			{
				"fieldname": "custom_instant_rebate_percentage",
				"label": "Instant Rebate Percentage",
				"fieldtype": "Float",
				"depends_on": "eval:doc.custom_apply_instant_rebate",
				"insert_after": "custom_apply_instant_rebate",
			},
			{
				"fieldname": "custom_instant_rebate_amount",
				"label": "Instant Rebate Amount",
				"fieldtype": "Currency",
				"depends_on": "eval:doc.custom_apply_instant_rebate",
				"insert_after": "custom_instant_rebate_percentage",
				"read_only": 1,
			},
			{
				"fieldname": "custom_rebate_settlement",
				"label": "Rebate Settlement",
				"fieldtype": "Link",
				"options": "Rebate Settlement Tool",
				"insert_after": "custom_instant_rebate_amount",
				"read_only": 1,
				"no_copy": 1,
				"description": "Set when this invoice is included in a submitted period rebate settlement.",
			},
		]
	}
	create_custom_fields(si_fields, update=True)
	frappe.db.commit()
