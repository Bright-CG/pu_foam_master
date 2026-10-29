# Copyright (c) 2026, PU Foam Master and contributors

from __future__ import unicode_literals

import frappe
from frappe import _

from pu_foam_master.pufm_manufacturing.utils.production_cost_inquiry import (
	get_production_cost_inquiry_data,
)


def execute(filters=None):
	columns = get_columns()
	data = get_production_cost_inquiry_data(filters)
	return columns, data


def get_columns():
	return [
		{"fieldname": "indent", "fieldtype": "Int", "hidden": 1, "width": 0},
		{
			"label": _("Posting Date"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
			"width": 100,
		},
		{
			"label": _("Stock Entry"),
			"fieldname": "stock_entry",
			"fieldtype": "Link",
			"options": "Stock Entry",
			"width": 150,
		},
		{
			"label": _("Production Doc"),
			"fieldname": "production_doc",
			"fieldtype": "Dynamic Link",
			"options": "production_doctype",
			"width": 160,
		},
		{
			"fieldname": "production_doctype",
			"fieldtype": "Data",
			"hidden": 1,
			"width": 0,
		},
		{
			"label": _("Row Type"),
			"fieldname": "row_type",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Item"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 160,
		},
		{
			"label": _("Item Name"),
			"fieldname": "item_name",
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"label": _("Item Group"),
			"fieldname": "item_group",
			"fieldtype": "Link",
			"options": "Item Group",
			"width": 130,
		},
		{
			"label": _("Qty"),
			"fieldname": "qty",
			"fieldtype": "Float",
			"width": 80,
		},
		{"label": _("UOM"), "fieldname": "uom", "fieldtype": "Data", "width": 70},
		{
			"label": _("Measure"),
			"fieldname": "measure_label",
			"fieldtype": "Data",
			"width": 90,
		},
		{
			"label": _("Measure Qty"),
			"fieldname": "measure_value",
			"fieldtype": "Float",
			"precision": 5,
			"width": 100,
		},
		{
			"label": _("Unit Cost"),
			"fieldname": "unit_cost",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Line Cost"),
			"fieldname": "line_cost",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"label": _("Cost / CBM"),
			"fieldname": "cost_per_cbm",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Cost / Cu In"),
			"fieldname": "cost_per_cubic_inch",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Integrity"),
			"fieldname": "integrity_flag",
			"fieldtype": "Data",
			"width": 70,
		},
	]
