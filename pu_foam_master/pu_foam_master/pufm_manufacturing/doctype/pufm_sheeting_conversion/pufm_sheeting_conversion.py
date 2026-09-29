# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

"""Pufm Sheeting Conversion — lightweight furniture-cut tracker.

Does NOT deduct source blocks from stock (that happens via Delivery Note).
Optional scrap is received into inventory via a Material Receipt Stock Entry
so Rebond can consume it with a clear Stock Ledger audit trail.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import cint, flt

from pu_foam_master.pufm_manufacturing.utils.approval_workflows import (
	assert_deletable_before_supervisor_approval,
)
from pu_foam_master.pufm_manufacturing.utils.density_bom import get_preferred_company
from pu_foam_master.pufm_manufacturing.utils.settings import get_cbm_factor, get_scrap_output_rate
from pu_foam_master.pufm_manufacturing.utils.stock_entry_valuation import apply_manual_rate


class PufmSheetingConversion(Document):
	def autoname(self):
		self.name = make_autoname(self.naming_series or "SH-CONV-.YYYY.-.####")

	def on_trash(self):
		assert_deletable_before_supervisor_approval(self)

	def validate(self):
		if not self.company:
			self.company = get_preferred_company()
		if not self.company:
			frappe.throw(_("Company is required."))
		if not self.processed_by:
			self.processed_by = frappe.session.user
		self._validate_job_order_type()
		if not self.sheeting_outputs:
			frappe.throw(_("Add at least one Sheeting Output row."))
		self._recalculate_output_cbm()

	def _validate_job_order_type(self):
		if not self.job_order:
			return
		order_type = frappe.db.get_value("Pufm Job Order", self.job_order, "order_type")
		if order_type and order_type != "Sheetings":
			frappe.throw(
				_("Job Order {0} is type {1}. Sheeting Conversion only accepts Sheetings Job Orders.").format(
					self.job_order, order_type
				)
			)

	def on_submit(self):
		self._create_scrap_material_receipt()
		self._sync_job_order_status("Completed")
		self._sync_job_order_operator(self.processed_by)

	def on_cancel(self):
		self._cancel_scrap_stock_entry()
		self._sync_job_order_status("Pending Slicing")
		self._sync_job_order_operator(None)

	def _recalculate_output_cbm(self):
		cbm_factor = get_cbm_factor() or 61023.74
		for row in self.get("sheeting_outputs") or []:
			if not row.source_block:
				frappe.throw(_("Row {0}: Source Block is required.").format(row.idx))
			length = flt(row.length_inches)
			width = flt(row.width_inches)
			thickness = flt(row.thickness_inches)
			qty = cint(row.quantity) or 0
			if length <= 0 or width <= 0 or thickness <= 0 or qty <= 0:
				row.calculated_cbm = 0
				continue
			row.calculated_cbm = flt((length * width * thickness * qty) / cbm_factor, 5)

	def _sync_job_order_status(self, status):
		if not self.job_order:
			return
		if not frappe.db.exists("Pufm Job Order", self.job_order):
			return
		from pu_foam_master.pufm_manufacturing.doctype.pufm_job_order.pufm_job_order import (
			sync_job_order_status,
		)

		sync_job_order_status(self.job_order, status)

	def _sync_job_order_operator(self, user):
		if not self.job_order:
			return
		if not frappe.db.exists("Pufm Job Order", self.job_order):
			return
		frappe.db.set_value("Pufm Job Order", self.job_order, "sliced_by", user)

	def _create_scrap_material_receipt(self):
		if flt(self.scrap_weight_kg) <= 0:
			return

		settings = frappe.get_single("Pufm Manufacturing Settings")
		scrap_item = getattr(settings, "scrap_item", None)
		scrap_warehouse = getattr(settings, "default_scrap_warehouse", None)
		scrap_output_rate = get_scrap_output_rate(settings)
		if not scrap_item or not scrap_warehouse:
			frappe.throw(
				_(
					"Please set Scrap Item and Default Scrap Warehouse in Pufm Manufacturing Settings."
				)
			)

		scrap_wh_company = frappe.db.get_value("Warehouse", scrap_warehouse, "company")
		if scrap_wh_company and scrap_wh_company != self.company:
			frappe.throw(
				_("Default Scrap Warehouse {0} belongs to {1}, not {2}.").format(
					scrap_warehouse, scrap_wh_company, self.company
				)
			)

		scrap_doc = frappe.get_cached_doc("Item", scrap_item)
		uom = scrap_doc.stock_uom or "Kg"

		entry = frappe.new_doc("Stock Entry")
		entry.company = self.company
		entry.stock_entry_type = "Material Receipt"
		entry.purpose = "Material Receipt"
		entry.posting_date = self.posting_date
		entry.set_posting_time = 1
		entry.remarks = f"Scrap generated from Sheeting Conversion: {self.name}"
		scrap_row = {
			"item_code": scrap_item,
			"qty": flt(self.scrap_weight_kg),
			"t_warehouse": scrap_warehouse,
			"uom": uom,
			"stock_uom": uom,
			"conversion_factor": 1,
		}
		apply_manual_rate(scrap_row, scrap_output_rate)
		entry.append("items", scrap_row)
		entry.insert(ignore_permissions=True)
		entry.submit()
		self.db_set("scrap_stock_entry", entry.name, update_modified=False)

	def _cancel_scrap_stock_entry(self):
		if not self.scrap_stock_entry:
			return
		if not frappe.db.exists("Stock Entry", self.scrap_stock_entry):
			return
		se = frappe.get_doc("Stock Entry", self.scrap_stock_entry)
		if se.docstatus == 1:
			se.cancel()
