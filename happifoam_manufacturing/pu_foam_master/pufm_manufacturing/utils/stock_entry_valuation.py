# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

"""Stock Entry valuation helpers — Option A balance-after-build.

Rule: for every Manufacture / Repack we create,
  sum(source row amounts) + sum(additional_costs)
    == sum(target row amounts)   [within tolerance]

Source rates must come from the same warehouse the line issues from.
Finished goods must never be posted at rate 0 when sources have value.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

DEFAULT_TOLERANCE = 0.05
PRECISION = 5


def get_stock_valuation_rate(item_code, warehouse=None, batch_no=None):
	"""Best available outgoing rate for an item at a warehouse (never prefer empty Batch.VR)."""
	if not item_code:
		return 0.0

	if item_code and warehouse:
		bin_rate = flt(
			frappe.db.get_value(
				"Bin",
				{"item_code": item_code, "warehouse": warehouse},
				"valuation_rate",
			)
		)
		if bin_rate > 0:
			return bin_rate

	if batch_no:
		sle_rate = _latest_sle_rate(item_code=item_code, warehouse=warehouse, batch_no=batch_no)
		if sle_rate > 0:
			return sle_rate
		meta = frappe.get_meta("Batch")
		if meta.has_field("valuation_rate"):
			batch_rate = flt(frappe.db.get_value("Batch", batch_no, "valuation_rate"))
			if batch_rate > 0:
				return batch_rate

	if item_code and warehouse:
		sle_rate = _latest_sle_rate(item_code=item_code, warehouse=warehouse, batch_no=None)
		if sle_rate > 0:
			return sle_rate

	return flt(frappe.db.get_value("Item", item_code, "valuation_rate"))


def _latest_sle_rate(item_code, warehouse=None, batch_no=None):
	conditions = ["item_code = %s", "actual_qty != 0"]
	values = [item_code]
	if warehouse:
		conditions.append("warehouse = %s")
		values.append(warehouse)
	if batch_no:
		conditions.append("batch_no = %s")
		values.append(batch_no)

	rows = frappe.db.sql(
		"""
		SELECT actual_qty, stock_value_difference, incoming_rate, valuation_rate
		FROM `tabStock Ledger Entry`
		WHERE {where}
		ORDER BY posting_date DESC, posting_time DESC, creation DESC
		LIMIT 5
		""".format(
			where=" AND ".join(conditions)
		),
		tuple(values),
		as_dict=True,
	)
	for row in rows or []:
		qty = flt(row.actual_qty)
		if qty:
			rate = abs(flt(row.stock_value_difference) / qty)
			if rate > 0:
				return rate
		for field in ("incoming_rate", "valuation_rate"):
			rate = flt(row.get(field))
			if rate > 0:
				return rate
	return 0.0


def row_amount(row):
	qty = flt(row.get("qty") if isinstance(row, dict) else row.qty)
	rate = flt(
		row.get("basic_rate")
		if isinstance(row, dict)
		else (row.basic_rate or row.valuation_rate)
	)
	amount = flt(
		row.get("amount") if isinstance(row, dict) else getattr(row, "amount", None)
	)
	if amount:
		return flt(amount, PRECISION)
	return flt(qty * rate, PRECISION)


def stock_entry_source_amount(entry):
	total = 0.0
	for row in entry.get("items") or []:
		if row.s_warehouse and flt(row.qty):
			total = flt(total + row_amount(row), PRECISION)
	return total


def stock_entry_target_amount(entry):
	total = 0.0
	for row in entry.get("items") or []:
		if row.t_warehouse and flt(row.qty):
			total = flt(total + row_amount(row), PRECISION)
	return total


def stock_entry_additional_amount(entry):
	total = 0.0
	for row in entry.get("additional_costs") or []:
		total = flt(total + flt(row.amount), PRECISION)
	return total


def apply_manual_rate(row, rate, precision=PRECISION):
	"""Stamp qty×rate onto a Stock Entry Item (dict or child doc)."""
	rate = flt(rate, precision)
	qty = flt(row.get("qty") if isinstance(row, dict) else row.qty)
	amount = flt(qty * rate, precision)
	if isinstance(row, dict):
		row["basic_rate"] = rate
		row["valuation_rate"] = rate
		row["amount"] = amount
		row["set_basic_rate_manually"] = 1
		row["allow_zero_valuation_rate"] = 1 if rate <= 0 else 0
	else:
		row.basic_rate = rate
		row.valuation_rate = rate
		row.amount = amount
		row.set_basic_rate_manually = 1
		row.allow_zero_valuation_rate = 1 if rate <= 0 else 0
	return amount


def balance_stock_entry_targets(
	entry,
	scrap_item=None,
	tolerance=DEFAULT_TOLERANCE,
	context="Stock Entry",
):
	"""
	Force target (t_warehouse) amounts so:
	  sources + additional_costs == targets
	Residual is absorbed into the last non-scrap finished row.
	Raises if sources have value but no FG row can absorb, or balance fails.
	"""
	# Sync amount fields from rates first
	for row in entry.get("items") or []:
		qty = flt(row.qty)
		rate = flt(row.basic_rate or row.valuation_rate)
		if qty and (row.s_warehouse or row.t_warehouse):
			row.amount = flt(qty * rate, PRECISION)
			row.set_basic_rate_manually = 1
			if rate > 0:
				row.allow_zero_valuation_rate = 0

	source_total = stock_entry_source_amount(entry)
	additional_total = stock_entry_additional_amount(entry)
	target_total = stock_entry_target_amount(entry)
	left = flt(source_total + additional_total, PRECISION)
	right = flt(target_total, PRECISION)
	residual = flt(left - right, PRECISION)

	if abs(residual) <= flt(tolerance):
		_assert_fg_not_zero_when_sources_valued(entry, source_total, context, scrap_item=scrap_item)
		return residual

	absorb_row = None
	for row in reversed(entry.get("items") or []):
		if not row.t_warehouse or flt(row.qty) <= 0:
			continue
		if scrap_item and row.item_code == scrap_item:
			continue
		absorb_row = row
		break

	if not absorb_row:
		# Only scrap targets — allow residual onto scrap as last resort
		for row in reversed(entry.get("items") or []):
			if row.t_warehouse and flt(row.qty) > 0:
				absorb_row = row
				break

	if not absorb_row:
		frappe.throw(
			_(
				"{0}: cannot balance Stock Entry — sources worth {1} but no finished/"
				"scrap target row to absorb cost."
			).format(context, frappe.format_value(left, {"fieldtype": "Currency"}))
		)

	qty = flt(absorb_row.qty)
	new_amount = flt(flt(absorb_row.basic_rate) * qty + residual, PRECISION)
	if qty <= 0:
		frappe.throw(_("{0}: absorb row has zero qty.").format(context))
	new_rate = flt(new_amount / qty, PRECISION)
	if new_amount < 0 and abs(new_amount) > flt(tolerance):
		frappe.throw(
			_(
				"{0}: balancing would make finished item {1} negative (amount {2}). "
				"Check scrap valuation and source rates."
			).format(
				context,
				absorb_row.item_code,
				frappe.format_value(new_amount, {"fieldtype": "Currency"}),
			)
		)
	absorb_row.basic_rate = new_rate
	absorb_row.valuation_rate = new_rate
	absorb_row.amount = new_amount
	absorb_row.set_basic_rate_manually = 1
	absorb_row.allow_zero_valuation_rate = 1 if new_rate <= 0 else 0

	source_total = stock_entry_source_amount(entry)
	additional_total = stock_entry_additional_amount(entry)
	target_total = stock_entry_target_amount(entry)
	left = flt(source_total + additional_total, PRECISION)
	right = flt(target_total, PRECISION)
	if abs(left - right) > flt(tolerance):
		frappe.throw(
			_(
				"{0}: Stock Entry still unbalanced after residual absorb "
				"(sources+overhead {1} vs targets {2})."
			).format(
				context,
				frappe.format_value(left, {"fieldtype": "Currency"}),
				frappe.format_value(right, {"fieldtype": "Currency"}),
			)
		)

	_assert_fg_not_zero_when_sources_valued(entry, source_total, context, scrap_item=scrap_item)
	return residual


def _assert_fg_not_zero_when_sources_valued(entry, source_total, context, scrap_item=None):
	if flt(source_total) <= 0:
		return
	for row in entry.get("items") or []:
		if not row.t_warehouse or flt(row.qty) <= 0:
			continue
		if scrap_item and row.item_code == scrap_item:
			continue
		rate = flt(row.basic_rate or row.valuation_rate)
		if rate <= 0 and flt(row_amount(row)) <= 0:
			frappe.throw(
				_(
					"{0}: finished item {1} would post at zero value while raw "
					"materials are worth {2}. Fix input valuation rates."
				).format(
					context,
					row.item_code,
					frappe.format_value(source_total, {"fieldtype": "Currency"}),
				)
			)


def set_finished_unit_rate_from_pool(entry, finished_item_code, pool_amount, scrap_item=None):
	"""Set every finished row of finished_item_code so qty*rate shares pool_amount by qty weight."""
	fg_rows = [
		row
		for row in entry.get("items") or []
		if row.t_warehouse
		and row.item_code == finished_item_code
		and flt(row.qty) > 0
		and (not scrap_item or row.item_code != scrap_item)
	]
	if not fg_rows:
		return
	total_qty = sum(flt(r.qty) for r in fg_rows)
	if total_qty <= 0:
		return
	unit = flt(flt(pool_amount) / total_qty, PRECISION)
	for row in fg_rows:
		apply_manual_rate(row, unit)
