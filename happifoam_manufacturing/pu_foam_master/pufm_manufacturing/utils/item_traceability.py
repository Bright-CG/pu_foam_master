# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

"""Finished-good Item traceability defaults.

Foam blocks are Batch-only (qty > 1 on conversion rows).
Mattresses / cores keep Batch + Serial.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint

# ERPNext Item naming series for auto Batch / Serial when not set by the voucher
DEFAULT_BATCH_NUMBER_SERIES = "BATCH-.YYYY.-.#####"
DEFAULT_SERIAL_NO_SERIES = "S-.YYYY.-.#####"


def apply_finished_good_traceability(item, brand=None):
	"""Force Batch + Serial tracking on mattress / core Item docs.

	Mutates ``item`` in place. Caller is responsible for insert/save.
	Do not use this for foam blocks — use ``apply_block_traceability``.
	"""
	item.has_batch_no = 1
	item.create_new_batch = 1
	item.has_serial_no = 1

	if not (item.get("batch_number_series") or "").strip():
		item.batch_number_series = DEFAULT_BATCH_NUMBER_SERIES
	if not (item.get("serial_no_series") or "").strip():
		item.serial_no_series = DEFAULT_SERIAL_NO_SERIES

	if brand:
		item.brand = brand

	return item


def apply_block_traceability(item, brand=None):
	"""Force Batch-only tracking on foam block Items (no serials)."""
	item.has_batch_no = 1
	item.create_new_batch = 1
	item.has_serial_no = 0

	if not (item.get("batch_number_series") or "").strip():
		item.batch_number_series = DEFAULT_BATCH_NUMBER_SERIES

	if brand:
		item.brand = brand

	return item


def finished_good_traceability_defaults(brand=None):
	"""Dict suitable for ``frappe.get_doc({...})`` / ``doc.update(...)``."""
	data = {
		"has_batch_no": 1,
		"create_new_batch": 1,
		"has_serial_no": 1,
		"batch_number_series": DEFAULT_BATCH_NUMBER_SERIES,
		"serial_no_series": DEFAULT_SERIAL_NO_SERIES,
	}
	if brand:
		data["brand"] = brand
	return data


def block_traceability_defaults(brand=None):
	"""Batch-only defaults for generated foam block Items."""
	data = {
		"has_batch_no": 1,
		"create_new_batch": 1,
		"has_serial_no": 0,
		"batch_number_series": DEFAULT_BATCH_NUMBER_SERIES,
	}
	if brand:
		data["brand"] = brand
	return data


def item_has_stock_ledger(item_code):
	"""True when Item has non-cancelled SLE rows (locks Has Batch/Serial No)."""
	if not item_code:
		return False
	return bool(
		frappe.db.exists(
			"Stock Ledger Entry",
			{"item_code": item_code, "is_cancelled": 0},
		)
	)


def is_foam_block_item(item_code):
	"""True for generated foam block SKUs (name ends with ' Block')."""
	if not item_code:
		return False
	name = str(item_code)
	if "BASE-FOAM-M3" in name:
		return False
	return name.endswith(" Block") or (" by " in name and name.endswith("Block"))


def ensure_item_finished_good_traceability(item_code, brand=None, throw_if_locked=True):
	"""Load Item, apply FG batch/serial flags, save. Returns the Item doc."""
	if not item_code or not frappe.db.exists("Item", item_code):
		frappe.throw(_("Item {0} does not exist.").format(item_code))

	item = frappe.get_doc("Item", item_code)
	needs = (
		not cint(item.has_batch_no)
		or not cint(item.has_serial_no)
		or not cint(item.create_new_batch)
		or not (item.get("batch_number_series") or "").strip()
		or not (item.get("serial_no_series") or "").strip()
		or (brand and item.brand != brand)
	)
	if not needs:
		return item

	if item_has_stock_ledger(item_code) and (
		not cint(item.has_batch_no) or not cint(item.has_serial_no) or not cint(item.create_new_batch)
	):
		if throw_if_locked:
			frappe.throw(
				_(
					"Item {0} already has stock transactions, so Has Batch No / Has Serial No "
					"cannot be changed. Cancel the linked Stock Entries first "
					"(run pu_foam_master.scripts.unlock_block_item_traceability.unlock_block_items)."
				).format(item_code)
			)
		return item

	apply_finished_good_traceability(item, brand=brand)
	item.save(ignore_permissions=True)
	return item


def ensure_block_item_traceability(item_code, brand=None, throw_if_locked=True):
	"""Ensure foam block Item is Batch-only (has_serial_no = 0)."""
	if not item_code or not frappe.db.exists("Item", item_code):
		frappe.throw(_("Item {0} does not exist.").format(item_code))

	item = frappe.get_doc("Item", item_code)
	needs = (
		not cint(item.has_batch_no)
		or cint(item.has_serial_no)
		or not cint(item.create_new_batch)
		or not (item.get("batch_number_series") or "").strip()
		or (brand and item.brand != brand)
	)
	if not needs:
		return item

	if item_has_stock_ledger(item_code):
		# Test / cutover: bypass Item.validate so operators can slice qty > 1.
		values = {
			"has_batch_no": 1,
			"create_new_batch": 1,
			"has_serial_no": 0,
		}
		if not (item.get("batch_number_series") or "").strip():
			values["batch_number_series"] = DEFAULT_BATCH_NUMBER_SERIES
		if brand:
			values["brand"] = brand
		frappe.db.set_value("Item", item_code, values, update_modified=False)
		return frappe.get_doc("Item", item_code)

	apply_block_traceability(item, brand=brand)
	item.save(ignore_permissions=True)
	return item


def list_foam_block_item_codes():
	"""Active Item names that look like generated foam blocks."""
	names = frappe.get_all(
		"Item",
		filters={"disabled": 0, "name": ["like", "% Block"]},
		pluck="name",
	)
	legacy = frappe.get_all(
		"Item",
		filters={"disabled": 0, "name": ["like", "% by % Block"]},
		pluck="name",
	)
	return sorted({n for n in (names + legacy) if is_foam_block_item(n)})

