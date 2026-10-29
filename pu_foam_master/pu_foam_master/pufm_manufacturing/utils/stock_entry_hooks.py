# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

"""Stock Entry doc_events — keep PUFM manufacture/repack entries balanced on submit."""

from __future__ import annotations

import frappe
from frappe.utils import flt

from pu_foam_master.pufm_manufacturing.utils.stock_entry_valuation import (
	sync_pufm_stock_entry_after_erpnext_validate,
)


def balance_pufm_stock_entry_on_validate(doc, method=None):
	"""After ERPNext validate (incl. calculate_rate_and_amount): fix outgoing + overhead."""
	if doc.purpose not in ("Manufacture", "Repack"):
		return

	# Only when submitting (docstatus 1 during submit save), not on draft saves.
	if doc.docstatus != 1:
		return

	if not any(flt(row.set_basic_rate_manually) for row in doc.get("items") or []):
		return

	scrap_item = frappe.db.get_single_value("Pufm Manufacturing Settings", "scrap_item")
	sync_pufm_stock_entry_after_erpnext_validate(
		doc,
		scrap_item=scrap_item,
		context=doc.name or "Stock Entry",
	)
