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
			"label": _("Date"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
			"width": 110,
		},
		{
			"label": _("Process Type"),
			"fieldname": "process_type",
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"label": _("Reference Doc"),
			"fieldname": "reference_doc",
			"fieldtype": "Dynamic Link",
			"options": "reference_doctype",
			"width": 160,
		},
		{
			"label": _("Reference Type"),
			"fieldname": "reference_doctype",
			"fieldtype": "Data",
			"hidden": 1,
			"width": 0,
		},
		{
			"label": _("Density Config / Source Block"),
			"fieldname": "density_config",
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"label": _("Expected CBM"),
			"fieldname": "expected_cbm",
			"fieldtype": "Float",
			"precision": 5,
			"width": 120,
		},
		{
			"label": _("Actual CBM"),
			"fieldname": "actual_cbm",
			"fieldtype": "Float",
			"precision": 5,
			"width": 120,
		},
		{
			"label": _("Variance %"),
			"fieldname": "variance_percentage",
			"fieldtype": "Float",
			"precision": 5,
			"width": 110,
		},
		{
			"label": _("Density Run"),
			"fieldname": "density_run",
			"fieldtype": "Link",
			"options": "Pufm Density Run",
			"width": 150,
		},
	]


def get_data(filters):
	raw_threshold = filters.get("variance_threshold")
	# Explicit 0 / "0" must be kept; only None / blank fall back.
	if raw_threshold in [None, ""]:
		threshold = 0.0
	else:
		threshold = flt(raw_threshold)

	combined = []
	combined.extend(_get_density_run_rows(filters))
	combined.extend(_get_block_conversion_rows(filters))

	data = []
	for row in combined:
		if abs(flt(row.get("variance_percentage"))) >= threshold:
			data.append(row)

	data.sort(key=lambda r: (r.get("posting_date") or "", r.get("reference_doc") or ""), reverse=True)
	return data


def _get_density_run_rows(filters):
	conditions = ["1=1"]
	values = {}

	if filters.get("from_date"):
		conditions.append("pb.posting_date >= %(from_date)s")
		values["from_date"] = filters.from_date
	if filters.get("to_date"):
		conditions.append("pb.posting_date <= %(to_date)s")
		values["to_date"] = filters.to_date

	where_sql = " AND ".join(conditions)
	rows = frappe.db.sql(
		f"""
		SELECT
			dr.name AS density_run,
			pb.posting_date AS posting_date,
			dr.parent_batch AS reference_doc,
			dr.density_config AS density_config,
			dr.expected_cbm AS expected_cbm,
			dr.actual_cbm AS actual_cbm,
			COALESCE(dr.variance_percentage, dr.variance_percent, 0) AS variance_percentage
		FROM `tabPufm Density Run` dr
		INNER JOIN `tabPufm Production Batch` pb
			ON pb.name = dr.parent_batch
		WHERE {where_sql}
		""",
		values,
		as_dict=True,
	)

	out = []
	for row in rows:
		variance = flt(row.variance_percentage)
		if not variance and flt(row.expected_cbm):
			variance = flt(
				((flt(row.actual_cbm) - flt(row.expected_cbm)) / flt(row.expected_cbm)) * 100,
				5,
			)
		out.append(
			{
				"posting_date": row.posting_date,
				"process_type": "Density Run",
				"reference_doctype": "Pufm Production Batch",
				"reference_doc": row.reference_doc,
				"density_config": row.density_config,
				"expected_cbm": flt(row.expected_cbm, 5),
				"actual_cbm": flt(row.actual_cbm, 5),
				"variance_percentage": flt(variance, 5),
				"density_run": row.density_run,
			}
		)
	return out


def _get_block_conversion_rows(filters):
	conditions = ["docstatus = 1"]
	values = {}

	if filters.get("from_date"):
		conditions.append("posting_date >= %(from_date)s")
		values["from_date"] = filters.from_date
	if filters.get("to_date"):
		conditions.append("posting_date <= %(to_date)s")
		values["to_date"] = filters.to_date

	where_sql = " AND ".join(conditions)
	has_variance_col = frappe.db.has_column("Foam Block Conversion", "variance_percentage")
	variance_select = (
		"COALESCE(variance_percentage, 0) AS variance_percentage"
		if has_variance_col
		else "0 AS variance_percentage"
	)

	rows = frappe.db.sql(
		f"""
		SELECT
			name,
			posting_date,
			total_input_cbm,
			total_output_cbm,
			{variance_select}
		FROM `tabFoam Block Conversion`
		WHERE {where_sql}
		""",
		values,
		as_dict=True,
	)

	out = []
	for row in rows:
		first_input = frappe.db.get_value(
			"Block Conversion Input",
			{"parent": row.name, "parenttype": "Foam Block Conversion", "idx": 1},
			"item_code",
		)
		if not first_input:
			first_input = frappe.db.get_value(
				"Block Conversion Input",
				{"parent": row.name, "parenttype": "Foam Block Conversion"},
				"item_code",
				order_by="idx asc",
			)

		expected = flt(row.total_input_cbm)
		actual = flt(row.total_output_cbm)
		variance = flt(row.variance_percentage)
		if expected:
			# Prefer live math if stored value is blank/zero but volumes differ
			if not variance and actual != expected:
				variance = flt(((actual - expected) / expected) * 100, 2)
			elif not has_variance_col:
				variance = flt(((actual - expected) / expected) * 100, 2)

		out.append(
			{
				"posting_date": row.posting_date,
				"process_type": "Block Conversion (Slicing)",
				"reference_doctype": "Foam Block Conversion",
				"reference_doc": row.name,
				"density_config": first_input,
				"expected_cbm": flt(expected, 5),
				"actual_cbm": flt(actual, 5),
				"variance_percentage": flt(variance, 5),
				"density_run": None,
			}
		)
	return out
