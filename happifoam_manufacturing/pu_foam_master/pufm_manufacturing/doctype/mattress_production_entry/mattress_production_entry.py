import frappe
from frappe.model.document import Document
from frappe.utils import flt

# Inches -> meters (same constant used for fabric area conversion elsewhere)
INCH_TO_METER = 39.37
TAPE_EDGE_ITEM = "Tape Edge"


class MattressProductionEntry(Document):
	def validate(self):
		self._calculate_rows()

	def before_submit(self):
		self._calculate_rows()

	def on_submit(self):
		entry = self._create_repack_stock_entry()
		self.db_set("stock_entry", entry.name, update_modified=False)

	def _calculate_rows(self):
		settings = frappe.get_single("Pufm Manufacturing Settings")
		tape_rate = _get_tape_edge_rate(settings)

		for row in self.production_items or []:
			if flt(row.qty) <= 0:
				frappe.throw(f"Row {row.idx}: Quantity must be greater than zero.")

			item = frappe.get_cached_doc("Item", row.mattress_item)
			length = flt(item.custom_length)
			width = flt(item.custom_width)
			height = flt(item.custom_height)
			if not (length and width and height):
				frappe.throw(f"Row {row.idx}: Mattress item dimensions are missing.")

			# Top + bottom perimeter tape, tracked strictly in meters
			tape_meters = _tape_edge_meters(length, width, row.qty)
			tape_cost = tape_meters * tape_rate

			pvc_usage = (length * width) / 1550
			pvc_cost = pvc_usage * flt(row.qty) * flt(settings.pvc_rate_per_sqm)

			thread_label_cost = (flt(settings.thread_rate_per_mat) + flt(settings.label_rate_per_pc)) * flt(
				row.qty
			)

			fabric_width_inches = _resolve_fabric_width(row.fabric_item)
			total_area = (2 * (length * width)) + ((2 * (length + width)) * height)
			total_area = total_area * (1 + (flt(settings.fabric_waste_factor) / 100))
			fabric_meters = (total_area / (fabric_width_inches * INCH_TO_METER)) * flt(row.qty)

			core_rate = _get_batch_valuation_rate(row.core_batch)
			fabric_rate = _get_batch_valuation_rate(row.fabric_batch)
			core_cost = flt(row.qty) * core_rate
			fabric_cost = fabric_meters * fabric_rate
			consumables = tape_cost + pvc_cost + thread_label_cost
			row.total_row_cost = core_cost + fabric_cost + consumables

	def _create_repack_stock_entry(self):
		entry = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Repack",
				"posting_date": self.posting_date,
				"set_posting_time": 1,
				"items": [],
			}
		)

		tape_item = _resolve_tape_edge_item()
		tape_doc = frappe.get_cached_doc("Item", tape_item) if tape_item else None
		tape_uom = (tape_doc.stock_uom if tape_doc else None) or "Meter"
		tape_rate = _get_tape_edge_rate(frappe.get_single("Pufm Manufacturing Settings"))

		for row in self.production_items or []:
			fabric_meters = _recalculate_fabric_meters(row)
			tape_meters = _recalculate_tape_meters(row)
			core_item = _get_batch_item(row.core_batch)
			fabric_item = row.fabric_item or _get_batch_item(row.fabric_batch)

			core_doc = frappe.get_cached_doc("Item", core_item)
			fabric_doc = frappe.get_cached_doc("Item", fabric_item)
			mattress_doc = frappe.get_cached_doc("Item", row.mattress_item)

			entry.append(
				"items",
				{
					"item_code": core_item,
					"s_warehouse": self.target_warehouse,
					"batch_no": row.core_batch,
					"qty": flt(row.qty),
					"uom": core_doc.stock_uom,
					"stock_uom": core_doc.stock_uom,
					"conversion_factor": 1,
					"valuation_rate": _get_batch_valuation_rate(row.core_batch),
				},
			)
			entry.append(
				"items",
				{
					"item_code": fabric_item,
					"s_warehouse": self.target_warehouse,
					"batch_no": row.fabric_batch,
					"qty": fabric_meters,
					"uom": fabric_doc.stock_uom or "Meter",
					"stock_uom": fabric_doc.stock_uom or "Meter",
					"conversion_factor": 1,
					"valuation_rate": _get_batch_valuation_rate(row.fabric_batch),
				},
			)

			if tape_item and flt(tape_meters) > 0:
				entry.append(
					"items",
					{
						"item_code": tape_item,
						"s_warehouse": self.target_warehouse,
						"qty": tape_meters,
						"uom": tape_uom,
						"stock_uom": tape_uom,
						"conversion_factor": 1,
						"valuation_rate": tape_rate,
					},
				)

			unit_rate = flt(row.total_row_cost) / flt(row.qty)
			entry.append(
				"items",
				{
					"item_code": row.mattress_item,
					"t_warehouse": self.target_warehouse,
					"qty": flt(row.qty),
					"uom": mattress_doc.stock_uom,
					"stock_uom": mattress_doc.stock_uom,
					"conversion_factor": 1,
					"basic_rate": unit_rate,
					"valuation_rate": unit_rate,
				},
			)

		entry.insert(ignore_permissions=True)
		entry.submit()
		return entry


def _tape_edge_meters(length_inches, width_inches, qty):
	"""
	Tape edge consumption in meters.
	Two full perimeters (top + bottom edge): 4 * (L + W) inches -> meters.
	"""
	inches = 4.0 * (flt(length_inches) + flt(width_inches))
	return (inches / INCH_TO_METER) * flt(qty)


def _recalculate_tape_meters(row):
	item = frappe.get_cached_doc("Item", row.mattress_item)
	return _tape_edge_meters(item.custom_length, item.custom_width, row.qty)


def _resolve_tape_edge_item():
	if frappe.db.exists("Item", TAPE_EDGE_ITEM):
		return TAPE_EDGE_ITEM
	return None


def _get_tape_edge_rate(settings=None):
	"""Prefer live stock valuation for Tape Edge (NGN/meter); fall back to settings."""
	item_code = _resolve_tape_edge_item()
	if item_code:
		rate = flt(frappe.db.get_value("Bin", {"item_code": item_code}, "valuation_rate"))
		if rate <= 0:
			rate = flt(frappe.db.get_value("Item", item_code, "valuation_rate"))
		if rate > 0:
			return rate

	settings = settings or frappe.get_single("Pufm Manufacturing Settings")
	# Field historically named per yard; treated as per-meter once inventory is meter-based
	return flt(settings.tape_rate_per_yard)


def _resolve_fabric_width(item_code):
	if not item_code:
		return 84.0
	width = flt(frappe.db.get_value("Item", item_code, "custom_width"))
	return width or 84.0


def _get_batch_valuation_rate(batch_no):
	if not batch_no:
		return 0

	meta = frappe.get_meta("Batch")
	if meta.has_field("valuation_rate"):
		return flt(frappe.db.get_value("Batch", batch_no, "valuation_rate"))

	row = frappe.db.sql(
		"""
		SELECT valuation_rate
		FROM `tabStock Ledger Entry`
		WHERE batch_no = %s
		ORDER BY posting_date DESC, posting_time DESC, creation DESC
		LIMIT 1
		""",
		(batch_no,),
		as_dict=True,
	)
	return flt(row[0].valuation_rate) if row else 0


def _get_batch_item(batch_no):
	return frappe.db.get_value("Batch", batch_no, "item")


def _recalculate_fabric_meters(row):
	settings = frappe.get_single("Pufm Manufacturing Settings")
	item = frappe.get_cached_doc("Item", row.mattress_item)
	length = flt(item.custom_length)
	width = flt(item.custom_width)
	height = flt(item.custom_height)
	fabric_width_inches = _resolve_fabric_width(row.fabric_item)
	total_area = (2 * (length * width)) + ((2 * (length + width)) * height)
	total_area = total_area * (1 + (flt(settings.fabric_waste_factor) / 100))
	return (total_area / (fabric_width_inches * INCH_TO_METER)) * flt(row.qty)


@frappe.whitelist()
def get_allowed_fabric_items_for_mattress(mattress_item):
	"""Resolve fabrics from the mattress Item's native Brand policy."""
	if not mattress_item:
		return []

	item_brand = frappe.db.get_value("Item", mattress_item, "brand")
	if not item_brand:
		# Fallback: MAT-{BRAND}-{size} naming
		item_brand = _extract_brand_from_item(mattress_item)
	if not item_brand:
		return []

	from pu_foam_master.pufm_manufacturing.doctype.mattress_brand_policy.mattress_brand_policy import (
		get_allowed_fabric_items,
	)

	return get_allowed_fabric_items(item_brand)


def _extract_brand_from_item(item_code):
	code = (item_code or "").upper()
	if not code.startswith("MAT-"):
		return ""
	chunks = code.split("-")
	return chunks[1] if len(chunks) >= 3 else ""
