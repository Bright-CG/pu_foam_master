# Copyright (c) 2026, PU Foam Master and contributors
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

# Core fields required for day-to-day virgin pour + mattress + rebate ops
_REQUIRED_CORE_FIELDS = (
	("default_company", "Default Company"),
	("default_wip_warehouse", "Default WIP Warehouse"),
	("default_fg_warehouse", "Default FG Warehouse"),
	("default_scrap_warehouse", "Default Scrap Warehouse"),
	("default_raw_material_warehouse", "Default Raw Material Warehouse"),
	("scrap_item", "Default Scrap Item"),
	("default_tape_edge_item", "Default Tape Edge Item"),
	("default_pvc_nylon_item", "Default PVC/Nylon Item"),
	("default_thread_item", "Default Thread Item"),
	("rebate_expense_account", "Rebate Expense Account"),
	("labour_absorption_account", "Labour Absorption Account"),
	("conversion_absorption_account", "Conversion Absorption Account"),
	("quilting_absorption_account", "Quilting Absorption Account"),
)


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
		# Fresh install / migrate creates an empty Single — do not block that bootstrap save.
		if self._is_bootstrap_context():
			return
		self._validate_required_operational_fields()
		self._validate_warehouse_companies()
		self._validate_rebate_account_type()
		self._validate_mattress_labour_absorption()
		self._validate_scrap_rates()

	def _is_bootstrap_context(self):
		"""True during install/migrate, or when Settings has never been configured yet."""
		if (
			getattr(frappe.flags, "in_install", None)
			or getattr(frappe.flags, "in_migrate", False)
			or getattr(frappe.flags, "in_patch", False)
		):
			return True
		# Allow first empty Single save (init_singles / Desk open before setup)
		return not any(self.get(field) for field, _label in _REQUIRED_CORE_FIELDS)

	def _validate_required_operational_fields(self):
		missing = [label for field, label in _REQUIRED_CORE_FIELDS if not self.get(field)]
		if missing:
			frappe.throw(
				_("Complete Pufm Manufacturing Settings before factory use. Missing: {0}").format(
					", ".join(missing)
				),
				frappe.ValidationError,
			)

	def _validate_warehouse_companies(self):
		company = self.default_company
		if not company:
			return
		for field, label in (
			("default_wip_warehouse", "Default WIP Warehouse"),
			("default_fg_warehouse", "Default FG Warehouse"),
			("default_scrap_warehouse", "Default Scrap Warehouse"),
			("default_raw_material_warehouse", "Default Raw Material Warehouse"),
		):
			wh = self.get(field)
			if not wh:
				continue
			wh_company = frappe.db.get_value("Warehouse", wh, "company")
			if wh_company and wh_company != company:
				frappe.throw(
					_("{0} ({1}) belongs to company {2}, not {3}.").format(
						label, wh, wh_company, company
					),
					frappe.ValidationError,
				)

	def _validate_rebate_account_type(self):
		account = self.rebate_expense_account
		if not account:
			return
		root_type = frappe.db.get_value("Account", account, "root_type")
		if root_type and root_type != "Expense":
			frappe.throw(
				_("Rebate Expense Account must be an Expense account."),
				frappe.ValidationError,
			)

	def _validate_mattress_labour_absorption(self):
		if flt(self.mattress_labour_per_pc) > 0 and not self.mattress_labour_absorption_account:
			frappe.throw(
				_("Set Mattress Labour Absorption Account when Labor per Mattress is greater than zero."),
				frappe.ValidationError,
			)
		account = self.mattress_labour_absorption_account
		if not account:
			return
		root_type = frappe.db.get_value("Account", account, "root_type")
		if root_type and root_type != "Expense":
			frappe.throw(
				_("Mattress Labour Absorption Account must be an Expense account."),
				frappe.ValidationError,
			)

	def _validate_scrap_rates(self):
		if flt(self.scrap_output_rate) < 0:
			frappe.throw(_("Scrap Output Rate cannot be negative."), frappe.ValidationError)
		if flt(self.scrap_input_rate) < 0:
			frappe.throw(_("Scrap Input Rate cannot be negative."), frappe.ValidationError)


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
