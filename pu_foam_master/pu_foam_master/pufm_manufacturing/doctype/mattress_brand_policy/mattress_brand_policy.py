import frappe
from frappe.model.document import Document


class MattressBrandPolicy(Document):
	pass


@frappe.whitelist()
def get_allowed_fabric_items(brand):
	"""Return fabric item codes allowed for a native Brand."""
	if not brand:
		return []

	policy = frappe.db.get_value("Mattress Brand Policy", {"brand_name": brand}, "name")
	if not policy:
		# Legacy: policy autoname was the brand value itself
		if frappe.db.exists("Mattress Brand Policy", brand):
			policy = brand
		else:
			return []

	rows = frappe.get_all(
		"Allowed Fabric",
		filters={"parenttype": "Mattress Brand Policy", "parent": policy},
		fields=["fabric_item"],
	)
	return [r.fabric_item for r in rows if r.fabric_item]


@frappe.whitelist()
def get_allowed_fabrics(doctype, txt, searchfield, start, page_len, filters):
	"""Link query helper: fabrics allowed for a core Item's Brand."""
	filters = frappe._dict(filters or {})
	core_item = filters.get("core_item")
	if not core_item:
		return []

	item_brand = frappe.db.get_value("Item", core_item, "brand")
	if not item_brand:
		return []

	allowed = get_allowed_fabric_items(item_brand)
	txt = (txt or "").lower()
	matched = [item for item in allowed if txt in (item or "").lower()]
	start = int(start or 0)
	page_len = int(page_len or 20)
	return [[item] for item in matched[start : start + page_len]]
