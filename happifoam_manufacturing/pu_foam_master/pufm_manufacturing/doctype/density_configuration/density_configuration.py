import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from pu_foam_master.pufm_manufacturing.utils.density_bom import (
	CBM_DIVISOR,
	PRECISION,
	build_block_item_code,
	cancel_active_bom,
	get_preferred_company,
	get_virtual_item_code,
	sync_bom_for_density_config,
	sync_related_block_items,
)


class DensityConfiguration(Document):
	def validate(self):
		if not self.company:
			self.company = get_preferred_company()
		if not self.company:
			frappe.throw(_("Company is required."))
		self.calculate_values()

	def on_submit(self):
		virtual_item = get_virtual_item_code(self.density_name)
		self.db_set("virtual_item", virtual_item, update_modified=False)
		sync_bom_for_density_config(self, cancel_existing=False)

	def on_update_after_submit(self):
		# Recalculate recipe rates, rebuild BOM (cancel old -> submit new), sync block Items
		self.calculate_values()
		sync_bom_for_density_config(self, cancel_existing=True)
		sync_related_block_items(self)

	def on_cancel(self):
		cancel_active_bom(self)

	def calculate_values(self):
		self.width_meters = flt(flt(self.width_inches) * 0.0254, PRECISION)
		self.height_meters = flt(flt(self.height_inches) * 0.0254, PRECISION)

		self.output_rate_m3_per_min = flt(
			flt(self.conveyor_speed)
			* flt(self.calibration_factor or 1.0)
			* flt(self.width_meters)
			* flt(self.height_meters),
			PRECISION,
		)

		for row in self.get("production_inputs") or []:
			row.flow_min = flt(flt(row.flow_factor) * flt(row.set_at), PRECISION)
			if self.output_rate_m3_per_min:
				row.qty_per_m3 = flt(
					flt(row.flow_min) / flt(self.output_rate_m3_per_min),
					PRECISION,
				)
			else:
				row.qty_per_m3 = flt(0, PRECISION)

		for row in self.get("bom_operations") or []:
			# Time to produce 1 m3 at current machine output rate
			if self.output_rate_m3_per_min:
				row.time = flt(1 / flt(self.output_rate_m3_per_min), PRECISION)
			else:
				row.time = flt(0, PRECISION)
			hour_rate = flt(row.get("hour_rate"), PRECISION)
			row.operating_cost = flt((flt(row.time) / 60.0) * hour_rate, PRECISION)
			if hasattr(row, "time_in_mins"):
				row.time_in_mins = flt(row.time, PRECISION)
			if hasattr(row, "description") and not row.get("description"):
				row.description = row.operation


@frappe.whitelist()
def generate_block_items(docname, lengths_string=None):
	"""Create or update stock Items for each target block length on a Density Configuration."""
	if not docname:
		frappe.throw(_("Density Configuration name is required."))

	doc = frappe.get_doc("Density Configuration", docname)
	# Prefer unsaved lengths from the form; fall back to saved doc field
	lengths_raw = (lengths_string or doc.get("target_block_lengths") or "").strip()
	if not lengths_raw:
		frappe.throw(_("Please enter Target Block Lengths."))

	length_tokens = [token.strip() for token in lengths_raw.split(",") if token.strip()]
	if not length_tokens:
		frappe.throw(_("No valid lengths found. Use commas to separate values (e.g. 54, 75, 84)."))

	width = flt(doc.width_inches, PRECISION)
	height = flt(doc.height_inches, PRECISION)
	if width <= 0 or height <= 0:
		frappe.throw(_("Width (Inches) and Height (Inches) must be greater than zero."))

	item_group = (
		frappe.db.get_single_value("Pufm Manufacturing Settings", "block_item_group")
		or "Raw Material"
	)
	if not frappe.db.exists("Item Group", item_group):
		frappe.throw(
			_("Item Group {0} does not exist. Set Block Item Group in settings.").format(item_group)
		)

	created = []
	updated = []
	invalid = []

	for token in length_tokens:
		try:
			length = flt(token, PRECISION)
		except (TypeError, ValueError):
			invalid.append(token)
			continue

		if length <= 0:
			invalid.append(token)
			continue

		# SKU: {density}-{L}x{W}x{H} Block using loop length + saved W/H
		item_code = build_block_item_code(doc.density_name, length, width, height)
		volume_cbm = flt((length * width * height) / CBM_DIVISOR, PRECISION)

		if frappe.db.exists("Item", item_code):
			item = frappe.get_doc("Item", item_code)
			item.custom_length = length
			item.custom_width = width
			item.custom_height = height
			item.custom_cbm_value = volume_cbm
			item.save(ignore_permissions=True)
			updated.append(item_code)
			continue

		item = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_code,
				"item_name": item_code,
				"item_group": item_group,
				"stock_uom": "Nos",
				"is_stock_item": 1,
				"include_item_in_manufacturing": 1,
				"custom_length": length,
				"custom_width": width,
				"custom_height": height,
				"custom_cbm_value": volume_cbm,
			}
		)
		item.insert(ignore_permissions=True)
		created.append(item_code)

	# Also refresh any already-generated blocks for this density (legacy names / prior dims)
	sync_related_block_items(doc)
	frappe.db.commit()

	parts = []
	if created:
		parts.append(_("Created {0}: {1}").format(len(created), ", ".join(created)))
	if updated:
		parts.append(_("Updated {0}: {1}").format(len(updated), ", ".join(updated)))
	if invalid:
		parts.append(_("Invalid lengths ignored: {0}").format(", ".join(invalid)))
	if not parts:
		parts.append(_("No items were created or updated."))

	return {
		"message": " | ".join(parts),
		"created": created,
		"updated": updated,
		"invalid": invalid,
	}
