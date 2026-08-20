# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cint, flt

from pu_foam_master.pufm_manufacturing.utils.stock_entry_valuation import (
	apply_manual_rate,
	balance_stock_entry_targets,
	get_stock_valuation_rate,
)


class QuiltingRecord(Document):
	def validate(self):
		if not self.company:
			frappe.throw("Company is required.")
		self._validate_job_order()
		self._validate_inputs()
		self._calculate_variance_fields()

	def before_submit(self):
		self._calculate_variance_fields()
		self.total_production_cost = self._calculate_total_cost()

	def on_submit(self):
		stock_entry = self._create_manufacture_stock_entry()
		self.db_set("stock_entry", stock_entry.name, update_modified=False)
		self._sync_job_order_on_change()

	def on_cancel(self):
		if self.stock_entry and frappe.db.exists("Stock Entry", self.stock_entry):
			se = frappe.get_doc("Stock Entry", self.stock_entry)
			if se.docstatus == 1:
				se.cancel()
		self._sync_job_order_on_change()

	def _validate_job_order(self):
		if not self.job_order:
			return
		if not frappe.db.exists("Pufm Job Order", self.job_order):
			frappe.throw("Job Order {0} was not found.".format(self.job_order))
		order_type, docstatus = frappe.db.get_value(
			"Pufm Job Order", self.job_order, ["order_type", "docstatus"]
		)
		if cint(docstatus) != 1:
			frappe.throw("Job Order {0} must be submitted before linking quilting.".format(self.job_order))
		if order_type and order_type != "Quilting":
			frappe.throw(
				"Job Order {0} is type {1}. Quilting Record only accepts Quilting Job Orders.".format(
					self.job_order, order_type
				)
			)

	def _sync_job_order_on_change(self):
		if not self.job_order:
			return
		from pu_foam_master.pufm_manufacturing.doctype.pufm_job_order.pufm_job_order import (
			reconcile_job_order_workflow,
		)

		reconcile_job_order_workflow(self.job_order)

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
			rate = (
				flt(settings.gum_cost_per_m)
				+ flt(settings.thread_cost_per_m_quilt)
				+ flt(settings.non_woven_cost_per_m)
				+ flt(settings.quilting_labor_per_m)
			)
		meters = flt(self.output_qty_meters)
		overhead_cost = rate * meters
		depreciation_cost = flt(getattr(settings, "quilting_depreciation_per_m", 0) or 0) * meters
		absorption_account = getattr(settings, "quilting_absorption_account", None)
		return overhead_cost, depreciation_cost, absorption_account

	def _input_rates(self):
		"""Outgoing rates from the warehouse each input actually issues from."""
		rates = {}
		for row in self.inputs:
			rate = get_stock_valuation_rate(
				row.item_code,
				warehouse=row.source_warehouse,
				batch_no=row.batch_no,
			)
			if rate <= 0:
				frappe.throw(
					"Valuation rate missing for quilting input {0} in warehouse {1} "
					"(batch {2}). Receive / revalue stock before submitting.".format(
						row.item_code, row.source_warehouse, row.batch_no or "—"
					)
				)
			rates[row.idx] = rate
		return rates

	def _calculate_total_cost(self):
		overhead_cost, depreciation_cost, _ = self._get_quilting_overhead()
		input_cost = 0.0
		for row in self.inputs:
			rate = get_stock_valuation_rate(
				row.item_code,
				warehouse=row.source_warehouse,
				batch_no=row.batch_no,
			)
			input_cost += flt(row.qty) * rate
		return input_cost + overhead_cost + depreciation_cost

	def _create_manufacture_stock_entry(self):
		overhead_cost, depreciation_cost, absorption_account = self._get_quilting_overhead()
		if (overhead_cost > 0 or depreciation_cost > 0) and not absorption_account:
			frappe.throw(
				"Set Quilting Absorption Account in Pufm Manufacturing Settings "
				"to post quilting overhead."
			)

		source_rates = self._input_rates()
		input_cost = sum(flt(row.qty) * flt(source_rates[row.idx]) for row in self.inputs)
		output_qty = flt(self.output_qty_meters)
		# Materials only in basic rate; overhead via additional_costs then balance absorbs both.
		material_unit_rate = (input_cost / output_qty) if output_qty else 0

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
		if depreciation_cost > 0 and absorption_account:
			entry.append(
				"additional_costs",
				{
					"expense_account": absorption_account,
					"description": "Quilting Depreciation for {0}".format(self.name),
					"amount": depreciation_cost,
				},
			)

		for row in self.inputs:
			item_doc = frappe.get_cached_doc("Item", row.item_code)
			valuation_rate = flt(source_rates.get(row.idx))
			se_row = {
				"item_code": row.item_code,
				"s_warehouse": row.source_warehouse,
				"qty": flt(row.qty),
				"batch_no": row.batch_no,
				"uom": item_doc.stock_uom,
				"stock_uom": item_doc.stock_uom,
				"conversion_factor": 1,
				"use_serial_batch_fields": 1,
			}
			apply_manual_rate(se_row, valuation_rate)
			entry.append("items", se_row)

		finished_doc = frappe.get_cached_doc("Item", self.finished_item)
		fg_row = {
			"item_code": self.finished_item,
			"t_warehouse": self.target_warehouse,
			"qty": output_qty,
			"uom": finished_doc.stock_uom or "Meter",
			"stock_uom": finished_doc.stock_uom or "Meter",
			"conversion_factor": 1,
			"is_finished_item": 1,
		}
		apply_manual_rate(fg_row, material_unit_rate)
		if cint(finished_doc.has_batch_no):
			fg_row["batch_no"] = fg_batch
		entry.append("items", fg_row)

		balance_stock_entry_targets(entry, context="Quilting Record {0}".format(self.name))

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
