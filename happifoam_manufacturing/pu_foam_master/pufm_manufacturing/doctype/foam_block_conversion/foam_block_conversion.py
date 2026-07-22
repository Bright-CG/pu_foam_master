import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import flt


class FoamBlockConversion(Document):
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

	def _set_conversion_rate(self):
		self.conversion_rate = flt(
			frappe.db.get_single_value("Pufm Manufacturing Settings", "conversion_rate_per_cbm")
		)

	def _recalculate_totals(self):
		self.total_input_cbm = sum(flt(row.total_cbm) for row in self.get("inputs") or [])
		self.total_output_cbm = sum(flt(row.total_cbm) for row in self.get("outputs") or [])
		self.cbm_variance = flt(self.total_output_cbm) - flt(self.total_input_cbm)
		self.conversion_cost = flt(self.total_input_cbm) * flt(self.conversion_rate)

	def _validate_rows(self):
		if not self.target_warehouse:
			frappe.throw("Target Warehouse is required.")

		if not self.inputs:
			frappe.throw("At least one input row is required.")

		if not self.outputs:
			frappe.throw("At least one output row is required.")

		for row in self.inputs:
			if not row.source_warehouse:
				frappe.throw(f"Source Warehouse is required in input row {row.idx}.")
			if not row.item_code:
				frappe.throw(f"Item Code is required in input row {row.idx}.")
			if flt(row.qty) <= 0:
				frappe.throw(f"Qty must be greater than zero in input row {row.idx}.")

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
		input_rows = self.get("inputs") or []
		output_rows = self.get("outputs") or []
		total_input_value = 0

		entry = frappe.new_doc("Stock Entry")
		entry.stock_entry_type = "Repack"
		entry.posting_date = self.posting_date
		entry.set_posting_time = 1

		for row in input_rows:
			item_doc = frappe.get_cached_doc("Item", row.item_code)
			valuation_rate = flt(
				frappe.db.get_value(
					"Bin",
					{"item_code": row.item_code, "warehouse": row.source_warehouse},
					"valuation_rate",
				)
			)
			total_input_value += flt(row.qty) * valuation_rate
			entry.append(
				"items",
				{
					"item_code": row.item_code,
					"qty": flt(row.qty),
					"s_warehouse": row.source_warehouse,
					"uom": item_doc.stock_uom,
					"stock_uom": item_doc.stock_uom,
					"conversion_factor": 1,
					"valuation_rate": valuation_rate,
				},
			)

		total_pool = total_input_value + flt(self.conversion_cost)
		total_output_cbm = flt(self.total_output_cbm)

		for row in output_rows:
			item_doc = frappe.get_cached_doc("Item", row.item_code)
			row_total_cbm = flt(row.total_cbm)
			share = (row_total_cbm / total_output_cbm) if total_output_cbm else 0
			output_value = total_pool * share
			basic_rate = (output_value / flt(row.qty)) if flt(row.qty) else 0
			entry.append(
				"items",
				{
					"item_code": row.item_code,
					"qty": flt(row.qty),
					"t_warehouse": self.target_warehouse,
					"uom": row.uom or item_doc.stock_uom,
					"stock_uom": item_doc.stock_uom,
					"conversion_factor": 1,
					"basic_rate": basic_rate,
					"valuation_rate": basic_rate,
				},
			)

		scrap_item = frappe.db.get_single_value("Pufm Manufacturing Settings", "scrap_item")
		scrap_warehouse = frappe.db.get_single_value(
			"Pufm Manufacturing Settings", "default_scrap_warehouse"
		)
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
					"basic_rate": 0,
					"valuation_rate": 0,
				},
			)

		entry.insert(ignore_permissions=True)
		entry.submit()
		self.db_set("stock_entry", entry.name, update_modified=False)
