# Copyright (c) 2026, Happifoam and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class DensityConfiguration(Document):
	def validate(self):
		if not self.block_sizes:
			frappe.throw("You must add at least one block size.")
		if self.density_value <= 0:
			frappe.throw("Density must be greater than zero.")
			
		# Duplicate Prevention: Ensure a density name cannot be created twice
		if frappe.db.exists("Density Configuration", {"density_name": self.density_name, "name": ["!=", self.name]}):
			frappe.throw(f"A Density Configuration with the name '{self.density_name}' already exists.")

	def on_update(self):
		if self.auto_generate_items and not self.items_generated:
			self.generate_items()
			self.db_set("items_generated", 1)

	def generate_items(self):
		# Ensure Item Group exists
		if not frappe.db.exists("Item Group", "Foam Blocks"):
			ig = frappe.get_doc({
				"doctype": "Item Group",
				"item_group_name": "Foam Blocks",
				"parent_item_group": "All Item Groups"
			})
			ig.insert(ignore_permissions=True)
			
		# Ensure UOM exists
		if not frappe.db.exists("UOM", "Nos"):
			uom = frappe.get_doc({
				"doctype": "UOM",
				"uom_name": "Nos",
				"must_be_whole_number": 1
			})
			uom.insert(ignore_permissions=True)
			
		for row in self.block_sizes:
			# Format: FB-{Density Code}-{L}x{W}x{H}
			item_code = f"FB-{self.density_code}-{int(row.length)}x{int(row.width)}x{int(row.height)}"
			
			if frappe.db.exists("Item", item_code):
				continue

			volume_m3 = (row.length * row.width * row.height) / 1000000000
			weight_kg = volume_m3 * self.density_value

			item = frappe.get_doc({
				"doctype": "Item",
				"item_code": item_code,
				"item_name": item_code,
				"item_group": "Foam Blocks",
				"stock_uom": "Nos",
				"is_stock_item": 1,
				"custom_density": self.density_value,
				"custom_length": row.length,
				"custom_width": row.width,
				"custom_height": row.height,
				"custom_weight": weight_kg,
				"custom_cbm": volume_m3
			})
			item.insert(ignore_permissions=True)
