# Copyright (c) 2026, Happifoam and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt

class ProductionBatch(Document):
	def validate(self):
		self.calculate_cbm_and_variance()
		self.distribute_costs()
		self.validate_approvals()

	def on_submit(self):
		if self.approval_status != "Approved":
			frappe.throw("Cannot submit unless Approval Status is 'Approved'.")

	def calculate_cbm_and_variance(self):
		total_expected = 0.0
		total_actual = 0.0

		produced_map = {}
		for item in self.get("produced_items"):
			if item.item_code:
				if not item.cbm_per_unit:
					item.cbm_per_unit = frappe.db.get_value("Item", item.item_code, "custom_cbm") or 0.0
				item.total_cbm = flt(item.qty) * flt(item.cbm_per_unit)
				
				run_id = str(item.density_run_id)
				if run_id not in produced_map:
					produced_map[run_id] = 0.0
				produced_map[run_id] += item.total_cbm

		for run in self.get("density_runs"):
			run.expected_cbm = flt(run.runtime_minutes) * flt(run.output_rate)
			
			actual = produced_map.get(run.name, 0.0)
			if actual == 0.0:
				actual = produced_map.get(str(run.idx), 0.0)
				
			run.actual_cbm = actual
			run.variance_cbm = run.actual_cbm - run.expected_cbm
			
			if run.expected_cbm > 0:
				run.variance_percent = (run.variance_cbm / run.expected_cbm) * 100.0
			else:
				run.variance_percent = 0.0

			abs_var = abs(run.variance_percent)
			if abs_var <= 3.0:
				run.variance_flag = "Normal"
				run.requires_attention = 0
			elif abs_var <= 7.0:
				run.variance_flag = "Warning"
				run.requires_attention = 0
			else:
				run.variance_flag = "Critical"
				run.requires_attention = 1

			total_expected += run.expected_cbm
			total_actual += run.actual_cbm

		self.total_expected_cbm = total_expected
		self.total_actual_cbm = total_actual
		self.total_variance_cbm = total_actual - total_expected
		if total_expected > 0:
			self.total_variance_percent = (self.total_variance_cbm / total_expected) * 100.0
		else:
			self.total_variance_percent = 0.0

	def distribute_costs(self):
		labour = flt(self.labour_cost)
		power = flt(self.power_cost)
		overhead = flt(self.overhead_cost)
		self.total_production_cost = labour + power + overhead

		if self.total_expected_cbm > 0:
			for run in self.get("density_runs"):
				share_ratio = flt(run.expected_cbm) / self.total_expected_cbm
				run.cost_share = self.total_production_cost * share_ratio

	def validate_approvals(self):
		if self.approval_status == "Approved":
			roles = frappe.get_roles(frappe.session.user)
			if "System Manager" not in roles and "Approver" not in roles and frappe.session.user != "Administrator":
				frappe.throw("You do not have permission to Approve this Production Batch.")

			if not self.approved_by:
				self.approved_by = frappe.session.user

		if self.blockstore_status == "Confirmed":
			if self.approval_status != "Approved":
				frappe.throw("Cannot confirm Blockstore before the batch is Approved.")
			
			if not self.get("produced_items"):
				frappe.throw("Produced Items table cannot be empty for Blockstore confirmation.")
			
			if self.total_actual_cbm <= 0:
				frappe.throw("Total Actual CBM must be greater than zero for Blockstore confirmation.")

			if not self.confirmed_by:
				self.confirmed_by = frappe.session.user

			if not self.stock_entry_created:
				self.create_stock_entry()

	def create_stock_entry(self):
		if not self.get("produced_items"):
			return

		se = frappe.new_doc("Stock Entry")
		se.stock_entry_type = "Material Receipt"
		se.purpose = "Material Receipt"
		se.posting_date = self.date
		
		warehouse = frappe.db.get_value("Warehouse", {"warehouse_name": ["like", "%Block Store%"]})
		if not warehouse:
			warehouse = frappe.db.get_value("Warehouse", {"is_group": 0})
			
		se.to_warehouse = warehouse

		default_cost_center = frappe.db.get_value("Cost Center", {"is_group": 0})

		for item in self.get("produced_items"):
			se.append("items", {
				"item_code": item.item_code,
				"qty": item.qty,
				"uom": "Nos",
				"t_warehouse": warehouse,
				"cost_center": default_cost_center
			})

		se.insert(ignore_permissions=True)
		se.submit()

		self.stock_entry_created = 1
		frappe.msgprint(f"Stock Entry {se.name} created automatically.")
