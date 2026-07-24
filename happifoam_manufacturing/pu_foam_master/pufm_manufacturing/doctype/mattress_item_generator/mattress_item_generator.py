import frappe
from frappe.model.document import Document
from frappe.utils import flt


CBM_FACTOR = 61023.74


class MattressItemGenerator(Document):
	def validate(self):
		self._recompute_cbm()

	def _recompute_cbm(self):
		for row in self.get("sizes") or []:
			row.unit_cbm = (
				(flt(row.width) * flt(row.length) * flt(row.height)) / CBM_FACTOR
				if flt(row.width) and flt(row.length) and flt(row.height)
				else 0
			)


@frappe.whitelist()
def generate_mattress_items(docname):
	doc = frappe.get_doc("Mattress Item Generator", docname)
	brand = (doc.brand_name or "").strip().upper()
	if not brand:
		frappe.throw("Brand Name is required. Please select Density Configuration first.")

	if not doc.sizes:
		frappe.throw("Please fetch/add at least one size row.")

	safe_core_group = get_or_create_item_group(doc.core_item_group)
	safe_mattress_group = get_or_create_item_group(doc.mattress_item_group)

	created_or_verified = []
	for row in doc.sizes:
		size = f"{int(flt(row.width))}x{int(flt(row.length))}x{int(flt(row.height))}"
		core_code = f"CORE-{brand}-{size}"
		mat_code = f"MAT-{brand}-{size}"

		_ensure_item(core_code, safe_core_group, row)
		_ensure_item(mat_code, safe_mattress_group, row)

		row.core_item = core_code
		row.mattress_item = mat_code
		created_or_verified.extend([core_code, mat_code])

	doc.save(ignore_permissions=True)
	frappe.db.commit()

	return {
		"count": len(created_or_verified),
		"items": created_or_verified,
	}


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


def _ensure_item(item_code, item_group, row):
	if frappe.db.exists("Item", item_code):
		return

	item = frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": item_code,
			"item_name": item_code,
			"item_group": item_group,
			"stock_uom": "Nos",
			"is_stock_item": 1,
			"include_item_in_manufacturing": 1,
			"has_batch_no": 1,
			"has_serial_no": 1,
			"custom_width": flt(row.width),
			"custom_length": flt(row.length),
			"custom_height": flt(row.height),
			"custom_cbm_value": flt(row.unit_cbm),
		}
	)
	item.insert(ignore_permissions=True)
