import frappe
from frappe import _
from frappe.utils import flt

VIRTUAL_ITEM_SUFFIX = "-BASE-FOAM-M3"
PRECISION = 5
CBM_DIVISOR = 61023.74


def get_virtual_item_code(density_name):
	return f"{density_name.strip()}{VIRTUAL_ITEM_SUFFIX}"


def format_dim(value):
	number = flt(value, PRECISION)
	if float(number).is_integer():
		return str(int(number))
	return f"{number:g}"


def build_block_item_code(density_name, length, width, height):
	return (
		f"{(density_name or '').strip()}-"
		f"{format_dim(length)}x{format_dim(width)}x{format_dim(height)} Block"
	)


def resolve_density_company(doc):
	"""Company that owns this density recipe / its Auto BOM."""
	company = getattr(doc, "company", None)
	if company and frappe.db.exists("Company", company):
		return company
	return get_preferred_company()


def get_preferred_company():
	"""Prefer primary Solarfoam (SF) over demo Solarfoam (Demo)/SFD."""
	if frappe.db.exists("Company", "Solarfoam"):
		return "Solarfoam"
	by_abbr = frappe.db.get_value("Company", {"abbr": "SF"}, "name")
	if by_abbr:
		return by_abbr
	company = frappe.defaults.get_user_default("Company")
	if company and frappe.db.exists("Company", company) and "Demo" not in company:
		return company
	company = frappe.db.get_single_value("Global Defaults", "default_company")
	if company and frappe.db.exists("Company", company):
		return company
	companies = frappe.get_all("Company", pluck="name", order_by="creation asc", limit=1)
	return companies[0] if companies else None


def ensure_virtual_item(density_name):
	item_code = get_virtual_item_code(density_name)
	if frappe.db.exists("Item", item_code):
		return item_code

	item_group = (
		frappe.db.get_single_value("Pufm Manufacturing Settings", "block_item_group")
		or "Products"
	)
	item = frappe.new_doc("Item")
	item.item_code = item_code
	item.item_name = item_code
	item.item_group = item_group
	item.is_stock_item = 1
	item.stock_uom = _get_stock_uom()
	item.include_item_in_manufacturing = 1
	item.custom_cbm_value = 1
	item.insert(ignore_permissions=True)
	return item_code


def sync_bom_for_density_config(doc, cancel_existing=True):
	"""
	ERPNext BOM update flow for a submitted recipe:
	1. Unlink references that block cancel (Density.active_bom, Item.default_bom)
	2. Cancel the old submitted BOM (docstatus -> 2)
	3. Create and submit a new BOM
	4. Relink active_bom / default_bom
	"""
	virtual_item = ensure_virtual_item(doc.density_name)
	company = resolve_density_company(doc)
	if not company:
		frappe.throw(_("Company is required on Density Configuration to create BOMs."))

	old_bom = doc.active_bom
	if cancel_existing and old_bom and frappe.db.exists("BOM", old_bom):
		_cancel_linked_bom(doc, old_bom, virtual_item)

	bom = frappe.new_doc("BOM")
	bom.item = virtual_item
	bom.quantity = 1
	bom.company = company
	bom.is_active = 1
	bom.is_default = 1
	bom.with_operations = 0

	for row in doc.get("production_inputs") or []:
		if not row.item_code or flt(row.qty_per_m3) <= 0:
			continue
		bom.append(
			"items",
			{
				"item_code": row.item_code,
				"qty": flt(row.qty_per_m3),
				"uom": frappe.db.get_value("Item", row.item_code, "stock_uom") or "Nos",
			},
		)

	if not bom.items:
		frappe.throw(
			_("Density Configuration {0} has no production inputs with qty per m3.").format(
				doc.density_name
			)
		)

	bom.insert(ignore_permissions=True)
	bom.submit()

	frappe.db.set_value(
		"Item",
		virtual_item,
		"default_bom",
		bom.name,
		update_modified=False,
	)
	doc.db_set("virtual_item", virtual_item, update_modified=False)
	doc.db_set("active_bom", bom.name, update_modified=False)
	return bom.name


def cancel_active_bom(doc):
	if not doc.active_bom or not frappe.db.exists("BOM", doc.active_bom):
		return

	virtual_item = doc.virtual_item or get_virtual_item_code(doc.density_name)
	_cancel_linked_bom(doc, doc.active_bom, virtual_item)
	doc.db_set("active_bom", None, update_modified=False)


def sync_related_block_items(doc):
	"""
	Update (and rename if needed) block Items tied to this density when
	width/height change, so CBM and dimensions stay correct.
	"""
	density_name = (doc.density_name or "").strip()
	if not density_name:
		return {"updated": [], "renamed": []}

	width = flt(doc.width_inches, PRECISION)
	height = flt(doc.height_inches, PRECISION)
	if width <= 0 or height <= 0:
		return {"updated": [], "renamed": []}

	candidates = frappe.get_all(
		"Item",
		filters={
			"disabled": 0,
			"name": ["like", f"{density_name}-% Block"],
		},
		fields=["name", "custom_length"],
	)
	legacy = frappe.get_all(
		"Item",
		filters={
			"disabled": 0,
			"name": ["like", f"{density_name} by % Block"],
		},
		fields=["name", "custom_length"],
	)

	seen = set()
	items = []
	for row in candidates + legacy:
		if row.name in seen or row.name.endswith(VIRTUAL_ITEM_SUFFIX):
			continue
		seen.add(row.name)
		items.append(row)

	updated = []
	renamed = []

	for row in items:
		length = flt(row.custom_length, PRECISION)
		if length <= 0:
			length = _parse_length_from_item_code(row.name, density_name)
		if length <= 0:
			continue

		new_cbm = flt((length * width * height) / CBM_DIVISOR, PRECISION)
		new_code = build_block_item_code(density_name, length, width, height)

		item = frappe.get_doc("Item", row.name)
		item.custom_length = length
		item.custom_width = width
		item.custom_height = height
		item.custom_cbm_value = new_cbm
		if item.item_name == row.name or not item.item_name:
			item.item_name = new_code if new_code else item.item_name
		item.save(ignore_permissions=True)
		current_name = item.name
		updated.append(current_name)

		if current_name != new_code and not frappe.db.exists("Item", new_code):
			frappe.rename_doc("Item", current_name, new_code, force=True, merge=False)
			renamed.append({"from": current_name, "to": new_code})

	return {"updated": updated, "renamed": renamed}


def _cancel_linked_bom(doc, bom_name, virtual_item=None):
	"""Clear inbound Link fields, then cancel the BOM (ERPNext replace flow)."""
	if getattr(doc, "active_bom", None) == bom_name:
		doc.db_set("active_bom", None, update_modified=False)

	if virtual_item and frappe.db.exists("Item", virtual_item):
		if frappe.db.get_value("Item", virtual_item, "default_bom") == bom_name:
			frappe.db.set_value("Item", virtual_item, "default_bom", None, update_modified=False)

	for item_code in frappe.get_all("Item", filters={"default_bom": bom_name}, pluck="name"):
		frappe.db.set_value("Item", item_code, "default_bom", None, update_modified=False)

	bom_doc = frappe.get_doc("BOM", bom_name)
	if bom_doc.docstatus != 1:
		return

	bom_doc.db_set("is_default", 0, update_modified=False)
	bom_doc.db_set("is_active", 0, update_modified=False)
	bom_doc.reload()
	bom_doc.cancel()


def _parse_length_from_item_code(item_code, density_name):
	name = (item_code or "").strip()
	prefix_new = f"{density_name}-"
	prefix_legacy = f"{density_name} by "

	try:
		if name.startswith(prefix_new) and name.endswith(" Block"):
			body = name[len(prefix_new) : -len(" Block")]
			return flt(body.split("x")[0], PRECISION)
		if name.startswith(prefix_legacy) and name.endswith(" Block"):
			body = name[len(prefix_legacy) : -len(" Block")]
			return flt(body, PRECISION)
	except Exception:
		return 0
	return 0


def _get_stock_uom():
	if frappe.db.exists("UOM", "M3"):
		return "M3"
	if frappe.db.exists("UOM", "Cubic Meter"):
		return "Cubic Meter"
	return "Nos"


def smoke_test_bom_replace(density_name="D40"):
	"""Manual check: cancel+recreate BOM without link errors."""
	doc = frappe.get_doc("Density Configuration", density_name)
	old_bom = doc.active_bom
	new_bom = sync_bom_for_density_config(doc, cancel_existing=True)
	doc.reload()
	old_status = frappe.db.get_value("BOM", old_bom, "docstatus") if old_bom else None
	new_status = frappe.db.get_value("BOM", doc.active_bom, "docstatus")
	frappe.db.commit()
	return {
		"old_bom": old_bom,
		"new_bom": doc.active_bom,
		"old_status": old_status,
		"new_status": new_status,
		"ok": bool(old_bom and old_bom != doc.active_bom and old_status == 2 and new_status == 1),
	}
