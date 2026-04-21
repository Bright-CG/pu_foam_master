import frappe
from frappe.model.document import Document


class MattressBrandPolicy(Document):
	pass


@frappe.whitelist()
def get_allowed_fabric_items(brand):
	if not brand:
		return []

	rows = frappe.get_all(
		"Allowed Fabric",
		filters={"parenttype": "Mattress Brand Policy", "parent": brand},
		fields=["fabric_item"],
	)
	return [r.fabric_item for r in rows if r.fabric_item]
