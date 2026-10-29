# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cint, flt

from pu_foam_master.pufm_manufacturing.utils.item_cbm import batch_belongs_to_conversion
from pu_foam_master.pufm_manufacturing.utils.stock_entry_valuation import (
	apply_manual_rate,
	finalize_pufm_stock_entry_balance,
	get_stock_valuation_rate,
)


class QuiltingRecord(Document):
	def validate(self):
		if not self.company:
			frappe.throw("Company is required.")
		self._validate_job_order()
		self._validate_core_conversion()
		self._validate_materials()
		self._calculate_variance_fields()
		# Draft save must show cost; submit uses the same formula with strict valuation.
		self.total_production_cost = self._calculate_total_cost(strict=False)

	def before_submit(self):
		self._calculate_variance_fields()
		self.total_production_cost = self._calculate_total_cost(strict=True)

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

	def _validate_core_conversion(self):
		if not self.job_order:
			return
		if not self.core_conversion:
			frappe.throw(
				"Core Conversion is required when quilting from a Quilting Job Order "
				"(so sheeting roll batches can be traced)."
			)
		if not frappe.db.exists("Mattress Core Conversion", self.core_conversion):
			frappe.throw("Core Conversion {0} was not found.".format(self.core_conversion))
		conv = frappe.db.get_value(
			"Mattress Core Conversion",
			self.core_conversion,
			["job_order", "docstatus"],
			as_dict=True,
		)
		if not conv or conv.job_order != self.job_order:
			frappe.throw(
				"Core Conversion {0} does not belong to Job Order {1}.".format(
					self.core_conversion, self.job_order
				)
			)
		if cint(conv.docstatus) != 1:
			frappe.throw(
				"Core Conversion {0} must be submitted before quilting.".format(self.core_conversion)
			)

	def _sync_job_order_on_change(self):
		if not self.job_order:
			return
		from pu_foam_master.pufm_manufacturing.doctype.pufm_job_order.pufm_job_order import (
			reconcile_job_order_workflow,
		)

		reconcile_job_order_workflow(self.job_order)

	def _material_lines(self):
		return [
			{
				"label": "Fabric",
				"item_code": self.fabric_item,
				"warehouse": self.fabric_warehouse,
				"batch_no": self.fabric_batch,
				"qty": flt(self.fabric_qty_meters),
			},
			{
				"label": "Sheeting Roll",
				"item_code": self.sheeting_roll_item,
				"warehouse": self.sheeting_warehouse,
				"batch_no": self.sheeting_batch,
				"qty": flt(self.sheeting_qty_meters),
			},
		]

	def _validate_materials(self):
		if flt(self.output_qty_meters) <= 0:
			frappe.throw("Output Qty (Meters) must be greater than zero.")
		if not self.finished_item:
			frappe.throw("Finished Quilted Item is required.")
		if not self.target_warehouse:
			frappe.throw("Target Warehouse is required.")
		if self.fabric_item and self.sheeting_roll_item and self.fabric_item == self.sheeting_roll_item:
			frappe.throw("Fabric Item and Sheeting Roll Item must be different.")

		for line in self._material_lines():
			if not line["item_code"]:
				frappe.throw("{0} Item is required.".format(line["label"]))
			if not line["warehouse"]:
				frappe.throw("{0} Warehouse is required.".format(line["label"]))
			if not line["batch_no"]:
				frappe.throw("{0} Batch is required.".format(line["label"]))
			if line["qty"] <= 0:
				frappe.throw("{0} Qty (Meters) must be greater than zero.".format(line["label"]))
			batch_item = frappe.db.get_value("Batch", line["batch_no"], "item")
			if batch_item and batch_item != line["item_code"]:
				frappe.throw(
					"{0} Batch {1} belongs to {2}, not {3}.".format(
						line["label"], line["batch_no"], batch_item, line["item_code"]
					)
				)

		if self.core_conversion and self.sheeting_batch:
			if not batch_belongs_to_conversion(self.sheeting_batch, self.core_conversion):
				frappe.throw(
					"Sheeting Batch {0} was not produced by Core Conversion {1}.".format(
						self.sheeting_batch, self.core_conversion
					)
				)

	def _calculate_variance_fields(self):
		# Variance uses the larger of the two input meters (same rule as before).
		total_input = max(flt(self.fabric_qty_meters), flt(self.sheeting_qty_meters))
		self.total_input_meters = total_input
		self.variance_meters = (
			flt(total_input) - flt(self.output_qty_meters) if self.output_qty_meters else 0
		)

	def _get_quilting_overhead(self):
		"""
		Quilting overhead from Pufm Manufacturing Settings:
		  (gum + thread + non-woven + labor) × output meters
		plus depreciation × output meters (separate; often 0).
		Component sum is preferred so a stale total_quilting_rate_per_m cannot zero out cost.
		"""
		settings = frappe.get_single("Pufm Manufacturing Settings")
		component_rate = (
			flt(settings.gum_cost_per_m)
			+ flt(settings.thread_cost_per_m_quilt)
			+ flt(settings.non_woven_cost_per_m)
			+ flt(settings.quilting_labor_per_m)
		)
		stored_total = flt(getattr(settings, "total_quilting_rate_per_m", 0) or 0)
		rate = component_rate if component_rate > 0 else stored_total
		meters = flt(self.output_qty_meters)
		overhead_cost = flt(rate) * meters
		depreciation_cost = flt(getattr(settings, "quilting_depreciation_per_m", 0) or 0) * meters
		absorption_account = getattr(settings, "quilting_absorption_account", None)
		return overhead_cost, depreciation_cost, absorption_account

	def _material_rates(self, strict=True):
		"""Outgoing rates from each material warehouse/batch.

		strict=True (submit): missing/zero rate throws.
		strict=False (draft): missing rate treated as 0 so overhead still shows on save.
		"""
		rates = []
		for line in self._material_lines():
			rate = 0.0
			if line["item_code"] and line["warehouse"]:
				rate = get_stock_valuation_rate(
					line["item_code"],
					warehouse=line["warehouse"],
					batch_no=line["batch_no"],
				)
			if rate <= 0:
				if strict:
					frappe.throw(
						"Valuation rate missing for {0} {1} in warehouse {2} "
						"(batch {3}). Receive / revalue stock before submitting.".format(
							line["label"].lower(),
							line["item_code"],
							line["warehouse"],
							line["batch_no"] or "—",
						)
					)
				rate = 0.0
			rates.append(flt(rate))
		return rates

	def _calculate_total_cost(self, strict=True):
		"""
		Total Production Cost =
		  fabric_qty × fabric_rate
		+ sheeting_qty × sheeting_rate
		+ quilting overhead (settings rate × output_qty_meters)
		+ quilting depreciation (settings × output_qty_meters)
		"""
		overhead_cost, depreciation_cost, _ = self._get_quilting_overhead()
		rates = self._material_rates(strict=strict)
		lines = self._material_lines()
		input_cost = sum(flt(line["qty"]) * flt(rate) for line, rate in zip(lines, rates))
		return flt(input_cost + overhead_cost + depreciation_cost, 2)

	def _create_manufacture_stock_entry(self):
		overhead_cost, depreciation_cost, absorption_account = self._get_quilting_overhead()
		if (overhead_cost > 0 or depreciation_cost > 0) and not absorption_account:
			frappe.throw(
				"Set Quilting Absorption Account in Pufm Manufacturing Settings "
				"to post quilting overhead."
			)

		rates = self._material_rates(strict=True)
		lines = self._material_lines()
		input_cost = sum(flt(line["qty"]) * flt(rate) for line, rate in zip(lines, rates))
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

		for line, valuation_rate in zip(lines, rates):
			item_doc = frappe.get_cached_doc("Item", line["item_code"])
			se_row = {
				"item_code": line["item_code"],
				"s_warehouse": line["warehouse"],
				"qty": flt(line["qty"]),
				"batch_no": line["batch_no"],
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
			fg_row["use_serial_batch_fields"] = 1
		entry.append("items", fg_row)

		finalize_pufm_stock_entry_balance(
			entry, context="Quilting Record {0}".format(self.name)
		)

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
