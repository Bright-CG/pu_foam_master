import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from pu_foam_master.pufm_manufacturing.utils.density_bom import get_preferred_company
from pu_foam_master.pufm_manufacturing.utils.settings import get_formula_factor


class ScrapCostingCalculator(Document):
	def before_insert(self):
		if not self.company:
			self.company = get_preferred_company()
		if not self.scrap_item:
			self.scrap_item = frappe.db.get_single_value(
				"Pufm Manufacturing Settings", "scrap_item"
			)
		if not flt(self.container_capacity_kg):
			self.container_capacity_kg = get_formula_factor("scrap_default_container_capacity_kg")
		if self.process_loss_contingency_ngn in (None, ""):
			self.process_loss_contingency_ngn = get_formula_factor("scrap_default_process_loss_ngn")

	def validate(self):
		if not self.company:
			self.company = get_preferred_company()
		if not self.company:
			frappe.throw(_("Company is required."))
		self._calculate_cost_per_kg()

	def on_submit(self):
		if self.stock_reconciliation:
			frappe.throw(_("Stock Reconciliation already linked to this document."))
		self._create_stock_reconciliation()

	def on_cancel(self):
		if self.stock_reconciliation:
			doc = frappe.get_doc("Stock Reconciliation", self.stock_reconciliation)
			if doc.docstatus == 1:
				doc.cancel()

	def _calculate_cost_per_kg(self):
		capacity = flt(self.container_capacity_kg) or get_formula_factor(
			"scrap_default_container_capacity_kg"
		)
		total_cost = (
			flt(self.shipping_cost_ngn)
			+ flt(self.local_logistics_ngn)
			+ flt(self.process_loss_contingency_ngn)
		)
		if capacity <= 0:
			frappe.throw(_("Container Capacity must be greater than zero."))
		self.calculated_cost_per_kg = total_cost / capacity

	def _create_stock_reconciliation(self):
		if not self.scrap_item:
			frappe.throw(_("Scrap Item is required."))
		if not self.company:
			frappe.throw(_("Company is required."))

		warehouse = frappe.db.get_single_value(
			"Pufm Manufacturing Settings", "default_scrap_warehouse"
		)
		if not warehouse:
			frappe.throw(_("Please set Default Scrap Warehouse in Pufm Manufacturing Settings."))

		wh_company = frappe.db.get_value("Warehouse", warehouse, "company")
		if wh_company and wh_company != self.company:
			frappe.throw(
				_("Scrap Warehouse {0} belongs to {1}, not {2}.").format(
					warehouse, wh_company, self.company
				)
			)

		qty = flt(
			frappe.db.get_value(
				"Bin",
				{"item_code": self.scrap_item, "warehouse": warehouse},
				"actual_qty",
			)
		)

		reconciliation = frappe.new_doc("Stock Reconciliation")
		reconciliation.purpose = "Stock Reconciliation"
		reconciliation.company = self.company
		reconciliation.posting_date = self.posting_date
		reconciliation.set_posting_time = 1
		reconciliation.append(
			"items",
			{
				"item_code": self.scrap_item,
				"warehouse": warehouse,
				"qty": qty,
				"valuation_rate": flt(self.calculated_cost_per_kg),
			},
		)
		reconciliation.insert(ignore_permissions=True)
		reconciliation.submit()
		self.db_set("stock_reconciliation", reconciliation.name, update_modified=False)
