# Copyright (c) 2026, PU Foam Master and contributors
"""Build actual production cost breakdown rows from submitted Stock Entries."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, flt

PRECISION = 5
CURRENCY_PRECISION = 2
TOLERANCE = 0.05

# (DocType, field holding Stock Entry name; Mattress Production Entry also uses stock_entries)
_PRODUCTION_LINKS = (
	("Pufm Production Batch", "chemical_consumption_entry"),
	("Pufm Production Batch", "fg_receipt_entry"),
	("Mattress Core Conversion", "stock_entry"),
	("Quilting Record", "stock_entry"),
	("Mattress Production Entry", "stock_entry"),
	("Rebound Production Entry", "stock_entry"),
)


def get_scrap_item_code():
	return frappe.db.get_single_value("Pufm Manufacturing Settings", "scrap_item")


def resolve_production_document(stock_entry_name):
	"""Return (doctype, name) for a PUFM production voucher linked to this Stock Entry."""
	if not stock_entry_name:
		return None, None

	for doctype, fieldname in _PRODUCTION_LINKS:
		if not frappe.db.exists("DocType", doctype):
			continue
		name = frappe.db.get_value(doctype, {fieldname: stock_entry_name}, "name")
		if name:
			return doctype, name

	# Mattress Production Entry may list multiple SE names in stock_entries
	if frappe.db.exists("DocType", "Mattress Production Entry"):
		rows = frappe.db.sql(
			"""
			SELECT name
			FROM `tabMattress Production Entry`
			WHERE docstatus = 1
				AND (
					stock_entry = %(se)s
					OR stock_entries LIKE %(like)s
				)
			LIMIT 1
			""",
			{"se": stock_entry_name, "like": "%{}%".format(stock_entry_name)},
		)
		if rows:
			return "Mattress Production Entry", rows[0][0]

	return None, None


def _line_amount(row):
	qty = flt(row.get("qty"))
	rate = flt(row.get("basic_rate") or row.get("valuation_rate"))
	amount = flt(row.get("amount") or row.get("basic_amount"))
	if amount:
		return flt(amount, PRECISION)
	return flt(qty * rate, PRECISION)


def _fg_rows(entry, scrap_item):
	rows = []
	for row in entry.get("items") or []:
		if not row.t_warehouse or flt(row.qty) <= 0:
			continue
		if scrap_item and row.item_code == scrap_item:
			continue
		if entry.purpose == "Manufacture" and not cint(row.is_finished_item):
			continue
		rows.append(row)
	return rows


def _item_measure(item_code, qty, uom):
	"""Return (measure_label, measure_value) for MD-facing quantity context."""
	meta = frappe.db.get_value(
		"Item",
		item_code,
		["custom_cbm_value", "stock_uom", "item_group"],
		as_dict=True,
	) or {}
	stock_uom = (meta.get("stock_uom") or uom or "").strip()
	cbm_unit = flt(meta.get("custom_cbm_value"))
	if cbm_unit > 0 and stock_uom and stock_uom.lower() in ("nos", "no", "ea", "each", "pc", "pcs"):
		return _("CBM"), flt(cbm_unit * flt(qty), PRECISION)
	if stock_uom and stock_uom.lower() in ("meter", "m", "mtr"):
		return _("Meters"), flt(qty, PRECISION)
	if cbm_unit > 0:
		return _("CBM"), flt(cbm_unit * flt(qty), PRECISION)
	return _("Qty"), flt(qty, PRECISION)


def _allocation_share(fg_amount, total_fg_amount):
	"""Fraction of FG value on this Stock Entry — do not round (avoids large-pool drift)."""
	if not total_fg_amount:
		return 1.0
	return flt(fg_amount) / flt(total_fg_amount)


def _allocate_line_amount(pool_amount, share):
	return flt(flt(pool_amount) * share, CURRENCY_PRECISION)


def _reconcile_children_to_fg_amount(child_rows, fg_amount):
	"""Penny remainder on last child so components sum exactly to the FG line."""
	if not child_rows:
		return 0.0
	component_sum = flt(sum(flt(row.get("line_cost")) for row in child_rows), CURRENCY_PRECISION)
	delta = flt(fg_amount - component_sum, CURRENCY_PRECISION)
	if abs(delta) > 0 and child_rows:
		last = child_rows[-1]
		last["line_cost"] = flt(flt(last.get("line_cost")) + delta, CURRENCY_PRECISION)
		qty = flt(last.get("qty"))
		if qty:
			last["unit_cost"] = flt(last["line_cost"] / qty, PRECISION)
	return flt(sum(flt(row.get("line_cost")) for row in child_rows), CURRENCY_PRECISION)


def _cost_density_metrics(item_code, total_cost, measure_label, measure_value):
	cbm_factor = flt(
		frappe.db.get_single_value("Pufm Manufacturing Settings", "cbm_factor") or 61023.74
	)
	cost_per_cbm = 0.0
	cost_per_cubic_inch = 0.0
	if measure_label == _("CBM") and flt(measure_value) > 0:
		cost_per_cbm = flt(flt(total_cost) / flt(measure_value), PRECISION)
		if cbm_factor > 0:
			cost_per_cubic_inch = flt(cost_per_cbm / cbm_factor, PRECISION)
	return cost_per_cbm, cost_per_cubic_inch


def build_inquiry_rows(entry, filters=None, scrap_item=None):
	"""Return tree rows (indent 0 = finished good, indent 1 = components) for one Stock Entry."""
	filters = frappe._dict(filters or {})
	scrap_item = scrap_item or get_scrap_item_code()
	rows_out = []

	fg_rows = _fg_rows(entry, scrap_item)
	if not fg_rows:
		return rows_out

	source_rows = [r for r in entry.get("items") or [] if r.s_warehouse and flt(r.qty) > 0]
	scrap_rows = [
		r
		for r in entry.get("items") or []
		if r.t_warehouse and scrap_item and r.item_code == scrap_item and flt(r.qty) > 0
	]
	additional_rows = list(entry.get("additional_costs") or [])

	total_fg_amount = sum(_line_amount(r) for r in fg_rows)
	total_source = sum(_line_amount(r) for r in source_rows)
	total_additional = sum(flt(a.amount) for a in additional_rows)
	total_scrap = sum(_line_amount(r) for r in scrap_rows)
	pool = flt(total_source + total_additional, PRECISION)

	production_doctype, production_doc = resolve_production_document(entry.name)

	for fg in fg_rows:
		fg_amount = _line_amount(fg)
		if filters.get("item_code") and fg.item_code != filters.item_code:
			continue
		if filters.get("item_group"):
			grp = frappe.db.get_value("Item", fg.item_code, "item_group")
			if grp != filters.item_group:
				continue
		if filters.get("production_doctype") and production_doctype != filters.production_doctype:
			continue

		share = _allocation_share(fg_amount, total_fg_amount)
		measure_label, measure_value = _item_measure(fg.item_code, fg.qty, fg.uom)
		cost_per_cbm, cost_per_cubic_inch = _cost_density_metrics(
			fg.item_code, fg_amount, measure_label, measure_value
		)

		child_rows = []

		for src in source_rows:
			line = _allocate_line_amount(_line_amount(src), share)
			child_rows.append(
				_component_row(
					entry,
					production_doctype,
					production_doc,
					src.item_code,
					flt(flt(src.qty) * share, PRECISION),
					src.uom or src.stock_uom,
					line,
					_("Material"),
					indent=1,
				)
			)

		for scrap in scrap_rows:
			line = _allocate_line_amount(_line_amount(scrap), share)
			child_rows.append(
				_component_row(
					entry,
					production_doctype,
					production_doc,
					scrap.item_code,
					flt(flt(scrap.qty) * share, PRECISION),
					scrap.uom or scrap.stock_uom,
					line,
					_("Scrap by-product"),
					indent=1,
				)
			)

		for add in additional_rows:
			line = _allocate_line_amount(add.amount, share)
			label = (add.description or _("Overhead")).strip()
			child_rows.append(
				{
					"indent": 1,
					"posting_date": entry.posting_date,
					"stock_entry": entry.name,
					"production_doctype": production_doctype,
					"production_doc": production_doc,
					"row_type": _("Overhead"),
					"item_code": "",
					"item_name": label,
					"item_group": "",
					"qty": 0,
					"uom": "",
					"measure_label": "",
					"measure_value": 0,
					"unit_cost": 0,
					"line_cost": line,
					"cost_per_cbm": 0,
					"cost_per_cubic_inch": 0,
					"integrity_flag": "",
				}
			)

		component_sum = _reconcile_children_to_fg_amount(child_rows, fg_amount)
		integrity_ok = abs(component_sum - fg_amount) <= TOLERANCE
		integrity_flag = _("OK") if integrity_ok else _("Check")

		rows_out.append(
			{
				"indent": 0,
				"posting_date": entry.posting_date,
				"stock_entry": entry.name,
				"production_doctype": production_doctype,
				"production_doc": production_doc,
				"row_type": _("Finished product"),
				"item_code": fg.item_code,
				"item_name": frappe.db.get_value("Item", fg.item_code, "item_name") or fg.item_code,
				"item_group": frappe.db.get_value("Item", fg.item_code, "item_group"),
				"qty": flt(fg.qty),
				"uom": fg.uom or fg.stock_uom,
				"measure_label": measure_label,
				"measure_value": measure_value,
				"unit_cost": flt(fg_amount / flt(fg.qty), PRECISION) if flt(fg.qty) else 0,
				"line_cost": fg_amount,
				"cost_per_cbm": cost_per_cbm,
				"cost_per_cubic_inch": cost_per_cubic_inch,
				"integrity_flag": integrity_flag,
				"_pool_hint": pool,
				"_fg_total_hint": total_fg_amount,
			}
		)
		rows_out.extend(child_rows)

	return rows_out


def _component_row(
	entry, production_doctype, production_doc, item_code, qty, uom, line_cost, row_type, indent
):
	unit_cost = flt(line_cost / qty, PRECISION) if qty else 0
	measure_label, measure_value = _item_measure(item_code, qty, uom)
	return {
		"indent": indent,
		"posting_date": entry.posting_date,
		"stock_entry": entry.name,
		"production_doctype": production_doctype,
		"production_doc": production_doc,
		"row_type": row_type,
		"item_code": item_code,
		"item_name": frappe.db.get_value("Item", item_code, "item_name") or item_code,
		"item_group": frappe.db.get_value("Item", item_code, "item_group"),
		"qty": flt(qty, PRECISION),
		"uom": uom,
		"measure_label": measure_label,
		"measure_value": measure_value,
		"unit_cost": unit_cost,
		"line_cost": line_cost,
		"cost_per_cbm": 0,
		"cost_per_cubic_inch": 0,
		"integrity_flag": "",
	}


def fetch_stock_entry_names(filters):
	filters = frappe._dict(filters or {})
	conditions = [
		"se.docstatus = 1",
		"se.purpose IN ('Manufacture', 'Repack')",
	]
	values = {}

	if filters.get("company"):
		conditions.append("se.company = %(company)s")
		values["company"] = filters.company
	if filters.get("from_date"):
		conditions.append("se.posting_date >= %(from_date)s")
		values["from_date"] = filters.from_date
	if filters.get("to_date"):
		conditions.append("se.posting_date <= %(to_date)s")
		values["to_date"] = filters.to_date
	if filters.get("stock_entry"):
		conditions.append("se.name = %(stock_entry)s")
		values["stock_entry"] = filters.stock_entry

	if filters.get("item_code") or filters.get("item_group"):
		item_conds = ["sed.parenttype = 'Stock Entry'", "sed.t_warehouse IS NOT NULL", "sed.qty > 0"]
		if filters.get("item_code"):
			item_conds.append("sed.item_code = %(item_code)s")
			values["item_code"] = filters.item_code
		if filters.get("item_group"):
			item_conds.append("item.item_group = %(item_group)s")
			values["item_group"] = filters.item_group
		conditions.append(
			"""
			EXISTS (
				SELECT 1 FROM `tabStock Entry Detail` sed
				INNER JOIN `tabItem` item ON item.name = sed.item_code
				WHERE sed.parent = se.name
					AND {item_where}
			)
			""".format(
				item_where=" AND ".join(item_conds)
			)
		)

	where_sql = " AND ".join(conditions)
	return frappe.db.sql(
		f"""
		SELECT se.name
		FROM `tabStock Entry` se
		WHERE {where_sql}
		ORDER BY se.posting_date DESC, se.creation DESC
		LIMIT 500
		""",
		values,
		pluck=True,
	)


def get_production_cost_inquiry_data(filters=None):
	filters = frappe._dict(filters or {})
	scrap_item = get_scrap_item_code()
	names = fetch_stock_entry_names(filters)
	data = []
	for name in names:
		entry = frappe.get_doc("Stock Entry", name)
		rows = build_inquiry_rows(entry, filters=filters, scrap_item=scrap_item)
		for row in rows:
			row.pop("_pool_hint", None)
			row.pop("_fg_total_hint", None)
		data.extend(rows)
	return data
