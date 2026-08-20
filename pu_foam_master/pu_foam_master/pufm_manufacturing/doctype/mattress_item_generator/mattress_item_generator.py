import frappe
from frappe.model.document import Document
from frappe.utils import cint, flt

from pu_foam_master.pufm_manufacturing.utils.settings import get_cbm_factor

DEFAULT_SUFFIXES = {
	"core_suffix": "-CORE",
	"plain_suffix": "-PLAIN",
	"side_quilted_suffix": "-SQ",
	"fully_quilted_suffix": "-FQ",
}


class MattressItemGenerator(Document):
	def validate(self):
		self._ensure_suffix_defaults()
		self._recompute_cbm()

	def _ensure_suffix_defaults(self):
		for fieldname, default in DEFAULT_SUFFIXES.items():
			if not (self.get(fieldname) or "").strip():
				self.set(fieldname, default)

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

	if not doc.sizes:
		frappe.throw("Please fetch/add at least one size row.")

	safe_core_group = get_or_create_item_group(doc.core_item_group)
	core_only = cint(doc.get("generate_core_only"))
	safe_mattress_group = None
	if not core_only:
		safe_mattress_group = get_or_create_item_group(doc.mattress_item_group)

	core_suffix = (doc.core_suffix or DEFAULT_SUFFIXES["core_suffix"]).strip()
	plain_suffix = (doc.plain_suffix or DEFAULT_SUFFIXES["plain_suffix"]).strip()
	sq_suffix = (doc.side_quilted_suffix or DEFAULT_SUFFIXES["side_quilted_suffix"]).strip()
	fq_suffix = (doc.fully_quilted_suffix or DEFAULT_SUFFIXES["fully_quilted_suffix"]).strip()

	created_or_verified = []
	brand_token = _resolve_brand_token(doc)
	brand_link = _resolve_brand_link(doc)
	for row in doc.sizes:
		size = _format_size(row.width, row.length, row.height)
		core_code = _branded_item_code(brand_token, size, core_suffix)

		_ensure_item(
			core_code, safe_core_group, row, brand=brand_link, serial_tracked=False
		)
		row.core_item = core_code
		created_or_verified.append(core_code)

		if not core_only:
			plain_code = _branded_item_code(brand_token, size, plain_suffix)
			sq_code = _branded_item_code(brand_token, size, sq_suffix)
			fq_code = _branded_item_code(brand_token, size, fq_suffix)
			for code, finish_type in (
				(plain_code, "Plain"),
				(sq_code, "Side Quilted"),
				(fq_code, "Fully Quilted"),
			):
				_ensure_item(
					code,
					safe_mattress_group,
					row,
					brand=brand_link,
					finish_type=finish_type,
					serial_tracked=True,
				)
				created_or_verified.append(code)
			# Primary finished SKU shown on the size row is the Plain mattress
			row.mattress_item = plain_code
		else:
			row.mattress_item = None

	doc.save(ignore_permissions=True)
	frappe.db.commit()

	return {
		"count": len(created_or_verified),
		"items": created_or_verified,
		"brand": brand_token,
	}


def _resolve_brand_link(doc):
	"""ERPNext Brand linked on generated Items (must exist as Brand)."""
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


def _resolve_brand_token(doc):
	"""Prefer Density Configuration.brand, then brand_name field, then density name."""
	brand = (doc.get("brand_name") or "").strip()
	if doc.density_configuration:
		density_brand = frappe.db.get_value(
			"Density Configuration", doc.density_configuration, "brand"
		)
		if density_brand:
			brand = density_brand
		elif not brand:
			brand = frappe.db.get_value(
				"Density Configuration", doc.density_configuration, "density_name"
			)
	return _sanitize_brand_token(brand)


def _sanitize_brand_token(brand):
	token = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in (brand or "").strip())
	token = "-".join(part for part in token.split("-") if part)
	return token


def _branded_item_code(brand_token, size, suffix):
	"""Naming standard: {brand}-{size}{suffix} e.g. Galaxy-42x84x8-FQ."""
	suffix = (suffix or "").strip()
	if brand_token:
		return f"{brand_token}-{size}{suffix}"
	return f"{size}{suffix}"


def _format_size(width, length, height):
	"""Build size token like 75x42x8 (drop trailing .0)."""

	def _fmt(value):
		number = flt(value)
		if float(number).is_integer():
			return str(int(number))
		return f"{number:g}"

	return f"{_fmt(width)}x{_fmt(length)}x{_fmt(height)}"


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


def _ensure_item(item_code, item_group, row, brand=None, finish_type=None, serial_tracked=True):
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
	if finish_type:
		payload["custom_finish_type"] = finish_type
	item = frappe.get_doc(payload)
	item.insert(ignore_permissions=True)
