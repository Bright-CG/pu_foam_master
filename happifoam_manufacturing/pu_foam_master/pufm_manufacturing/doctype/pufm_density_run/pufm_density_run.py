import frappe
from frappe.model.document import Document
from frappe.utils import flt


class PufmDensityRun(Document):
	def validate(self):
		self.calculate_expected_and_actual()

	def calculate_expected_and_actual(self):
		self.expected_cbm = 0
		self.actual_cbm = 0
		self.variance_percent = 0

		if self.density_config:
			output_rate = flt(
				frappe.db.get_value("Density Configuration", self.density_config, "output_rate_m3_per_min")
			)
			self.expected_cbm = flt(self.minutes_run) * output_rate

		for row in self.get("produced_blocks_table") or []:
			if row.block_item:
				row.unit_cbm = flt(frappe.db.get_value("Item", row.block_item, "cbm_value"))
			else:
				row.unit_cbm = 0
			row.total_cbm = flt(row.quantity) * flt(row.unit_cbm)
			self.actual_cbm += row.total_cbm

		if self.expected_cbm:
			self.variance_percent = ((self.actual_cbm - self.expected_cbm) / self.expected_cbm) * 100


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

	return frappe.db.sql(
		"""
		SELECT item_code, item_name
		FROM `tabItem`
		WHERE variant_of = %(variant_of)s
			AND disabled = 0
			AND ({searchfield} LIKE %(txt)s OR item_name LIKE %(txt)s)
		ORDER BY item_code
		LIMIT %(start)s, %(page_len)s
		""".format(searchfield=search_field),
		{
			"variant_of": density_name,
			"txt": f"%{txt}%",
			"start": start,
			"page_len": page_len,
		},
	)
