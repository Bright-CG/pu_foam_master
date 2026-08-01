import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from pu_foam_master.pufm_manufacturing.utils.density_bom import (
	PRECISION,
	build_block_item_code,
	cancel_active_bom,
	get_preferred_company,
	get_virtual_item_code,
	sync_bom_for_density_config,
	sync_related_block_items,
)
from pu_foam_master.pufm_manufacturing.utils.item_traceability import (
	apply_finished_good_traceability,
	finished_good_traceability_defaults,
)
from pu_foam_master.pufm_manufacturing.utils.settings import get_cbm_factor, get_formula_factor


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
		# Always refresh recipe math for display
		self.calculate_values()

		if not self.is_new():
			dimensions_changed = (
				self.has_value_changed("width_inches")
				or self.has_value_changed("height_inches")
				or self.has_value_changed("conveyor_speed")
				or self.has_value_changed("calibration_factor")
			)
			chemicals_changed = self.has_value_changed("production_inputs")
			operations_changed = self.has_value_changed("bom_operations")

			if not (dimensions_changed or chemicals_changed or operations_changed):
				# Brand / text-only changes: refresh Item brand, skip BOM rebuild
				if self.has_value_changed("brand"):
					_sync_block_item_brands(self)
				return

		# Dimensions, chemicals, or operations changed → rebuild BOM
		sync_bom_for_density_config(self, cancel_existing=True)
		sync_related_block_items(self)
		if self.brand:
			_sync_block_item_brands(self)

	def on_cancel(self):
		cancel_active_bom(self)

	def calculate_values(self):
		inch_to_m = get_formula_factor("inches_to_meters_factor")
		self.width_meters = flt(flt(self.width_inches) * inch_to_m, PRECISION)
		self.height_meters = flt(flt(self.height_inches) * inch_to_m, PRECISION)

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
def get_clone_recipe(source_name, new_density_name=None):
	"""Return recipe fields for a new Density Configuration draft (no BOM / virtual item)."""
	if not source_name:
		frappe.throw(_("Source Density Configuration is required."))

	source = frappe.get_doc("Density Configuration", source_name)
	if source.docstatus == 2:
		frappe.throw(_("Cannot clone a cancelled Density Configuration."))

	new_name = (new_density_name or "").strip()
	if new_name and frappe.db.exists("Density Configuration", new_name):
		frappe.throw(_("Density Configuration {0} already exists.").format(new_name))

	# copy_doc respects no_copy on virtual_item / active_bom
	target = frappe.copy_doc(source)
	if new_name:
		target.density_name = new_name
	target.virtual_item = None
	target.active_bom = None

	data = target.as_dict()
	for key in (
		"name",
		"creation",
		"modified",
		"modified_by",
		"owner",
		"docstatus",
		"amended_from",
		"_user_tags",
		"_comments",
		"_assign",
		"_liked_by",
	):
		data.pop(key, None)

	data["virtual_item"] = None
	data["active_bom"] = None

	for table in ("production_inputs", "bom_operations"):
		cleaned = []
		for row in data.get(table) or []:
			row = frappe._dict(row)
			for key in (
				"name",
				"owner",
				"creation",
				"modified",
				"modified_by",
				"parent",
				"parentfield",
				"parenttype",
				"docstatus",
			):
				row.pop(key, None)
			cleaned.append(row)
		data[table] = cleaned

	return data


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

	settings = frappe.get_single("Pufm Manufacturing Settings")
	item_group = settings.block_item_group or "Raw Material"
	# Prefer density Brand, fall back to manufacturing default
	default_brand = doc.get("brand") or settings.default_brand or None
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
		volume_cbm = flt((length * width * height) / get_cbm_factor(), PRECISION)

		if frappe.db.exists("Item", item_code):
			item = frappe.get_doc("Item", item_code)
			item.custom_length = length
			item.custom_width = width
			item.custom_height = height
			item.custom_cbm_value = volume_cbm
			apply_finished_good_traceability(item, brand=default_brand)
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
				**finished_good_traceability_defaults(brand=default_brand),
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


def _sync_block_item_brands(doc):
	"""Push Density Configuration.brand onto related block Items."""
	brand = (doc.get("brand") or "").strip()
	if not brand:
		return
	density_name = (doc.density_name or "").strip()
	if not density_name:
		return
	items = frappe.get_all(
		"Item",
		filters={"disabled": 0, "name": ["like", f"{density_name}-% Block"]},
		pluck="name",
	)
	for item_code in items:
		if frappe.db.get_value("Item", item_code, "brand") != brand:
			frappe.db.set_value("Item", item_code, "brand", brand, update_modified=False)
