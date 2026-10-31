import frappe
from frappe import _
from frappe.model.document import Document

from pu_foam_master.pufm_manufacturing.utils.mattress_sku import policy_document_name


class MattressBrandPolicy(Document):
	def autoname(self):
		brand = (self.brand_name or "").strip()
		if not brand:
			frappe.throw(_("Brand is required."))
		self.name = policy_document_name(brand, self.product_line)


def resolve_policy_name(brand, product_line=None):
	"""Find policy docname: product-line specific, then brand default, then legacy name."""
	brand = (brand or "").strip()
	line = (product_line or "").strip()
	if not brand:
		return None

	if line:
		specific = policy_document_name(brand, line)
		if frappe.db.exists("Mattress Brand Policy", specific):
			return specific
		match = frappe.db.get_value(
			"Mattress Brand Policy",
			{"brand_name": brand, "product_line": line},
			"name",
		)
		if match:
			return match

	default_name = policy_document_name(brand, None)
	if frappe.db.exists("Mattress Brand Policy", default_name):
		return default_name

	match = frappe.db.get_value(
		"Mattress Brand Policy",
		{"brand_name": brand, "product_line": ("in", ("", None))},
		"name",
	)
	if match:
		return match

	if frappe.db.exists("Mattress Brand Policy", brand):
		return brand

	return None


@frappe.whitelist()
def get_allowed_fabric_items(brand, product_line=None):
	"""Return fabric item codes allowed for brand + optional product line."""
	if not brand:
		return []

	policy = resolve_policy_name(brand, product_line)
	if not policy:
		return []

	rows = frappe.get_all(
		"Allowed Fabric",
		filters={"parenttype": "Mattress Brand Policy", "parent": policy},
		fields=["fabric_item"],
	)
	return [r.fabric_item for r in rows if r.fabric_item]


@frappe.whitelist()
def get_allowed_fabrics(doctype, txt, searchfield, start, page_len, filters):
	"""Link query helper: fabrics allowed for a core Item's brand + product line."""
	filters = frappe._dict(filters or {})
	core_item = filters.get("core_item")
	if not core_item:
		return []

	from pu_foam_master.pufm_manufacturing.utils.mattress_sku import get_product_line_for_item

	item_brand = frappe.db.get_value("Item", core_item, "brand")
	if not item_brand:
		return []

	product_line = get_product_line_for_item(core_item)
	allowed = get_allowed_fabric_items(item_brand, product_line)
	txt = (txt or "").lower()
	matched = [item for item in allowed if txt in (item or "").lower()]
	start = int(start or 0)
	page_len = int(page_len or 20)
	return [[item] for item in matched[start : start + page_len]]
