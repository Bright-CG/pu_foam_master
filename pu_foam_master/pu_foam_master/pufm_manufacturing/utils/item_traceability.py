# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

"""Finished-good Item traceability defaults.

Foam blocks, mattress cores, and finished mattresses are Batch-only.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint

# ERPNext Item naming series for auto Batch when not set by the voucher
DEFAULT_BATCH_NUMBER_SERIES = "BATCH-.YYYY.-.#####"

FINISHED_MATTRESS_FINISH_TYPES = frozenset(
	{"Plain", "Side Quilted", "Fully Quilted"}
)
FINISHED_MATTRESS_SUFFIXES = ("-PLAIN", "-SQ", "-FQ")


def apply_finished_good_traceability(item, brand=None):
	"""Force Batch-only tracking on finished mattress Item docs (alias of core/block)."""
	return apply_core_traceability(item, brand=brand)


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


def apply_core_traceability(item, brand=None):
	"""Force Batch-only tracking on mattress core Items (no serials)."""
	return apply_block_traceability(item, brand=brand)


def finished_good_traceability_defaults(brand=None):
	"""Batch-only defaults for finished mattress Items (same as cores)."""
	return core_traceability_defaults(brand=brand)


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


def core_traceability_defaults(brand=None):
	"""Batch-only defaults for generated mattress core Items."""
	return block_traceability_defaults(brand=brand)


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


def is_foam_core_item(item_code):
	"""True for generated mattress core SKUs (…-CORE or legacy CORE-…)."""
	if not item_code:
		return False
	name = str(item_code)
	if name.endswith(" Block"):
		return False
	upper = name.upper()
	return upper.endswith("-CORE") or upper.startswith("CORE-")


def ensure_item_finished_good_traceability(item_code, brand=None, throw_if_locked=True):
	"""Ensure finished mattress Item is Batch-only."""
	return ensure_finished_mattress_item_traceability(
		item_code, brand=brand, throw_if_locked=throw_if_locked
	)


def is_finished_mattress_item(item_code):
	"""True for sellable mattress SKUs (Plain / SQ / FQ), not cores or blocks."""
	if not item_code:
		return False
	if is_foam_block_item(item_code) or is_foam_core_item(item_code):
		return False
	name = str(item_code)
	upper = name.upper()
	if any(upper.endswith(suffix) for suffix in FINISHED_MATTRESS_SUFFIXES):
		return True
	finish = frappe.db.get_value("Item", item_code, "custom_finish_type")
	return (finish or "").strip() in FINISHED_MATTRESS_FINISH_TYPES


def ensure_finished_mattress_item_traceability(item_code, brand=None, throw_if_locked=True):
	"""Ensure finished mattress Item is Batch-only (has_serial_no = 0)."""
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

	apply_core_traceability(item, brand=brand)
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


def ensure_core_item_traceability(item_code, brand=None, throw_if_locked=True):
	"""Ensure mattress core Item is Batch-only (has_serial_no = 0)."""
	return ensure_block_item_traceability(
		item_code, brand=brand, throw_if_locked=throw_if_locked
	)


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


def list_foam_core_item_codes():
	"""Active Item names that look like generated mattress cores."""
	by_suffix = frappe.get_all(
		"Item",
		filters={"disabled": 0, "name": ["like", "%-CORE"]},
		pluck="name",
	)
	legacy = frappe.get_all(
		"Item",
		filters={"disabled": 0, "name": ["like", "CORE-%"]},
		pluck="name",
	)
	by_group = []
	if frappe.db.exists("Item Group", "Foam Cores"):
		by_group = frappe.get_all(
			"Item",
			filters={"disabled": 0, "item_group": "Foam Cores"},
			pluck="name",
		)
	return sorted({n for n in (by_suffix + legacy + by_group) if is_foam_core_item(n)})


def list_finished_mattress_item_codes():
	"""Active finished mattress Items (Plain / SQ / FQ), excluding cores and blocks."""
	by_finish = frappe.get_all(
		"Item",
		filters={
			"disabled": 0,
			"custom_finish_type": ["in", list(FINISHED_MATTRESS_FINISH_TYPES)],
		},
		pluck="name",
	)
	by_name = []
	for suffix in FINISHED_MATTRESS_SUFFIXES:
		by_name.extend(
			frappe.get_all(
				"Item",
				filters={"disabled": 0, "name": ["like", f"%{suffix}"]},
				pluck="name",
			)
		)
	return sorted(
		{n for n in (by_finish + by_name) if is_finished_mattress_item(n)}
	)

