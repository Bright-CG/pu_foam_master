# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{
			"label": _("Item Code"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 160,
		},
		{
			"label": _("Item Name"),
			"fieldname": "item_name",
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"label": _("Item Group"),
			"fieldname": "item_group",
			"fieldtype": "Link",
			"options": "Item Group",
			"width": 140,
		},
		{
			"label": _("Actual Qty"),
			"fieldname": "actual_qty",
			"fieldtype": "Float",
			"width": 110,
		},
		{
			"label": _("Reorder Level"),
			"fieldname": "reorder_level",
			"fieldtype": "Float",
			"width": 120,
		},
		{
			"label": _("Shortfall"),
			"fieldname": "shortfall",
			"fieldtype": "Float",
			"width": 110,
		},
		{
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "HTML",
			"width": 140,
		},
	]


def get_data(filters):
	conditions = ["item.disabled = 0", "item.is_stock_item = 1"]
	values = {}

	if filters.get("item_group"):
		conditions.append("item.item_group = %(item_group)s")
		values["item_group"] = filters.item_group
	if filters.get("item_code"):
		conditions.append("item.name = %(item_code)s")
		values["item_code"] = filters.item_code

	where_sql = " AND ".join(conditions)

	rows = frappe.db.sql(
		f"""
		SELECT
			item.name AS item_code,
			item.item_name,
			item.item_group,
			COALESCE(bin_totals.actual_qty, 0) AS actual_qty,
			COALESCE(reorder_totals.reorder_level, 0) AS reorder_level
		FROM `tabItem` item
		LEFT JOIN (
			SELECT item_code, SUM(actual_qty) AS actual_qty
			FROM `tabBin`
			GROUP BY item_code
		) bin_totals ON bin_totals.item_code = item.name
		LEFT JOIN (
			SELECT parent AS item_code, MAX(warehouse_reorder_level) AS reorder_level
			FROM `tabItem Reorder`
			GROUP BY parent
		) reorder_totals ON reorder_totals.item_code = item.name
		WHERE {where_sql}
		ORDER BY item.item_group ASC, item.name ASC
		""",
		values,
		as_dict=True,
	)

	data = []
	for row in rows:
		actual = flt(row.actual_qty)
		reorder = flt(row.reorder_level)
		shortfall = max(reorder - actual, 0) if reorder > 0 and actual < reorder else 0
		data.append(
			{
				"item_code": row.item_code,
				"item_name": row.item_name,
				"item_group": row.item_group,
				"actual_qty": actual,
				"reorder_level": reorder,
				"shortfall": shortfall,
				"status": _status_html(actual, reorder),
			}
		)
	return data


def _status_html(actual_qty, reorder_level):
	actual = flt(actual_qty)
	reorder = flt(reorder_level)

	# No reorder configured: treat zero/negative as critical, else healthy
	if reorder <= 0:
		if actual <= 0:
			return '<span style="color:red; font-weight:bold;">Critical/Reorder</span>'
		return '<span style="color:green; font-weight:bold;">Healthy</span>'

	if actual <= 0 or actual < reorder:
		return '<span style="color:red; font-weight:bold;">Critical/Reorder</span>'

	# Within 20% above reorder level → warning band
	warning_ceiling = reorder * 1.20
	if actual < warning_ceiling:
		return '<span style="color:orange; font-weight:bold;">Warning</span>'

	return '<span style="color:green; font-weight:bold;">Healthy</span>'
