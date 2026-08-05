# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

"""One-off: unlock foam block Items so Batch + Serial can be enabled.

Cancels the production-doc → Stock Entry chain that locks block Items missing
Has Batch No / Has Serial No, then enables those flags.

Order: cancel parent production docs first (they own the SE links), then any
leftover Stock Entries. Negative-stock / batch validators are relaxed for this
test-data cleanup. Vouchers stay cancelled for a clean E2E slate.

Usage:
  bench --site <site> execute \\
    pu_foam_master.scripts.unlock_block_item_traceability.unlock_block_items
"""

from __future__ import annotations

import frappe
from frappe.utils import cint

from pu_foam_master.pufm_manufacturing.utils.item_traceability import (
	apply_finished_good_traceability,
	item_has_stock_ledger,
)

# Parent DocTypes that store a Link to Stock Entry (cancel parent before SE)
SE_PARENT_LINKS = (
	("Mattress Production Entry", "stock_entry"),
	("Quilting Record", "stock_entry"),
	("Mattress Core Conversion", "stock_entry"),
	("Rebound Production Entry", "stock_entry"),
	("Pufm Production Batch", "chemical_consumption_entry"),
	("Pufm Production Batch", "fg_receipt_entry"),
	("Pufm Production Batch", "scrap_stock_entry"),
)


def unlock_block_items():
	"""Cancel locking vouchers and enable Batch/Serial on foam block Items."""
	broken_items = _find_broken_block_items()
	if not broken_items:
		msg = "No foam block Items missing Batch/Serial flags."
		print(msg)
		return {
			"cancelled_parents": [],
			"cancelled_stock_entries": [],
			"updated_items": [],
			"message": msg,
		}

	print(
		f"Found {len(broken_items)} block Item(s) missing Batch/Serial: "
		f"{', '.join(broken_items)}"
	)

	conversions = _find_submitted_conversions(broken_items)
	conversion_outputs = _conversion_output_items(conversions)
	related_items = sorted(set(broken_items) | set(conversion_outputs))
	stock_entries = _find_submitted_stock_entries(related_items)

	for name in conversions:
		se = frappe.db.get_value("Mattress Core Conversion", name, "stock_entry")
		if se and frappe.db.get_value("Stock Entry", se, "docstatus") == 1 and se not in stock_entries:
			stock_entries.append(se)

	print(f"Related submitted Stock Entries: {', '.join(stock_entries) or '(none)'}")

	cancelled_parents = []
	cancelled_ses = []

	prev_neg = frappe.db.get_single_value("Stock Settings", "allow_negative_stock")
	frappe.db.set_single_value("Stock Settings", "allow_negative_stock", 1)
	frappe.flags.allow_negative_stock = True
	restore_batch_validator = _patch_batch_negative_validator()

	try:
		# 1) Cancel every parent that links to these SEs (newest parents first)
		parents = _find_parents_for_stock_entries(stock_entries)
		for doctype, name in parents:
			doc = frappe.get_doc(doctype, name)
			if cint(doc.docstatus) != 1:
				continue
			print(f"  Cancelling {doctype} {name}...")
			doc.cancel()
			cancelled_parents.append(f"{doctype}:{name}")
			frappe.db.commit()

		# 2) Cancel any leftover submitted SEs (newest first)
		leftover = [
			n
			for n in _sort_stock_entries_newest_first(stock_entries)
			if frappe.db.get_value("Stock Entry", n, "docstatus") == 1
		]
		for se_name in leftover:
			print(f"  Cancelling leftover Stock Entry {se_name}...")
			frappe.get_doc("Stock Entry", se_name).cancel()
			cancelled_ses.append(se_name)
			frappe.db.commit()
	finally:
		restore_batch_validator()
		frappe.flags.allow_negative_stock = False
		frappe.db.set_single_value("Stock Settings", "allow_negative_stock", cint(prev_neg))

	# Collect SEs cancelled via parents
	for se_name in stock_entries:
		if frappe.db.get_value("Stock Entry", se_name, "docstatus") == 2:
			cancelled_ses.append(se_name)

	updated_items = []
	still_locked = []
	for item_code in broken_items:
		if item_has_stock_ledger(item_code):
			still_locked.append(item_code)
			print(f"  SKIP {item_code}: still has active SLE after cancel.")
			continue
		item = frappe.get_doc("Item", item_code)
		apply_finished_good_traceability(item)
		item.save(ignore_permissions=True)
		updated_items.append(item_code)
		print(
			f"  Updated Item {item_code}: has_batch_no=1, has_serial_no=1, create_new_batch=1"
		)

	frappe.db.commit()

	result = {
		"broken_items_found": broken_items,
		"cancelled_parents": cancelled_parents,
		"cancelled_stock_entries": sorted(set(cancelled_ses)),
		"updated_items": updated_items,
		"still_locked": still_locked,
	}
	print("Unlock complete:")
	for key, value in result.items():
		print(f"  {key}: {value}")
	return result


def _patch_batch_negative_validator():
	try:
		from erpnext.stock.doctype.serial_and_batch_bundle.serial_and_batch_bundle import (
			SerialandBatchBundle,
		)
	except Exception:
		return lambda: None

	original = SerialandBatchBundle.validate_negative_batch

	def _noop(self, *args, **kwargs):
		return None

	SerialandBatchBundle.validate_negative_batch = _noop
	return lambda: setattr(SerialandBatchBundle, "validate_negative_batch", original)


def _find_broken_block_items():
	broken_items = frappe.get_all(
		"Item",
		filters={"disabled": 0, "name": ["like", "% Block"]},
		or_filters={"has_batch_no": 0, "has_serial_no": 0},
		pluck="name",
	)
	legacy = frappe.get_all(
		"Item",
		filters={"disabled": 0, "name": ["like", "% by % Block"]},
		or_filters={"has_batch_no": 0, "has_serial_no": 0},
		pluck="name",
	)
	broken_items = sorted(set(broken_items) | set(legacy))
	return [c for c in broken_items if "BASE-FOAM-M3" not in c]


def _find_submitted_stock_entries(item_codes):
	if not item_codes:
		return []
	rows = frappe.db.sql(
		"""
		SELECT DISTINCT sed.parent
		FROM `tabStock Entry Detail` sed
		INNER JOIN `tabStock Entry` se ON se.name = sed.parent
		WHERE sed.item_code IN %(items)s
			AND se.docstatus = 1
		""",
		{"items": tuple(item_codes)},
	)
	sle_vouchers = frappe.db.sql(
		"""
		SELECT DISTINCT voucher_no
		FROM `tabStock Ledger Entry`
		WHERE item_code IN %(items)s
			AND voucher_type = 'Stock Entry'
			AND is_cancelled = 0
		""",
		{"items": tuple(item_codes)},
	)
	names = {r[0] for r in (rows or []) if r and r[0]}
	names |= {r[0] for r in (sle_vouchers or []) if r and r[0]}
	return [n for n in names if frappe.db.get_value("Stock Entry", n, "docstatus") == 1]


def _sort_stock_entries_newest_first(names):
	if not names:
		return []
	rows = frappe.get_all(
		"Stock Entry",
		filters={"name": ["in", list(names)]},
		fields=["name"],
		order_by="posting_date desc, posting_time desc, creation desc",
	)
	return [r.name for r in rows]


def _find_parents_for_stock_entries(stock_entries):
	"""Return [(doctype, name), ...] for submitted parents linking these SEs."""
	if not stock_entries:
		return []
	found = []
	seen = set()
	for doctype, fieldname in SE_PARENT_LINKS:
		if not frappe.db.exists("DocType", doctype):
			continue
		rows = frappe.get_all(
			doctype,
			filters={fieldname: ["in", list(stock_entries)], "docstatus": 1},
			fields=["name", "creation"],
			order_by="creation desc",
		)
		for row in rows:
			key = (doctype, row.name)
			if key in seen:
				continue
			seen.add(key)
			found.append((doctype, row.name, row.creation))

	# Newest parents first so downstream mattress/quilting cancel before conversion
	found.sort(key=lambda x: x[2] or "", reverse=True)
	return [(d, n) for d, n, _ in found]


def _find_submitted_conversions(item_codes):
	if not item_codes or not frappe.db.exists("DocType", "Mattress Core Conversion"):
		return []
	names = set()
	for child in ("Block Conversion Input", "Block Conversion Output"):
		if not frappe.db.exists("DocType", child):
			continue
		rows = frappe.db.sql(
			f"""
			SELECT DISTINCT parent
			FROM `tab{child}`
			WHERE item_code IN %(items)s
				AND parenttype = 'Mattress Core Conversion'
			""",
			{"items": tuple(item_codes)},
		)
		for r in rows or []:
			if r and r[0]:
				names.add(r[0])
	return [
		n
		for n in names
		if frappe.db.get_value("Mattress Core Conversion", n, "docstatus") == 1
	]


def _conversion_output_items(conversion_names):
	items = set()
	for name in conversion_names or []:
		rows = frappe.get_all(
			"Block Conversion Output",
			filters={"parent": name, "parenttype": "Mattress Core Conversion"},
			pluck="item_code",
		)
		items.update([r for r in rows if r])
	return sorted(items)
