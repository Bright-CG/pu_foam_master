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
	"""Best available outgoing rate for an item at a warehouse (never prefer empty Batch.VR).

	When batch_no is set, batch-specific valuation wins over warehouse Bin average so
	pre-submit Stock Entry rates match ERPNext batch consumption on submit.
	"""
	if not item_code:
		return 0.0

	if batch_no:
		batch_rate = _batch_valuation_rate(item_code, warehouse, batch_no)
		if batch_rate > 0:
			return batch_rate

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

	if item_code and warehouse:
		sle_rate = _latest_sle_rate(item_code=item_code, warehouse=warehouse, batch_no=None)
		if sle_rate > 0:
			return sle_rate

	return flt(frappe.db.get_value("Item", item_code, "valuation_rate"))


def _batch_valuation_rate(item_code, warehouse=None, batch_no=None):
	"""Batch-specific rate from inbound SLE (v15 bundles) or Batch master."""
	if not batch_no:
		return 0.0

	warehouse_clause = "AND sle.warehouse = %s" if warehouse else ""
	values = [batch_no, batch_no]
	if warehouse:
		values.append(warehouse)

	rows = frappe.db.sql(
		"""
		SELECT sle.incoming_rate, sle.valuation_rate,
			sle.stock_value_difference, sle.actual_qty
		FROM `tabStock Ledger Entry` sle
		LEFT JOIN `tabSerial and Batch Entry` sbe
			ON sbe.parent = sle.serial_and_batch_bundle
		WHERE IFNULL(sle.is_cancelled, 0) = 0
			AND sle.item_code = %s
			AND (sle.batch_no = %s OR sbe.batch_no = %s)
			{warehouse_clause}
		ORDER BY
			CASE WHEN sle.actual_qty > 0 THEN 0 ELSE 1 END,
			sle.posting_date DESC, sle.posting_time DESC, sle.creation DESC
		LIMIT 10
		""".format(warehouse_clause=warehouse_clause),
		[item_code, batch_no, batch_no] + ([warehouse] if warehouse else []),
		as_dict=True,
	)
	for row in rows or []:
		rate = _sle_economic_rate(row, prefer_incoming=True)
		if rate > 0:
			return rate

	meta = frappe.get_meta("Batch")
	if meta.has_field("valuation_rate"):
		batch_rate = flt(frappe.db.get_value("Batch", batch_no, "valuation_rate"))
		if batch_rate > 0:
			return batch_rate

	return 0.0


def _sle_economic_rate(row, prefer_incoming=False):
	"""Extract per-unit rate from an SLE row; prefer true batch cost over bin-blended VR."""
	qty = flt(row.get("actual_qty"))
	incoming_rate = flt(row.get("incoming_rate"))
	if prefer_incoming and qty > 0 and incoming_rate > 0:
		return incoming_rate
	if qty:
		economic = abs(flt(row.get("stock_value_difference")) / qty)
		if economic > 0:
			return economic
	if incoming_rate > 0:
		return incoming_rate
	return flt(row.get("valuation_rate"))


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
		rate = _sle_economic_rate(row)
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
	basic_amount = flt(
		row.get("basic_amount")
		if isinstance(row, dict)
		else getattr(row, "basic_amount", None)
	)
	if basic_amount:
		return flt(basic_amount, PRECISION)
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
		# ERPNext stores company currency on base_amount after landed-cost init
		amt = flt(getattr(row, "base_amount", None) or row.amount)
		total = flt(total + amt, PRECISION)
	return total


def apply_manual_rate(row, rate, precision=PRECISION):
	"""Stamp qty×rate onto a Stock Entry Item (dict or child doc).

	ERPNext Repack/Manufacture totals use ``basic_amount`` (not only ``amount``).
	When ``set_basic_rate_manually`` is set on incoming rows, ``validate`` skips
	auto-pricing — so ``basic_amount`` must be populated here.
	"""
	rate = flt(rate, precision)
	qty = flt(row.get("qty") if isinstance(row, dict) else row.qty)
	transfer_qty = flt(
		row.get("transfer_qty")
		if isinstance(row, dict)
		else getattr(row, "transfer_qty", None)
	)
	if transfer_qty <= 0:
		transfer_qty = qty
	basic_amount = flt(transfer_qty * rate, precision)
	amount = basic_amount

	if isinstance(row, dict):
		row["basic_rate"] = rate
		row["valuation_rate"] = rate
		row["basic_amount"] = basic_amount
		row["amount"] = amount
		row["transfer_qty"] = transfer_qty
		row["set_basic_rate_manually"] = 1
		row["allow_zero_valuation_rate"] = 1 if rate <= 0 else 0
	else:
		row.basic_rate = rate
		row.valuation_rate = rate
		row.basic_amount = basic_amount
		row.amount = amount
		row.transfer_qty = transfer_qty
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
	# Sync amount fields from rates first (ERPNext uses basic_amount on Repack/MFG)
	for row in entry.get("items") or []:
		qty = flt(row.qty)
		transfer_qty = flt(row.transfer_qty) or qty
		rate = flt(row.basic_rate or row.valuation_rate)
		if qty and (row.s_warehouse or row.t_warehouse):
			row.transfer_qty = transfer_qty
			row.basic_amount = flt(transfer_qty * rate, PRECISION)
			additional = flt(getattr(row, "additional_cost", 0))
			row.amount = flt(row.basic_amount + additional, PRECISION)
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
	transfer_qty = flt(absorb_row.transfer_qty) or qty
	if transfer_qty <= 0:
		frappe.throw(_("{0}: absorb row has zero qty.").format(context))

	# Prefer current row amount (may already include distributed additional_cost)
	current_amount = flt(row_amount(absorb_row), PRECISION)
	if not current_amount:
		current_amount = flt(
			flt(absorb_row.basic_rate) * transfer_qty
			+ flt(getattr(absorb_row, "additional_cost", 0)),
			PRECISION,
		)
	new_amount = flt(current_amount + residual, PRECISION)
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

	# Fold residual into basic_amount; keep row.additional_cost so amount =
	# basic_amount + additional_cost (ERPNext convention after distribute).
	line_additional = flt(getattr(absorb_row, "additional_cost", 0))
	new_basic_amount = flt(new_amount - line_additional, PRECISION)
	if new_basic_amount < 0 and abs(new_basic_amount) > flt(tolerance):
		line_additional = 0.0
		absorb_row.additional_cost = 0
		new_basic_amount = new_amount
	new_basic_rate = flt(new_basic_amount / transfer_qty, PRECISION)
	new_valuation_rate = flt(new_amount / transfer_qty, PRECISION)
	absorb_row.basic_rate = new_basic_rate
	absorb_row.valuation_rate = new_valuation_rate
	absorb_row.basic_amount = new_basic_amount
	absorb_row.amount = new_amount
	absorb_row.set_basic_rate_manually = 1
	absorb_row.allow_zero_valuation_rate = 1 if new_valuation_rate <= 0 else 0

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


def finalize_pufm_stock_entry_balance(entry, scrap_item=None, context=None):
	"""Re-sync row amounts and enforce source + overhead == targets (call before submit)."""
	for row in entry.get("items") or []:
		qty = flt(row.qty)
		transfer_qty = flt(row.transfer_qty) or qty
		rate = flt(row.basic_rate or row.valuation_rate)
		if qty and (row.s_warehouse or row.t_warehouse):
			row.transfer_qty = transfer_qty
			row.basic_amount = flt(transfer_qty * rate, PRECISION)
			additional = flt(getattr(row, "additional_cost", 0))
			row.amount = flt(row.basic_amount + additional, PRECISION)
			if rate > 0:
				row.set_basic_rate_manually = 1
				row.allow_zero_valuation_rate = 0

	return balance_stock_entry_targets(
		entry,
		scrap_item=scrap_item,
		context=context or getattr(entry, "name", None) or "Stock Entry",
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
