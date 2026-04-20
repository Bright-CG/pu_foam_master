import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import flt


class PufmProductionBatch(Document):
	def autoname(self):
		self.name = make_autoname(self.naming_series or "PB-.YYYY.-.MM.-.###")
		self.batch_id = self.name

	def validate(self):
		if self.name:
			self.batch_id = self.name

	def before_save(self):
		if self.is_new():
			return

		previous_state = frappe.db.get_value(self.doctype, self.name, "workflow_state")
		if previous_state == self.workflow_state:
			return

		if self.workflow_state == "Pending Store Confirmation":
			self.create_scrap_stock_entry()
		elif self.workflow_state == "Completed":
			self.create_chemical_consumption_entry()
			self.create_fg_receipt_entry()

	def _get_linked_runs(self):
		return frappe.get_all(
			"Pufm Density Run",
			filters={"parent_batch": self.name},
			fields=["name", "density_config", "scrap_weight_kg", "actual_cbm", "expected_cbm"],
		)

	def update_totals(self):
		"""Aggregates totals from all linked Density Runs."""
		runs = self._get_linked_runs()
		
		# Reset totals
		self.total_actual_cbm = 0
		self.total_scrap_weight = 0
		self.total_produced_qty = 0
		
		run_names = [run.name for run in runs]
		if not run_names:
			self.save(ignore_permissions=True)
			return

		# Sum basics from Runs
		for run in runs:
			self.total_actual_cbm += flt(run.actual_cbm)
			self.total_scrap_weight += flt(run.scrap_weight_kg)

		# Sum Produced Blocks quantity across all runs
		produced_blocks = frappe.get_all(
			"Pufm Produced Block",
			filters={"parent": ["in", run_names], "parenttype": "Pufm Density Run"},
			fields=["quantity"]
		)
		self.total_produced_qty = sum(flt(b.quantity) for b in produced_blocks)

		self.save(ignore_permissions=True)
		frappe.db.commit()

	def _get_settings(self):
		return frappe.get_single("Pufm Manufacturing Settings")

	def create_scrap_stock_entry(self):
		if self.scrap_stock_entry:
			return

		runs = self._get_linked_runs()
		total_scrap = sum(flt(run.scrap_weight_kg) for run in runs)
		if total_scrap <= 0:
			return

		settings = self._get_settings()
		scrap_warehouse = settings.default_scrap_warehouse
		if not scrap_warehouse:
			frappe.throw("Set Default Scrap Warehouse in Pufm Manufacturing Settings.")

		scrap_item = frappe.db.get_single_value("Stock Settings", "scrap_item")
		if not scrap_item:
			frappe.throw("Set Scrap Item in Stock Settings.")

		entry = frappe.new_doc("Stock Entry")
		entry.stock_entry_type = "Material Receipt"
		entry.posting_date = self.posting_date
		entry.append(
			"items",
			{
				"item_code": scrap_item,
				"qty": total_scrap,
				"t_warehouse": scrap_warehouse,
			},
		)
		entry.insert(ignore_permissions=True)
		entry.submit()
		self.scrap_stock_entry = entry.name

	def create_chemical_consumption_entry(self):
		if self.chemical_consumption_entry:
			return

		runs = self._get_linked_runs()
		consumption_map = {}
		for run in runs:
			basis_cbm = flt(run.actual_cbm) or flt(run.expected_cbm)
			if basis_cbm <= 0 or not run.density_config:
				continue

			input_rows = frappe.get_all(
				"Production Inputs",
				filters={"parent": run.density_config, "parenttype": "Density Configuration"},
				fields=["item_code", "qty_per_m3"],
			)
			for row in input_rows:
				if not row.item_code:
					continue
				consumption_map[row.item_code] = consumption_map.get(row.item_code, 0) + (
					flt(row.qty_per_m3) * basis_cbm
				)

		if not consumption_map:
			return

		settings = self._get_settings()
		wip_warehouse = settings.default_wip_warehouse
		if not wip_warehouse:
			frappe.throw("Set Default WIP Warehouse in Pufm Manufacturing Settings.")

		entry = frappe.new_doc("Stock Entry")
		entry.stock_entry_type = "Material Issue"
		entry.posting_date = self.posting_date
		for item_code, qty in consumption_map.items():
			if qty <= 0:
				continue
			entry.append(
				"items",
				{
					"item_code": item_code,
					"qty": qty,
					"s_warehouse": wip_warehouse,
				},
			)

		if not entry.get("items"):
			return

		entry.insert(ignore_permissions=True)
		entry.submit()
		self.chemical_consumption_entry = entry.name

	def create_fg_receipt_entry(self):
		if self.fg_receipt_entry:
			return

		run_names = frappe.get_all("Pufm Density Run", filters={"parent_batch": self.name}, pluck="name")
		if not run_names:
			return

		fg_map = {}
		for run_name in run_names:
			rows = frappe.get_all(
				"Pufm Produced Block",
				filters={"parent": run_name, "parenttype": "Pufm Density Run"},
				fields=["block_item", "quantity"],
			)
			for row in rows:
				if not row.block_item:
					continue
				fg_map[row.block_item] = fg_map.get(row.block_item, 0) + flt(row.quantity)

		if not fg_map:
			return

		settings = self._get_settings()
		fg_warehouse = settings.default_fg_warehouse
		if not fg_warehouse:
			frappe.throw("Set Default FG Warehouse in Pufm Manufacturing Settings.")

		entry = frappe.new_doc("Stock Entry")
		entry.stock_entry_type = "Material Receipt"
		entry.posting_date = self.posting_date
		for item_code, qty in fg_map.items():
			if qty <= 0:
				continue
			entry.append(
				"items",
				{
					"item_code": item_code,
					"qty": qty,
					"t_warehouse": fg_warehouse,
				},
			)

		if not entry.get("items"):
			return

		entry.insert(ignore_permissions=True)
		entry.submit()
		self.fg_receipt_entry = entry.name
