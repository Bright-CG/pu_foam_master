import frappe
from frappe.model.document import Document
from frappe.utils import flt


class QuiltingRecord(Document):
	def validate(self):
		self._validate_inputs()

	def before_submit(self):
		self.total_production_cost = self._calculate_total_cost()

	def on_submit(self):
		stock_entry = self._create_repack_stock_entry()
		self.db_set("stock_entry", stock_entry.name, update_modified=False)

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

	def _calculate_total_cost(self):
		settings = frappe.get_single("Pufm Manufacturing Settings")
		overhead_per_m = (
			flt(settings.gum_cost_per_m)
			+ flt(settings.thread_cost_per_m_quilt)
			+ flt(settings.non_woven_cost_per_m)
			+ flt(settings.quilting_labor_per_m)
		)
		overhead_cost = overhead_per_m * flt(self.output_qty_meters)

		input_cost = 0
		for row in self.inputs:
			valuation_rate = _get_batch_valuation_rate(row.batch_no)
			input_cost += flt(row.qty) * valuation_rate

		return input_cost + overhead_cost

	def _create_repack_stock_entry(self):
		total_cost = flt(self.total_production_cost)
		unit_rate = total_cost / flt(self.output_qty_meters) if flt(self.output_qty_meters) else 0

		entry = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Repack",
				"posting_date": self.posting_date,
				"set_posting_time": 1,
				"items": [],
			}
		)

		for row in self.inputs:
			item_doc = frappe.get_cached_doc("Item", row.item_code)
			valuation_rate = _get_batch_valuation_rate(row.batch_no)
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
					"valuation_rate": valuation_rate,
				},
			)

		finished_doc = frappe.get_cached_doc("Item", self.finished_item)
		entry.append(
			"items",
			{
				"item_code": self.finished_item,
				"t_warehouse": self.target_warehouse,
				"qty": flt(self.output_qty_meters),
				"uom": finished_doc.stock_uom or "Meter",
				"stock_uom": finished_doc.stock_uom or "Meter",
				"conversion_factor": 1,
				"basic_rate": unit_rate,
				"valuation_rate": unit_rate,
			},
		)

		entry.insert(ignore_permissions=True)
		entry.submit()
		return entry


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
