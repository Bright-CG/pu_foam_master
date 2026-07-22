import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class ScrapCostingCalculator(Document):
	def before_insert(self):
		if not self.scrap_item:
			self.scrap_item = frappe.db.get_single_value(
				"Pufm Manufacturing Settings", "scrap_item"
			)

	def validate(self):
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
		capacity = flt(self.container_capacity_kg) or 20000
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

		warehouse = frappe.db.get_single_value(
			"Pufm Manufacturing Settings", "default_scrap_warehouse"
		)
		if not warehouse:
			frappe.throw(_("Please set Default Scrap Warehouse in Pufm Manufacturing Settings."))

		qty = flt(
			frappe.db.get_value(
				"Bin",
				{"item_code": self.scrap_item, "warehouse": warehouse},
				"actual_qty",
			)
		)

		reconciliation = frappe.new_doc("Stock Reconciliation")
		reconciliation.purpose = "Stock Reconciliation"
		reconciliation.company = frappe.defaults.get_user_default("Company")
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
