# Copyright (c) 2026, Happifoam and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class PufmManufacturingSettings(Document):
	def validate(self):
		self.conversion_rate_per_cbm = (
			flt(self.conversion_glue_cost_per_cbm)
			+ flt(self.conversion_power_cost_per_cbm)
			+ flt(self.conversion_labor_cost_per_cbm)
		)
		self.total_quilting_rate_per_m = (
			flt(self.gum_cost_per_m)
			+ flt(self.thread_cost_per_m_quilt)
			+ flt(self.non_woven_cost_per_m)
			+ flt(self.quilting_labor_per_m)
		)
