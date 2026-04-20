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
