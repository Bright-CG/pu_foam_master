# Copyright (c) 2026, Happifoam and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cint, flt


class QuiltingRecord(Document):
	def validate(self):
		if not self.company:
			frappe.throw("Company is required.")
		self._validate_inputs()
		self._calculate_variance_fields()

	def before_submit(self):
		self._calculate_variance_fields()
		self.total_production_cost = self._calculate_total_cost()

	def on_submit(self):
		stock_entry = self._create_manufacture_stock_entry()
		self.db_set("stock_entry", stock_entry.name, update_modified=False)

	def on_cancel(self):
		if self.stock_entry and frappe.db.exists("Stock Entry", self.stock_entry):
			se = frappe.get_doc("Stock Entry", self.stock_entry)
			if se.docstatus == 1:
				se.cancel()

	def _validate_inputs(self):
		if flt(self.output_qty_meters) <= 0:
			frappe.throw("Output Qty (Meters) must be greater than zero.")
		if len(self.get("inputs") or []) != 2:
			frappe.throw("Exactly two input rows are required (1 fabric and 1 foam roll).")
		for row in self.inputs:
			if flt(row.qty) <= 0:
				frappe.throw(f"Row {row.idx}: Qty must be greater than zero.")
			if not row.batch_no:
				frappe.throw(f"Row {row.idx}: Batch No is required.")
			if not row.source_warehouse:
				frappe.throw(f"Row {row.idx}: Source Warehouse is required.")

	def _calculate_variance_fields(self):
		total_input = 0.0
		for row in self.get("inputs") or []:
			if flt(row.qty) > total_input:
				total_input = flt(row.qty)
		self.total_input_meters = total_input
		self.variance_meters = (
			flt(total_input) - flt(self.output_qty_meters) if self.output_qty_meters else 0
		)

	def _get_quilting_overhead(self):
		settings = frappe.get_single("Pufm Manufacturing Settings")
		rate = flt(getattr(settings, "total_quilting_rate_per_m", 0) or 0)
		if not rate:
			# Fallback if total not yet saved: sum components
			rate = (
				flt(settings.gum_cost_per_m)
				+ flt(settings.thread_cost_per_m_quilt)
				+ flt(settings.non_woven_cost_per_m)
				+ flt(settings.quilting_labor_per_m)
			)
		overhead_cost = rate * flt(self.output_qty_meters)
		absorption_account = getattr(settings, "quilting_absorption_account", None)
		return overhead_cost, absorption_account

	def _calculate_total_cost(self):
		overhead_cost, _ = self._get_quilting_overhead()
		input_cost = 0
		for row in self.inputs:
			valuation_rate = _get_batch_valuation_rate(row.batch_no)
			input_cost += flt(row.qty) * valuation_rate
		return input_cost + overhead_cost

	def _create_manufacture_stock_entry(self):
		overhead_cost, absorption_account = self._get_quilting_overhead()
		if overhead_cost > 0 and not absorption_account:
			frappe.throw(
				"Set Quilting Absorption Account in Pufm Manufacturing Settings "
				"to post quilting overhead."
			)

		input_cost = 0.0
		source_rates = {}
		for row in self.inputs:
			rate = _get_batch_valuation_rate(row.batch_no)
			source_rates[row.idx] = rate
			input_cost += flt(row.qty) * rate

		output_qty = flt(self.output_qty_meters)
		unit_rate = (input_cost / output_qty) if output_qty else 0

		fg_batch = self._ensure_output_batch(self.finished_item)

		entry = frappe.new_doc("Stock Entry")
		entry.company = self.company
		entry.stock_entry_type = "Manufacture"
		entry.purpose = "Manufacture"
		entry.posting_date = self.posting_date
		entry.set_posting_time = 1

		if overhead_cost > 0 and absorption_account:
			entry.append(
				"additional_costs",
				{
					"expense_account": absorption_account,
					"description": "Quilting Operations for {0}".format(self.name),
					"amount": overhead_cost,
				},
			)

		for row in self.inputs:
			item_doc = frappe.get_cached_doc("Item", row.item_code)
			valuation_rate = flt(source_rates.get(row.idx))
			entry.append(
				"items",
				{
					"item_code": row.item_code,
					"s_warehouse": row.source_warehouse,
					"qty": flt(row.qty),
					"batch_no": row.batch_no,
					"uom": item_doc.stock_uom,
					"stock_uom": item_doc.stock_uom,
					"conversion_factor": 1,
					"basic_rate": valuation_rate,
					"valuation_rate": valuation_rate,
					"set_basic_rate_manually": 1,
					"allow_zero_valuation_rate": 1 if valuation_rate <= 0 else 0,
				},
			)

		finished_doc = frappe.get_cached_doc("Item", self.finished_item)
		fg_row = {
			"item_code": self.finished_item,
			"t_warehouse": self.target_warehouse,
			"qty": output_qty,
			"uom": finished_doc.stock_uom or "Meter",
			"stock_uom": finished_doc.stock_uom or "Meter",
			"conversion_factor": 1,
			"basic_rate": unit_rate,
			"valuation_rate": unit_rate,
			"set_basic_rate_manually": 1,
			"allow_zero_valuation_rate": 1 if unit_rate <= 0 else 0,
			"is_finished_item": 1,
		}
		if cint(finished_doc.has_batch_no):
			fg_row["batch_no"] = fg_batch
		entry.append("items", fg_row)

		entry.insert(ignore_permissions=True)
		entry.submit()
		return entry

	def _ensure_output_batch(self, item_code):
		"""Create a Batch for the finished quilted item (FIFO outbound later)."""
		batch_id = f"{self.name}-{item_code}"
		if not frappe.db.exists("Batch", batch_id):
			new_batch = frappe.new_doc("Batch")
			new_batch.batch_id = batch_id
			new_batch.item = item_code
			new_batch.reference_doctype = "Quilting Record"
			new_batch.reference_name = self.name
			new_batch.insert(ignore_permissions=True)
		return batch_id


def _get_batch_valuation_rate(batch_no):
	if not batch_no:
		return 0

	meta = frappe.get_meta("Batch")
	if meta.has_field("valuation_rate"):
		return flt(frappe.db.get_value("Batch", batch_no, "valuation_rate"))

	row = frappe.db.sql(
		"""
		SELECT valuation_rate
		FROM `tabStock Ledger Entry`
		WHERE batch_no = %s
		ORDER BY posting_date DESC, posting_time DESC, creation DESC
		LIMIT 1
		""",
		(batch_no,),
		as_dict=True,
	)
	return flt(row[0].valuation_rate) if row else 0
