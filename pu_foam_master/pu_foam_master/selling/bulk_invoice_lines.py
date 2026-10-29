# Copyright (c) 2026, PU Foam Master and contributors

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, flt


@frappe.whitelist()
def search_items_for_bulk_invoice(item_group, txt=None, limit=80):
	"""Items for Sales Invoice bulk picker (filter by Item Group + search text)."""
	if not item_group:
		frappe.throw(_("Item Group is required."))
	if not frappe.db.exists("Item Group", item_group):
		frappe.throw(_("Item Group {0} was not found.").format(item_group))

	limit = min(cint(limit) or 80, 200)
	txt = (txt or "").strip()

	conditions = [
		"item.disabled = 0",
		"item.item_group = %(item_group)s",
	]
	values = {"item_group": item_group, "limit": limit}

	if txt:
		conditions.append("(item.name LIKE %(txt)s OR item.item_name LIKE %(txt)s)")
		values["txt"] = "%{}%".format(txt)

	rows = frappe.db.sql(
		"""
		SELECT
			item.name AS item_code,
			item.item_name,
			item.item_group,
			item.stock_uom,
			item.brand,
			item.custom_finish_type,
			item.custom_length,
			item.custom_width,
			item.custom_height,
			item.description
		FROM `tabItem` item
		WHERE {where}
		ORDER BY item.name ASC
		LIMIT %(limit)s
		""".format(
			where=" AND ".join(conditions)
		),
		values,
		as_dict=True,
	)

	for row in rows:
		row["details"] = _format_item_details(row)

	return rows


def _format_item_details(row):
	parts = [row.get("item_group") or ""]
	if row.get("brand"):
		parts.append(str(row.brand))
	finish = (row.get("custom_finish_type") or "").strip()
	if finish:
		parts.append(finish)
	length, width, height = flt(row.get("custom_length")), flt(row.get("custom_width")), flt(
		row.get("custom_height")
	)
	if length and width and height:
		parts.append("{0}×{1}×{2} in".format(length, width, height))
	desc = (row.get("description") or "").strip()
	if desc and desc not in parts:
		parts.append(desc[:80])
	return ", ".join(p for p in parts if p)
