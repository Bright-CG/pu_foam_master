# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

"""Stock Entry doc_events — keep PUFM manufacture/repack entries balanced on submit."""

from __future__ import annotations

import frappe
from frappe.utils import flt

from pu_foam_master.pufm_manufacturing.utils.stock_entry_valuation import (
	finalize_pufm_stock_entry_balance,
)


def balance_pufm_stock_entry_before_submit(doc, method=None):
	"""Re-balance manually rated entries so yield/overhead stays in FG, not Stock Adjustment."""
	if doc.purpose not in ("Manufacture", "Repack"):
		return

	# docstatus is already 1 when before_submit runs (set before save on submit)
	if doc.docstatus == 2:
		return

	if not any(flt(row.set_basic_rate_manually) for row in doc.get("items") or []):
		return

	scrap_item = frappe.db.get_single_value("Pufm Manufacturing Settings", "scrap_item")
	finalize_pufm_stock_entry_balance(
		doc,
		scrap_item=scrap_item,
		context=doc.name or "Stock Entry",
	)
