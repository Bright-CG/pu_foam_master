# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

"""Item CBM helpers and mattress core ↔ batch validation."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from pu_foam_master.pufm_manufacturing.utils.settings import calculate_cbm

MATTRESS_FINISH_SUFFIXES = ("-PLAIN", "-SQ", "-FQ")


def recalculate_item_cbm(doc):
	"""Set custom_cbm_value from width × length × height when all three are present."""
	width = flt(getattr(doc, "custom_width", 0))
	height = flt(getattr(doc, "custom_height", 0))
	length = flt(getattr(doc, "custom_length", 0))
	if width <= 0 or height <= 0 or length <= 0:
		return
	doc.custom_cbm_value = flt(calculate_cbm(length, width, height, 1), 5)


def on_item_validate(doc, method=None):
	recalculate_item_cbm(doc)


def implied_core_item(mattress_item):
	"""Core SKU implied by Mattress Item Generator naming (-PLAIN/-SQ/-FQ → -CORE)."""
	if not mattress_item:
		return None
	code = str(mattress_item)
	upper = code.upper()
	for suffix in MATTRESS_FINISH_SUFFIXES:
		if upper.endswith(suffix):
			return code[: len(code) - len(suffix)] + "-CORE"
	if upper.startswith("MAT-"):
		return "CORE-" + code[4:]
	return None


def validate_core_batch_for_mattress(mattress_item, core_batch, row_label=None):
	"""Server check: core batch Item must match the core implied by the mattress SKU."""
	prefix = row_label or _("Row")
	if not mattress_item:
		return
	if not core_batch:
		frappe.throw(_("{0}: Core Batch is required.").format(prefix))

	expected_core = implied_core_item(mattress_item)
	if not expected_core:
		frappe.throw(
			_(
				"{0}: Cannot determine the core Item for mattress {1}. "
				"Use a standard finish SKU ending in -PLAIN, -SQ, or -FQ."
			).format(prefix, mattress_item)
		)

	batch_item = frappe.db.get_value("Batch", core_batch, "item")
	if not batch_item:
		frappe.throw(_("{0}: Core Batch {1} was not found.").format(prefix, core_batch))
	if batch_item != expected_core:
		frappe.throw(
			_(
				"{0}: Core Batch {1} belongs to {2}, but mattress {3} requires core {4}."
			).format(prefix, core_batch, batch_item, mattress_item, expected_core)
		)


def batch_belongs_to_conversion(batch_no, conversion_name):
	if not batch_no or not conversion_name:
		return False
	row = frappe.db.get_value(
		"Batch", batch_no, ["reference_name", "batch_id"], as_dict=True
	)
	if not row:
		return False
	if row.reference_name == conversion_name:
		return True
	batch_id = (row.batch_id or "").strip()
	return batch_id.startswith("{0}-".format(conversion_name))
