# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

from pu_foam_master.pufm_manufacturing.utils.settings import (
	calculate_cbm,
	get_scrap_input_rate,
	get_settings,
	require_absorption_accounts,
)
from pu_foam_master.pufm_manufacturing.utils.stock_entry_valuation import (
	apply_manual_rate,
	finalize_pufm_stock_entry_balance,
	get_stock_valuation_rate,
)


class ReboundProductionEntry(Document):
	def validate(self):
		if not self.company:
			frappe.throw(_("Company is required."))
		if not self.scrap_warehouse:
			frappe.throw(_("Scrap Source Warehouse is required."))
		if not self.mdi_warehouse:
			frappe.throw(_("MDI Source Warehouse is required."))
		if not self.target_warehouse:
			frappe.throw(_("Target (FG) Warehouse is required."))
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

		if not scrap_item:
			frappe.throw(_("Please set Default Scrap Item in Pufm Manufacturing Settings."))
		if not mdi_item:
			frappe.throw(_("Please set Default MDI/Binder Item in Pufm Manufacturing Settings."))

		entry = frappe.new_doc("Stock Entry")
		entry.company = self.company
		entry.stock_entry_type = "Manufacture"
		entry.purpose = "Manufacture"
		entry.posting_date = self.posting_date
		entry.set_posting_time = 1
		entry.from_bom = 0

		# Scrap always at Settings Scrap Input Rate (zero is valid).
		# MDI keeps warehouse valuation so binder cost is not overwritten.
		scrap_input_rate = get_scrap_input_rate(settings)
		mdi_batch = _pick_batch_with_stock(mdi_item, self.mdi_warehouse, self.actual_mdi_kg)
		mdi_rate = get_stock_valuation_rate(
			mdi_item, warehouse=self.mdi_warehouse, batch_no=mdi_batch
		)

		scrap_row = {
			"item_code": scrap_item,
			"qty": flt(self.actual_scrap_kg),
			"s_warehouse": self.scrap_warehouse,
			"use_serial_batch_fields": 1,
		}
		apply_manual_rate(scrap_row, scrap_input_rate)

		mdi_row = {
			"item_code": mdi_item,
			"qty": flt(self.actual_mdi_kg),
			"s_warehouse": self.mdi_warehouse,
			"use_serial_batch_fields": 1,
		}
		apply_manual_rate(mdi_row, mdi_rate)
		if mdi_batch:
			mdi_row["batch_no"] = mdi_batch

		fg_row = {
			"item_code": self.target_block_item,
			"qty": flt(self.quantity_produced),
			"t_warehouse": self.target_warehouse,
			"is_finished_item": 1,
			"use_serial_batch_fields": 1,
		}
		if cint(frappe.db.get_value("Item", self.target_block_item, "has_batch_no")):
			fg_row["batch_no"] = self._ensure_output_batch(self.target_block_item)
		apply_manual_rate(fg_row, 0)

		entry.append("items", scrap_row)
		entry.append("items", mdi_row)
		entry.append("items", fg_row)

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

		finalize_pufm_stock_entry_balance(
			entry, context="Rebound Production Entry {0}".format(self.name)
		)

		entry.insert(ignore_permissions=True)
		entry.submit()
		self.db_set("stock_entry", entry.name, update_modified=False)

	def _ensure_output_batch(self, item_code):
		batch_id = f"{self.name}-{item_code}"
		if not frappe.db.exists("Batch", batch_id):
			new_batch = frappe.new_doc("Batch")
			new_batch.batch_id = batch_id
			new_batch.item = item_code
			new_batch.reference_doctype = "Rebound Production Entry"
			new_batch.reference_name = self.name
			new_batch.insert(ignore_permissions=True)
		return batch_id


def _pick_batch_with_stock(item_code, warehouse, required_qty):
	"""Pick a batch with available qty when the item is batch-tracked."""
	if not cint(frappe.db.get_value("Item", item_code, "has_batch_no")):
		return None

	from erpnext.controllers.queries import get_batch_no

	rows = get_batch_no(
		"Batch",
		"",
		"name",
		0,
		20,
		{"item_code": item_code, "warehouse": warehouse},
	)
	if not rows:
		frappe.throw(
			_("No batch stock found for {0} in {1}.").format(item_code, warehouse)
		)

	# Prefer a batch that can cover required qty; else first available
	required = flt(required_qty)
	for row in rows:
		batch_name = row[0]
		batch_qty = flt(row[1]) if len(row) > 1 else 0
		if batch_qty >= required:
			return batch_name
	return rows[0][0]


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
