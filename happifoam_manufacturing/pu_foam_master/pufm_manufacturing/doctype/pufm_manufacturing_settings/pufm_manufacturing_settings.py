# Copyright (c) 2026, Happifoam and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


FACTORY_FORMULA_DEFAULTS = {
	"cbm_factor": 61023.74,
	"inches_per_meter": 39.37,
	"inches_to_meters_factor": 0.0254,
	"default_fabric_width_inches": 84.0,
	"fabric_panel_faces": 2,
	"fabric_side_panels_factor": 2,
	"tape_edge_perimeter_multiplier": 4.0,
	"tape_edge_waste_percentage": 0,
	"pvc_nylon_divisor": 1550,
	"pvc_nylon_faces": 1,
	"thread_qty_per_mattress": 1.0,
	"label_qty_per_mattress": 1.0,
	"scrap_default_container_capacity_kg": 20000,
	"scrap_default_process_loss_ngn": 3000000,
}


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


@frappe.whitelist()
def reset_formula_defaults():
	"""Restore consumption formula factors to factory defaults (not rates/accounts)."""
	roles = set(frappe.get_roles())
	if not roles.intersection({"System Manager", "PUFM Manager"}):
		frappe.throw(_("Only System Manager or PUFM Manager can reset formula defaults."))

	doc = frappe.get_single("Pufm Manufacturing Settings")
	for fieldname, value in FACTORY_FORMULA_DEFAULTS.items():
		doc.set(fieldname, value)
	doc.save(ignore_permissions=True)
	return True
