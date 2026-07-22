import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from pu_foam_master.pufm_manufacturing.utils.settings import (
	calculate_cbm,
	get_settings,
	require_absorption_accounts,
)


class ReboundProductionEntry(Document):
	def validate(self):
		self._calculate_values()
		self._validate_inputs()

	def on_submit(self):
		self._create_manufacture_stock_entry()

	def on_cancel(self):
		if self.stock_entry:
			se = frappe.get_doc("Stock Entry", self.stock_entry)
			if se.docstatus == 1:
				se.cancel()

	def _calculate_values(self):
		config = frappe.get_cached_doc("Rebound Configuration", self.rebound_configuration)

		self.total_volume_cbm = calculate_cbm(
			self.length_inches,
			self.width_inches,
			self.height_inches,
			self.quantity_produced,
		)
		self.expected_scrap_kg = flt(config.scrap_kg_per_cbm) * flt(self.total_volume_cbm)
		self.expected_mdi_kg = flt(config.mdi_kg_per_cbm) * flt(self.total_volume_cbm)

		if not flt(self.actual_scrap_kg):
			self.actual_scrap_kg = self.expected_scrap_kg
		if not flt(self.actual_mdi_kg):
			self.actual_mdi_kg = self.expected_mdi_kg

		settings = get_settings()
		self.total_hours = (
			flt(config.standard_cycle_time_mins) * flt(self.quantity_produced)
		) / 60

		exchange_rate = flt(settings.rebound_exchange_rate)
		self.power_cost_ngn = self.total_hours * flt(settings.power_cost_usd_per_hour) * exchange_rate
		self.diesel_cost_ngn = self.total_hours * flt(settings.diesel_cost_usd_per_hour) * exchange_rate
		self.labour_cost_ngn = self.total_hours * flt(settings.labour_cost_usd_per_hour) * exchange_rate
		self.depreciation_cost_ngn = (
			self.total_hours * flt(settings.depreciation_cost_usd_per_hour) * exchange_rate
		)

	def _validate_inputs(self):
		if flt(self.quantity_produced) <= 0:
			frappe.throw(_("Quantity Produced must be greater than zero."))
		if flt(self.actual_scrap_kg) <= 0:
			frappe.throw(_("Actual Scrap (kg) must be greater than zero."))
		if flt(self.actual_mdi_kg) <= 0:
			frappe.throw(_("Actual MDI (kg) must be greater than zero."))

	def _create_manufacture_stock_entry(self):
		settings = require_absorption_accounts()
		scrap_item = settings.scrap_item
		mdi_item = settings.mdi_item
		scrap_warehouse = settings.default_scrap_warehouse
		wip_warehouse = settings.default_wip_warehouse
		fg_warehouse = settings.default_fg_warehouse

		if not scrap_item:
			frappe.throw(_("Please set Scrap Item in Pufm Manufacturing Settings."))
		if not mdi_item:
			frappe.throw(_("Please set MDI Item in Pufm Manufacturing Settings."))
		if not scrap_warehouse:
			frappe.throw(_("Please set Default Scrap Warehouse in Pufm Manufacturing Settings."))
		if not wip_warehouse:
			frappe.throw(_("Please set Default WIP Warehouse in Pufm Manufacturing Settings."))
		if not fg_warehouse:
			frappe.throw(_("Please set Default FG Warehouse in Pufm Manufacturing Settings."))

		entry = frappe.new_doc("Stock Entry")
		entry.stock_entry_type = "Manufacture"
		entry.company = frappe.defaults.get_user_default("Company")
		entry.posting_date = self.posting_date
		entry.set_posting_time = 1
		entry.from_bom = 0

		entry.append(
			"items",
			{
				"item_code": scrap_item,
				"qty": flt(self.actual_scrap_kg),
				"s_warehouse": scrap_warehouse,
				"allow_zero_valuation_rate": 1,
			},
		)
		entry.append(
			"items",
			{
				"item_code": mdi_item,
				"qty": flt(self.actual_mdi_kg),
				"s_warehouse": wip_warehouse,
				"allow_zero_valuation_rate": 1,
			},
		)
		entry.append(
			"items",
			{
				"item_code": self.target_block_item,
				"qty": flt(self.quantity_produced),
				"t_warehouse": fg_warehouse,
				"is_finished_item": 1,
			},
		)

		for description, amount, account in (
			("Power Absorption", self.power_cost_ngn, settings.power_absorption_account),
			("Diesel Absorption", self.diesel_cost_ngn, settings.diesel_absorption_account),
			("Labour Absorption", self.labour_cost_ngn, settings.labour_absorption_account),
			(
				"Depreciation Absorption",
				self.depreciation_cost_ngn,
				settings.depreciation_absorption_account,
			),
		):
			if flt(amount) <= 0:
				continue
			entry.append(
				"additional_costs",
				{
					"description": description,
					"amount": flt(amount),
					"expense_account": account,
				},
			)

		entry.insert(ignore_permissions=True)
		entry.submit()
		self.db_set("stock_entry", entry.name, update_modified=False)


@frappe.whitelist()
def get_item_dimensions(item_code):
	if not item_code:
		return {}

	return frappe.db.get_value(
		"Item",
		item_code,
		["custom_length", "custom_width", "custom_height"],
		as_dict=True,
	) or {}
