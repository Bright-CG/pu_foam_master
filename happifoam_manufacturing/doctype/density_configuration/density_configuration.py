# Copyright (c) 2026, Happifoam and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class DensityConfiguration(Document):
	def validate(self):
		self.calculate_values()
		if self.density_value <= 0:
			frappe.throw("Density must be greater than zero.")
			
		# Duplicate Prevention: Ensure a density name cannot be created twice
		if frappe.db.exists("Density Configuration", {"density_name": self.density_name, "name": ["!=", self.name]}):
			frappe.throw(f"A Density Configuration with the name '{self.density_name}' already exists.")

	def calculate_values(self):
		# Dimensions in meters
		self.width_meters = (self.width_inches or 0) * 0.0254
		self.height_meters = (self.height_inches or 0) * 0.0254
		
		# Output rate
		self.output_rate_m3_per_min = self.width_meters * self.height_meters * (self.conveyor_speed or 0)

		# Production Inputs calculations
		for row in self.get("production_inputs"):
			row.flow_min = (row.flow_factor or 0) * (row.set_at or 0)
			if self.output_rate_m3_per_min:
				row.qty_per_m3 = row.flow_min / self.output_rate_m3_per_min
			else:
				row.qty_per_m3 = 0

		# Output Item Variants calculations
		for row in self.get("output_item_variants"):
			row.unit_cbm = (row.width * row.height * row.length) / 61023.74

	def on_update(self):
		if self.auto_generate_items and not self.items_generated:
			self.generate_items()
			self.db_set("items_generated", 1)

	def generate_items(self):
		# Ensure Item Group exists
		if not frappe.db.exists("Item Group", "Foam Products"):
			ig = frappe.get_doc({
				"doctype": "Item Group",
				"item_group_name": "Foam Products",
				"parent_item_group": "All Item Groups"
			})
			ig.insert(ignore_permissions=True)
		
		for row in self.get("output_item_variants"):
			# Format: {Branding}-{Type}-{Density}-{WxHxL}
			item_code = f"{row.branding or 'GEN'}-{row.item_type[:4].upper()}-{self.density_code}-{int(row.width)}x{int(row.height)}x{int(row.length)}"
			
			if frappe.db.exists("Item", item_code):
				continue

			item = frappe.get_doc({
				"doctype": "Item",
				"item_code": item_code,
				"item_name": item_code,
				"item_group": "Foam Products",
				"stock_uom": "Nos",
				"is_stock_item": 1,
				"custom_density_val": self.density_value,
				"custom_length_in": row.length,
				"custom_width_in": row.width,
				"custom_height_in": row.height,
				"custom_weight_kg": row.unit_cbm * self.density_value,
				"custom_cbm_val": row.unit_cbm
			})
			item.insert(ignore_permissions=True)
