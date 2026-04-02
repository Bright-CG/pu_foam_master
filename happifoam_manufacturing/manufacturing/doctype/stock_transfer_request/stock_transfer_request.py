# Copyright (c) 2026, Happifoam and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt

class StockTransferRequest(Document):
	def validate(self):
		for row in self.get("items"):
			actual_qty = frappe.db.get_value(
				"Bin",
				{"item_code": row.item_code, "warehouse": self.from_warehouse},
				"actual_qty"
			) or 0.0

			row.available_qty = actual_qty

			if flt(row.qty) > flt(actual_qty):
				frappe.throw(f"Not enough stock for {row.item_code} in {self.from_warehouse}. Available: {actual_qty}, Requested: {row.qty}")

		if self.status == "Approved" and not self.approved_by:
			frappe.throw("Approved By is required. Save as Pending Approval if not authorized.")

	def on_submit(self):
		if self.status != "Approved":
			frappe.throw("Status must be 'Approved' before submission.")

		self.db_set("status", "In Transit")
		
		# Create transfer entry
		se_created = self.create_transfer_entry()
		self.db_set("stock_entry", se_created)

		self.db_set("status", "Completed")

	def create_transfer_entry(self):
		se = frappe.new_doc("Stock Entry")
		se.stock_entry_type = "Material Transfer"
		se.purpose = "Material Transfer"
		
		for row in self.get("items"):
			se.append("items", {
				"item_code": row.item_code,
				"qty": row.qty,
				"s_warehouse": self.from_warehouse,
				"t_warehouse": self.to_warehouse
			})

		se.insert(ignore_permissions=True)
		se.submit()

		frappe.msgprint(f"Stock Entry (Transfer) {se.name} created and submitted successfully.")
		return se.name
