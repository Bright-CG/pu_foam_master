import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import cint, flt


class MattressCoreConversion(Document):
	def autoname(self):
		self.name = make_autoname(self.naming_series or "CONV-.YYYY.-.MM.-.#####")

	def validate(self):
		if not self.processed_by:
			self.processed_by = frappe.session.user
		self._set_conversion_rate()
		self._recalculate_totals()
		self._validate_rows()

	def on_submit(self):
		self._create_repack_stock_entry()
		self._sync_job_order_on_submit()
		self._sync_job_order_operator(self.processed_by)

	def on_cancel(self):
		if self.stock_entry and frappe.db.exists("Stock Entry", self.stock_entry):
			se = frappe.get_doc("Stock Entry", self.stock_entry)
			if se.docstatus == 1:
				se.cancel()
		self._sync_job_order_on_cancel()
		self._sync_job_order_operator(None)

	def _sync_job_order_operator(self, user):
		if not self.job_order:
			return
		if not frappe.db.exists("Pufm Job Order", self.job_order):
			return
		frappe.db.set_value("Pufm Job Order", self.job_order, "sliced_by", user)

	def _sync_job_order_on_submit(self):
		if not self.job_order:
			return
		if not frappe.db.exists("Pufm Job Order", self.job_order):
			return
		order_type = frappe.db.get_value("Pufm Job Order", self.job_order, "order_type")
		from pu_foam_master.pufm_manufacturing.doctype.pufm_job_order.pufm_job_order import (
			sync_job_order_status,
		)

		if order_type == "Mattress":
			sync_job_order_status(self.job_order, "Pending Assembly")
		# Sheetings Job Orders complete via Pufm Sheeting Conversion (no stock SE).

	def _sync_job_order_on_cancel(self):
		if not self.job_order:
			return
		if not frappe.db.exists("Pufm Job Order", self.job_order):
			return
		from pu_foam_master.pufm_manufacturing.doctype.pufm_job_order.pufm_job_order import (
			sync_job_order_status,
		)

		sync_job_order_status(self.job_order, "Pending Slicing")

	def _set_conversion_rate(self):
		settings = frappe.get_single("Pufm Manufacturing Settings")
		self.conversion_rate = flt(getattr(settings, "conversion_rate_per_cbm", 0) or 0)

	def _recalculate_totals(self):
		self.total_input_cbm = sum(flt(row.total_cbm) for row in self.get("inputs") or [])
		self.total_output_cbm = sum(flt(row.total_cbm) for row in self.get("outputs") or [])
		self.cbm_variance = flt(self.total_output_cbm) - flt(self.total_input_cbm)
		self.conversion_cost = flt(flt(self.total_input_cbm) * flt(self.conversion_rate), 2)
		if self.total_input_cbm:
			self.variance_percentage = flt(
				((self.total_output_cbm - self.total_input_cbm) / self.total_input_cbm) * 100,
				2,
			)
		else:
			self.variance_percentage = 0.0

	def _validate_rows(self):
		if not self.company:
			frappe.throw("Company is required.")

		if not self.target_warehouse:
			frappe.throw("Target Warehouse is required.")

		if not self.inputs:
			frappe.throw("At least one input row is required.")

		if not self.outputs:
			frappe.throw("At least one output row is required.")

		density_prefixes = set()
		for row in self.inputs:
			if not row.source_warehouse:
				frappe.throw(f"Source Warehouse is required in input row {row.idx}.")
			if not row.item_code:
				frappe.throw(f"Item Code is required in input row {row.idx}.")
			if flt(row.qty) <= 0:
				frappe.throw(f"Qty must be greater than zero in input row {row.idx}.")

			has_batch = cint(frappe.db.get_value("Item", row.item_code, "has_batch_no"))
			has_serial = cint(frappe.db.get_value("Item", row.item_code, "has_serial_no"))
			if has_batch and not row.batch_no:
				frappe.throw(
					f"Batch No is required in input row {row.idx} "
					f"(Item {row.item_code} is batch-tracked)."
				)
			if has_serial and not row.serial_no:
				frappe.throw(
					f"Serial No is required in input row {row.idx} "
					f"(Item {row.item_code} is serial-tracked)."
				)
			if has_serial and flt(row.qty) != 1:
				frappe.throw(
					f"Input row {row.idx}: serial-tracked blocks must have Qty = 1 "
					"(one row per serial)."
				)

			# Allow multi-size / gumming; block multi-density cost pooling
			prefix = (
				row.item_code.split("-")[0]
				if "-" in row.item_code
				else row.item_code
			)
			density_prefixes.add(prefix)

		if len(density_prefixes) > 1:
			frappe.throw(
				"Costing Error: You are mixing different foam densities ({0}). "
				"You can mix different block sizes, but they MUST be of the same density "
				"in a single conversion document.".format(", ".join(sorted(density_prefixes)))
			)

		for row in self.outputs:
			if not row.item_code:
				frappe.throw(f"Item Code is required in output row {row.idx}.")
			if flt(row.qty) <= 0:
				frappe.throw(f"Qty must be greater than zero in output row {row.idx}.")

		if flt(self.total_input_cbm) <= 0:
			frappe.throw("Total Input CBM must be greater than zero.")
		if flt(self.total_output_cbm) <= 0:
			frappe.throw("Total Output CBM must be greater than zero.")

	def _create_repack_stock_entry(self):
		"""
		Repack Stock Entry with volumetric cost apportionment:
		  Total Input Cost = Sum(Core/Sheet Value) + Scrap Value
		"""
		PRECISION = 5
		input_rows = self.get("inputs") or []
		output_rows = self.get("outputs") or []

		settings = frappe.get_single("Pufm Manufacturing Settings")
		scrap_output_rate = flt(getattr(settings, "scrap_output_rate", 0) or 0)
		scrap_item = getattr(settings, "scrap_item", None)
		scrap_warehouse = getattr(settings, "default_scrap_warehouse", None)
		conversion_absorption_account = getattr(settings, "conversion_absorption_account", None)
		conversion_cost = flt(self.conversion_cost)

		if scrap_warehouse:
			scrap_wh_company = frappe.db.get_value("Warehouse", scrap_warehouse, "company")
			if scrap_wh_company and scrap_wh_company != self.company:
				frappe.throw(
					"Default Scrap Warehouse {0} belongs to {1}, not {2}.".format(
						scrap_warehouse, scrap_wh_company, self.company
					)
				)

		if conversion_cost > 0 and not conversion_absorption_account:
			frappe.throw(
				"Set Conversion (Slicing) Absorption Account in Pufm Manufacturing Settings "
				"to post conversion overhead."
			)

		# --- Step 1: Source block value ---
		total_input_cost = 0.0
		source_rates = {}
		for row in input_rows:
			source_rate = flt(
				frappe.db.get_value(
					"Bin",
					{"item_code": row.item_code, "warehouse": row.source_warehouse},
					"valuation_rate",
				)
				or 0.0
			)
			source_rates[row.idx] = source_rate
			total_input_cost = flt(total_input_cost + (flt(row.qty) * source_rate), PRECISION)

		# --- Step 2: Scrap + conversion overhead → net cost per CBM ---
		scrap_value = flt(flt(self.scrap_weight) * scrap_output_rate, PRECISION)
		net_slicing_cost = flt(total_input_cost + conversion_cost - scrap_value, PRECISION)
		total_output_cbm = flt(self.total_output_cbm)
		cost_per_cbm = (
			flt(net_slicing_cost / total_output_cbm, PRECISION) if total_output_cbm > 0 else 0.0
		)

		entry = frappe.new_doc("Stock Entry")
		entry.company = self.company
		entry.stock_entry_type = "Repack"
		entry.purpose = "Repack"
		entry.posting_date = self.posting_date
		entry.set_posting_time = 1

		if conversion_cost > 0 and conversion_absorption_account:
			entry.append(
				"additional_costs",
				{
					"expense_account": conversion_absorption_account,
					"description": "Conversion Operations for {0}".format(self.name),
					"amount": conversion_cost,
				},
			)

		# --- Step 3A: Source rows (blocks) — map batch/serial from input table ---
		for row in input_rows:
			item_doc = frappe.get_cached_doc("Item", row.item_code)
			source_rate = flt(source_rates.get(row.idx), PRECISION)
			source_row = {
				"item_code": row.item_code,
				"qty": flt(row.qty),
				"s_warehouse": row.source_warehouse,
				"uom": item_doc.stock_uom,
				"stock_uom": item_doc.stock_uom,
				"conversion_factor": 1,
				"basic_rate": source_rate,
				"valuation_rate": source_rate,
				"set_basic_rate_manually": 1,
				"allow_zero_valuation_rate": 1 if source_rate <= 0 else 0,
			}
			if row.batch_no or row.serial_no:
				source_row["use_serial_batch_fields"] = 1
			if row.batch_no:
				source_row["batch_no"] = row.batch_no
			if row.serial_no:
				# Stock Entry Detail.serial_no is Text; Link value is the Serial No name
				source_row["serial_no"] = row.serial_no
			entry.append("items", source_row)

		# --- Step 3B: Target scrap ---
		if flt(self.scrap_weight) > 0:
			if not scrap_item or not scrap_warehouse:
				frappe.throw(
					"Please set Scrap Item and Default Scrap Warehouse in Pufm Manufacturing Settings."
				)
			scrap_doc = frappe.get_cached_doc("Item", scrap_item)
			entry.append(
				"items",
				{
					"item_code": scrap_item,
					"qty": flt(self.scrap_weight),
					"t_warehouse": scrap_warehouse,
					"uom": scrap_doc.stock_uom,
					"stock_uom": scrap_doc.stock_uom,
					"conversion_factor": 1,
					"basic_rate": scrap_output_rate,
					"valuation_rate": scrap_output_rate,
					"set_basic_rate_manually": 1,
					"allow_zero_valuation_rate": 1 if scrap_output_rate <= 0 else 0,
				},
			)

		# --- Step 3C: Target cores / sheets (CBM apportionment + batch/serial) ---
		total_target_amount = 0.0
		for row in output_rows:
			item_doc = frappe.get_cached_doc("Item", row.item_code)
			qty = flt(row.qty)
			if qty <= 0:
				continue

			has_serial = cint(frappe.db.get_value("Item", row.item_code, "has_serial_no"))
			# Discrete serialized items need whole qty; continuous sheets (Meter) may be fractional
			if has_serial:
				serial_qty = cint(qty)
				if serial_qty <= 0 or abs(qty - serial_qty) > 0.0001:
					frappe.throw(
						"Output quantity for {0} must be a whole number to generate serial numbers "
						"(got {1}).".format(row.item_code, qty)
					)

			batch_id = self._ensure_output_batch(row.item_code)
			serial_string = None
			if has_serial:
				serial_string = self._build_output_serials(batch_id, cint(qty))

			core_unit_cost = flt(cost_per_cbm * flt(row.unit_cbm), PRECISION)
			amount = flt(core_unit_cost * qty, PRECISION)
			total_target_amount = flt(total_target_amount + amount, PRECISION)

			target_row = {
				"item_code": row.item_code,
				"qty": qty,
				"t_warehouse": self.target_warehouse,
				"uom": row.uom or item_doc.stock_uom,
				"stock_uom": item_doc.stock_uom,
				"conversion_factor": 1,
				"basic_rate": core_unit_cost,
				"valuation_rate": core_unit_cost,
				"amount": amount,
				"set_basic_rate_manually": 1,
				"allow_zero_valuation_rate": 1 if core_unit_cost <= 0 else 0,
				"use_serial_batch_fields": 1,
				"batch_no": batch_id,
			}
			if serial_string:
				target_row["serial_no"] = serial_string

			entry.append("items", target_row)

		# Absorb residual rounding so Input Cost + Conversion = Output Cores + Scrap
		left = flt(total_input_cost + conversion_cost, PRECISION)
		right = flt(total_target_amount + scrap_value, PRECISION)
		residual = flt(left - right, PRECISION)
		if abs(residual) > 0.00001:
			for se_row in reversed(entry.items):
				if (
					se_row.t_warehouse
					and flt(se_row.qty)
					and (not scrap_item or se_row.item_code != scrap_item)
				):
					new_amount = flt(flt(se_row.basic_rate) * flt(se_row.qty) + residual, PRECISION)
					new_rate = flt(new_amount / flt(se_row.qty), PRECISION)
					se_row.basic_rate = new_rate
					se_row.valuation_rate = new_rate
					se_row.amount = new_amount
					break

		entry.insert(ignore_permissions=True)
		entry.submit()
		self.db_set("stock_entry", entry.name, update_modified=False)

	def _ensure_output_batch(self, item_code):
		"""Batch ID inherits conversion name + item (globally unique per ERPNext)."""
		batch_id = f"{self.name}-{item_code}"
		if not frappe.db.exists("Batch", batch_id):
			new_batch = frappe.new_doc("Batch")
			new_batch.batch_id = batch_id
			new_batch.item = item_code
			new_batch.reference_doctype = "Mattress Core Conversion"
			new_batch.reference_name = self.name
			new_batch.insert(ignore_permissions=True)
		return batch_id

	@staticmethod
	def _build_output_serials(batch_id, qty):
		"""Serials: {batch_id}-{n}."""
		return "\n".join(f"{batch_id}-{i}" for i in range(1, cint(qty) + 1))
