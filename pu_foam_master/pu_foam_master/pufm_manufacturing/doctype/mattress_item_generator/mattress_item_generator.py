import frappe
from frappe.model.document import Document
from frappe.utils import cint, flt

from pu_foam_master.pufm_manufacturing.utils.mattress_sku import (
	build_item_code,
	sanitize_sku_token,
)
from pu_foam_master.pufm_manufacturing.utils.settings import get_cbm_factor

DEFAULT_SUFFIXES = {
	"core_suffix": "-CORE",
	"plain_suffix": "-PLAIN",
	"side_quilted_suffix": "-SQ",
	"fully_quilted_suffix": "-FQ",
}

FINISHED_VARIANTS = (
	("generate_plain", "plain_suffix", "Plain"),
	("generate_side_quilted", "side_quilted_suffix", "Side Quilted"),
	("generate_fully_quilted", "fully_quilted_suffix", "Fully Quilted"),
)


class MattressItemGenerator(Document):
	def validate(self):
		self._ensure_suffix_defaults()
		self._normalize_variant_flags()
		self._recompute_cbm()
		self._validate_generation_flags()

	def _ensure_suffix_defaults(self):
		for fieldname, default in DEFAULT_SUFFIXES.items():
			if not (self.get(fieldname) or "").strip():
				self.set(fieldname, default)

	def _normalize_variant_flags(self):
		for flag in (
			"generate_core",
			"generate_plain",
			"generate_side_quilted",
			"generate_fully_quilted",
		):
			if self.get(flag) is None:
				self.set(flag, 1)
		if cint(self.get("generate_core_only")):
			self.generate_plain = 0
			self.generate_side_quilted = 0
			self.generate_fully_quilted = 0

	def _validate_generation_flags(self):
		if not (self.get("product_line") or "").strip():
			frappe.throw("Product Line (SKU Prefix) is required.")
		if not any(
			cint(self.get(flag))
			for flag in (
				"generate_core",
				"generate_plain",
				"generate_side_quilted",
				"generate_fully_quilted",
			)
		):
			frappe.throw("Select at least one variant to generate (Core, Plain, SQ, or FQ).")

	def _recompute_cbm(self):
		cbm_factor = get_cbm_factor()
		for row in self.get("sizes") or []:
			row.unit_cbm = (
				(flt(row.width) * flt(row.length) * flt(row.height)) / cbm_factor
				if flt(row.width) and flt(row.length) and flt(row.height)
				else 0
			)


@frappe.whitelist()
def generate_mattress_items(docname):
	doc = frappe.get_doc("Mattress Item Generator", docname)
	doc._ensure_suffix_defaults()
	doc._normalize_variant_flags()
	doc._validate_generation_flags()

	if not doc.sizes:
		frappe.throw("Please fetch/add at least one size row.")

	product_line = sanitize_sku_token(doc.product_line)
	if not product_line:
		frappe.throw("Product Line (SKU Prefix) is required.")

	safe_core_group = get_or_create_item_group(doc.core_item_group)
	generate_core = cint(doc.generate_core)
	generate_finished = any(
		cint(doc.get(flag)) for flag, _, _ in FINISHED_VARIANTS
	)
	safe_mattress_group = None
	if generate_finished:
		safe_mattress_group = get_or_create_item_group(doc.mattress_item_group)

	core_suffix = (doc.core_suffix or DEFAULT_SUFFIXES["core_suffix"]).strip()
	suffix_map = {
		"plain_suffix": (doc.plain_suffix or DEFAULT_SUFFIXES["plain_suffix"]).strip(),
		"side_quilted_suffix": (
			doc.side_quilted_suffix or DEFAULT_SUFFIXES["side_quilted_suffix"]
		).strip(),
		"fully_quilted_suffix": (
			doc.fully_quilted_suffix or DEFAULT_SUFFIXES["fully_quilted_suffix"]
		).strip(),
	}

	created_or_verified = []
	brand_link = _resolve_erp_brand_link(doc)
	for row in doc.sizes:
		row.core_item = None
		row.mattress_item = None
		primary_finished = None

		if generate_core:
			core_code = build_item_code(
				product_line, row.width, row.length, row.height, core_suffix
			)
			_ensure_item(
				core_code,
				safe_core_group,
				row,
				brand=brand_link,
				product_line=product_line,
				finish_type=None,
				serial_tracked=False,
			)
			row.core_item = core_code
			created_or_verified.append(core_code)

		for flag, suffix_field, finish_type in FINISHED_VARIANTS:
			if not cint(doc.get(flag)):
				continue
			code = build_item_code(
				product_line,
				row.width,
				row.length,
				row.height,
				suffix_map[suffix_field],
			)
			_ensure_item(
				code,
				safe_mattress_group,
				row,
				brand=brand_link,
				product_line=product_line,
				finish_type=finish_type,
				serial_tracked=True,
			)
			created_or_verified.append(code)
			if primary_finished is None:
				primary_finished = code

		row.mattress_item = primary_finished

	doc.save(ignore_permissions=True)
	frappe.db.commit()

	return {
		"count": len(created_or_verified),
		"items": created_or_verified,
		"product_line": product_line,
		"erp_brand": brand_link,
	}


def _resolve_erp_brand_link(doc):
	"""ERPNext Brand on Items (e.g. HappiFoam) — not the SKU product line."""
	if doc.density_configuration:
		density_brand = frappe.db.get_value(
			"Density Configuration", doc.density_configuration, "brand"
		)
		if density_brand and frappe.db.exists("Brand", density_brand):
			return density_brand
	brand = (doc.get("brand_name") or "").strip()
	if brand and frappe.db.exists("Brand", brand):
		return brand
	return None


def get_or_create_item_group(group_name):
	if not group_name:
		return "All Item Groups"

	group_name = group_name.strip()
	if not group_name:
		return "All Item Groups"

	if not frappe.db.exists("Item Group", group_name):
		doc = frappe.new_doc("Item Group")
		doc.item_group_name = group_name
		doc.parent_item_group = "All Item Groups"
		doc.is_group = 0
		doc.insert(ignore_permissions=True)

	return group_name


def _ensure_item(
	item_code,
	item_group,
	row,
	brand=None,
	product_line=None,
	finish_type=None,
	serial_tracked=True,
):
	from pu_foam_master.pufm_manufacturing.utils.item_traceability import (
		apply_core_traceability,
		apply_finished_good_traceability,
		core_traceability_defaults,
		ensure_core_item_traceability,
		finished_good_traceability_defaults,
		item_has_stock_ledger,
	)

	if frappe.db.exists("Item", item_code):
		item = frappe.get_doc("Item", item_code)
		item.custom_width = flt(row.width)
		item.custom_length = flt(row.length)
		item.custom_height = flt(row.height)
		item.custom_cbm_value = flt(row.unit_cbm)
		if product_line:
			item.custom_product_line = product_line
		if brand:
			item.brand = brand
		if finish_type:
			item.custom_finish_type = finish_type
		if serial_tracked:
			if item_has_stock_ledger(item_code):
				item.save(ignore_permissions=True)
			else:
				apply_finished_good_traceability(item, brand=brand)
				item.save(ignore_permissions=True)
		elif item_has_stock_ledger(item_code):
			item.save(ignore_permissions=True)
			ensure_core_item_traceability(item_code, brand=brand, throw_if_locked=False)
		else:
			apply_core_traceability(item, brand=brand)
			item.save(ignore_permissions=True)
		return

	defaults = (
		finished_good_traceability_defaults(brand=brand)
		if serial_tracked
		else core_traceability_defaults(brand=brand)
	)
	payload = {
		"doctype": "Item",
		"item_code": item_code,
		"item_name": item_code,
		"item_group": item_group,
		"stock_uom": "Nos",
		"is_stock_item": 1,
		"include_item_in_manufacturing": 1,
		"custom_width": flt(row.width),
		"custom_length": flt(row.length),
		"custom_height": flt(row.height),
		"custom_cbm_value": flt(row.unit_cbm),
		**defaults,
	}
	if product_line:
		payload["custom_product_line"] = product_line
	if finish_type:
		payload["custom_finish_type"] = finish_type
	item = frappe.get_doc(payload)
	item.insert(ignore_permissions=True)
