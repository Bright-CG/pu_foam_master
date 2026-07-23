import frappe
from frappe.model.document import Document
from frappe.utils import flt


class PufmDensityRun(Document):
	def validate(self):
		self.calculate_expected_and_actual()

	def before_save(self):
		# Enforce Expected CBM on the server before commit
		if self.density_config and self.minutes_run:
			output_rate = frappe.db.get_value(
				"Density Configuration", self.density_config, "output_rate_m3_per_min"
			)
			self.expected_cbm = flt(flt(self.minutes_run) * flt(output_rate), 5)
			self.output_rate_m3_per_min = flt(output_rate, 5)
		self._apply_variance_percentage()

	def on_update(self):
		self.update_parent_batch()

	def on_trash(self):
		self.update_parent_batch()

	def update_parent_batch(self):
		if self.parent_batch:
			parent_doc = frappe.get_doc("Pufm Production Batch", self.parent_batch)
			parent_doc.update_totals()

	def calculate_expected_and_actual(self):
		self.expected_cbm = 0
		self.actual_cbm = 0
		self.variance_percent = 0
		self.variance_percentage = 0

		if self.density_config:
			output_rate = flt(
				frappe.db.get_value(
					"Density Configuration", self.density_config, "output_rate_m3_per_min"
				)
			)
			self.output_rate_m3_per_min = flt(output_rate, 5)
			self.expected_cbm = flt(flt(self.minutes_run) * output_rate, 5)

		self.actual_cbm = 0
		for row in self.get("produced_blocks_table") or []:
			if row.block_item:
				row.unit_cbm = flt(frappe.db.get_value("Item", row.block_item, "custom_cbm_value"))
			else:
				row.unit_cbm = 0
			row.total_cbm = flt(flt(row.quantity) * flt(row.unit_cbm), 5)
			self.actual_cbm = flt(self.actual_cbm + flt(row.total_cbm), 5)

		self._apply_variance_percentage()

	def _apply_variance_percentage(self):
		"""Variance % = ((Actual CBM - Expected CBM) / Expected CBM) * 100."""
		expected = flt(self.expected_cbm)
		actual = flt(self.actual_cbm)
		if expected:
			variance = flt(((actual - expected) / expected) * 100, 5)
		else:
			variance = 0.0
		self.variance_percentage = variance
		# Keep legacy Percent field in sync for older forms/reports
		self.variance_percent = variance


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_filtered_block_items(doctype, txt, searchfield, start, page_len, filters):
	density_config = (filters or {}).get("density_config")
	if not density_config:
		return []

	density_name = frappe.db.get_value("Density Configuration", density_config, "density_name")
	if not density_name:
		return []

	search_field = "item_code" if searchfield not in {"item_code", "item_name"} else searchfield
	density_name = (density_name or "").strip()
	if not density_name:
		return []

	return frappe.db.sql(
		"""
		SELECT name, item_name
		FROM `tabItem`
		WHERE (
				item_code LIKE %(new_pattern)s
				OR item_name LIKE %(new_pattern)s
				OR variant_of = %(density_name)s
				OR item_code LIKE %(legacy_pattern)s
			)
			AND disabled = 0
			AND ({searchfield} LIKE %(txt)s OR item_name LIKE %(txt)s)
		ORDER BY item_code
		LIMIT %(start)s, %(page_len)s
		""".format(searchfield=search_field),
		{
			"new_pattern": f"{density_name}-% Block",
			"legacy_pattern": f"{density_name} by % Block",
			"density_name": density_name,
			"txt": f"%{txt}%",
			"start": start,
			"page_len": page_len,
		},
	)
