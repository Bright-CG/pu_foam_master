# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from pu_foam_master.pufm_manufacturing.utils.settings import get_cbm_factor


class PufmRebondItemGenerator(Document):
	pass


@frappe.whitelist()
def generate_rebond_items(rebond_density=None, block_sizes=None):
	"""Create Rebound block Items from comma-separated LxWxH sizes."""
	doc = frappe.get_single("Pufm Rebond Item Generator")
	density = (rebond_density or doc.rebond_density or "").strip()
	sizes_raw = (block_sizes or doc.block_sizes or "").strip()

	if not density:
		frappe.throw(_("Rebond Density is required."))
	if not frappe.db.exists("Item", density):
		frappe.throw(_("Item {0} does not exist.").format(density))
	if not sizes_raw:
		frappe.throw(_("Enter at least one block size (e.g. 75x72x10)."))

	density_name = frappe.db.get_value("Item", density, "item_name") or density
	item_group = frappe.db.get_value("Item", density, "item_group") or "Products"
	cbm_factor = get_cbm_factor() or 61023.74

	created = []
	updated = []
	invalid = []

	for token in [part.strip() for part in sizes_raw.split(",") if part.strip()]:
		dims = _parse_size_token(token)
		if not dims:
			invalid.append(token)
			continue

		length, width, height = dims
		size_label = _format_size(length, width, height)
		item_code = f"{density_name}-{size_label}"
		unit_cbm = flt((length * width * height) / cbm_factor, 5)

		if frappe.db.exists("Item", item_code):
			item = frappe.get_doc("Item", item_code)
			item.custom_length = length
			item.custom_width = width
			item.custom_height = height
			item.custom_cbm_value = unit_cbm
			_apply_traceability(item)
			item.save(ignore_permissions=True)
			updated.append(item_code)
			continue

		from pu_foam_master.pufm_manufacturing.utils.item_traceability import (
			finished_good_traceability_defaults,
		)

		item = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_code,
				"item_name": item_code,
				"item_group": item_group,
				"stock_uom": "Nos",
				"is_stock_item": 1,
				"include_item_in_manufacturing": 1,
				"custom_length": length,
				"custom_width": width,
				"custom_height": height,
				"custom_cbm_value": unit_cbm,
				**finished_good_traceability_defaults(),
			}
		)
		item.insert(ignore_permissions=True)
		created.append(item_code)

	# Persist latest inputs on the Single
	doc.rebond_density = density
	doc.block_sizes = sizes_raw
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	parts = []
	if created:
		parts.append(_("Created {0}: {1}").format(len(created), ", ".join(created)))
	if updated:
		parts.append(_("Updated {0}: {1}").format(len(updated), ", ".join(updated)))
	if invalid:
		parts.append(_("Invalid sizes ignored: {0}").format(", ".join(invalid)))
	if not parts:
		parts.append(_("No items were created or updated."))

	return {
		"message": " | ".join(parts),
		"created": created,
		"updated": updated,
		"invalid": invalid,
	}


def _parse_size_token(token):
	parts = [p.strip() for p in token.lower().replace("*", "x").split("x") if p.strip()]
	if len(parts) != 3:
		return None
	try:
		length = flt(parts[0])
		width = flt(parts[1])
		height = flt(parts[2])
	except (TypeError, ValueError):
		return None
	if length <= 0 or width <= 0 or height <= 0:
		return None
	return length, width, height


def _format_size(length, width, height):
	def _fmt(value):
		number = flt(value)
		if float(number).is_integer():
			return str(int(number))
		return f"{number:g}"

	return f"{_fmt(length)}x{_fmt(width)}x{_fmt(height)}"


def _apply_traceability(item):
	from pu_foam_master.pufm_manufacturing.utils.item_traceability import (
		apply_finished_good_traceability,
	)

	apply_finished_good_traceability(item)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def rebond_density_query(doctype, txt, searchfield, start, page_len, filters):
	"""Prefer Items whose name/group suggests Rebound/Rebond density masters."""
	return frappe.db.sql(
		"""
		SELECT name, item_name, item_group
		FROM `tabItem`
		WHERE disabled = 0
			AND (
				name LIKE %(txt)s
				OR item_name LIKE %(txt)s
			)
			AND (
				name LIKE '%%Rebound%%'
				OR name LIKE '%%Rebond%%'
				OR item_name LIKE '%%Rebound%%'
				OR item_name LIKE '%%Rebond%%'
				OR item_group LIKE '%%Rebound%%'
				OR item_group LIKE '%%Rebond%%'
			)
		ORDER BY
			CASE WHEN name LIKE %(exact)s THEN 0 ELSE 1 END,
			name
		LIMIT %(start)s, %(page_len)s
		""",
		{
			"txt": f"%{txt}%",
			"exact": txt,
			"start": start,
			"page_len": page_len,
		},
	)
