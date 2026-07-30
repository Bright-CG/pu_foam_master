# Copyright (c) 2026, Happifoam and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cint, flt, nowdate

from pu_foam_master.pufm_manufacturing.utils.settings import get_formula_factor

CONSUMABLE_SETTINGS = (
	("default_tape_edge_item", "Default Tape Edge Item"),
	("default_pvc_nylon_item", "Default PVC/Nylon Item"),
	("default_thread_item", "Default Thread Item"),
	("default_label_item", "Default Label Item"),
)


class MattressProductionEntry(Document):
	def validate(self):
		if not self.company:
			frappe.throw("Company is required.")
		if not self.processed_by:
			self.processed_by = frappe.session.user
		if not self.source_warehouse:
			frappe.throw("Source/WIP Warehouse is required.")
		if not self.target_warehouse:
			frappe.throw("Target/FG Warehouse is required.")
		self._calculate_rows()

	def before_submit(self):
		self._calculate_rows()
		_require_mattress_consumable_settings()

	def on_submit(self):
		entry = self._create_manufacture_stock_entry()
		self.db_set("stock_entry", entry.name, update_modified=False)
		self._sync_job_order_on_submit()
		self._sync_job_order_operator(self.processed_by)

	def on_cancel(self):
		if self.stock_entry and frappe.db.exists("Stock Entry", self.stock_entry):
			se = frappe.get_doc("Stock Entry", self.stock_entry)
			if se.docstatus == 1:
				se.cancel()
		self._sync_job_order_on_cancel()
		self._sync_job_order_operator(None)

	def _sync_job_order_operator(self, user):
		if not self.job_order:
			return
		if not frappe.db.exists("Pufm Job Order", self.job_order):
			return
		frappe.db.set_value("Pufm Job Order", self.job_order, "assembled_by", user)

	def _sync_job_order_on_submit(self):
		if not self.job_order:
			return
		if not frappe.db.exists("Pufm Job Order", self.job_order):
			return
		from pu_foam_master.pufm_manufacturing.doctype.pufm_job_order.pufm_job_order import (
			sync_job_order_status,
		)

		sync_job_order_status(self.job_order, "Completed")

	def _sync_job_order_on_cancel(self):
		if not self.job_order:
			return
		if not frappe.db.exists("Pufm Job Order", self.job_order):
			return
		from pu_foam_master.pufm_manufacturing.doctype.pufm_job_order.pufm_job_order import (
			sync_job_order_status,
		)

		sync_job_order_status(self.job_order, "Pending Assembly")

	def _calculate_rows(self):
		settings = frappe.get_single("Pufm Manufacturing Settings")
		for row in self.production_items or []:
			costs = _row_cost_breakdown(row, settings)
			row.total_row_cost = costs["total_row_cost"]

	def _create_manufacture_stock_entry(self):
		settings = _require_mattress_consumable_settings()
		rm_warehouse = settings.default_raw_material_warehouse

		entry = frappe.new_doc("Stock Entry")
		entry.company = self.company
		entry.stock_entry_type = "Manufacture"
		entry.purpose = "Manufacture"
		entry.posting_date = self.posting_date
		entry.set_posting_time = 1

		for row in self.production_items or []:
			costs = _row_cost_breakdown(row, settings)
			core_item = _get_batch_item(row.core_batch)
			fabric_item = row.fabric_item or _get_batch_item(row.fabric_batch)

			core_doc = frappe.get_cached_doc("Item", core_item)
			fabric_doc = frappe.get_cached_doc("Item", fabric_item)
			mattress_doc = frappe.get_cached_doc("Item", row.mattress_item)

			# --- Source: Core ---
			entry.append(
				"items",
				{
					"item_code": core_item,
					"s_warehouse": self.source_warehouse,
					"batch_no": row.core_batch,
					"qty": flt(row.qty),
					"uom": core_doc.stock_uom,
					"stock_uom": core_doc.stock_uom,
					"conversion_factor": 1,
					"basic_rate": costs["core_rate"],
					"valuation_rate": costs["core_rate"],
					"set_basic_rate_manually": 1,
					"allow_zero_valuation_rate": 1 if costs["core_rate"] <= 0 else 0,
					"use_serial_batch_fields": 1,
				},
			)

			# --- Source: Fabric ---
			entry.append(
				"items",
				{
					"item_code": fabric_item,
					"s_warehouse": self.source_warehouse,
					"batch_no": row.fabric_batch,
					"qty": costs["fabric_meters"],
					"uom": fabric_doc.stock_uom or "Meter",
					"stock_uom": fabric_doc.stock_uom or "Meter",
					"conversion_factor": 1,
					"basic_rate": costs["fabric_rate"],
					"valuation_rate": costs["fabric_rate"],
					"set_basic_rate_manually": 1,
					"allow_zero_valuation_rate": 1 if costs["fabric_rate"] <= 0 else 0,
					"use_serial_batch_fields": 1,
				},
			)

			# --- Source: Tape / PVC / Thread / Labels (physical stock backflush) ---
			for consumable in costs["consumables"]:
				item_doc = frappe.get_cached_doc("Item", consumable["item_code"])
				entry.append(
					"items",
					{
						"item_code": consumable["item_code"],
						"s_warehouse": rm_warehouse,
						"qty": consumable["qty"],
						"uom": item_doc.stock_uom,
						"stock_uom": item_doc.stock_uom,
						"conversion_factor": 1,
						"basic_rate": consumable["rate"],
						"valuation_rate": consumable["rate"],
						"set_basic_rate_manually": 1,
						"allow_zero_valuation_rate": 1 if consumable["rate"] <= 0 else 0,
					},
				)

			unit_rate = (
				flt(costs["stocked_cost"]) / flt(row.qty) if flt(row.qty) else 0
			)

			qty = flt(row.qty)
			has_serial = cint(mattress_doc.has_serial_no)
			has_batch = cint(mattress_doc.has_batch_no)
			if has_serial:
				serial_qty = cint(qty)
				if serial_qty <= 0 or abs(qty - serial_qty) > 0.0001:
					frappe.throw(
						"Quantity for {0} must be a whole number to generate serial numbers "
						"(got {1}).".format(row.mattress_item, qty)
					)

			batch_id = None
			if has_batch:
				batch_id = self._ensure_output_batch(row.mattress_item, row.idx)

			serial_string = None
			if has_serial:
				serial_string = self._build_output_serials(
					row.mattress_item, cint(qty), row.idx, batch_id
				)

			target_row = {
				"item_code": row.mattress_item,
				"t_warehouse": self.target_warehouse,
				"qty": qty,
				"uom": mattress_doc.stock_uom,
				"stock_uom": mattress_doc.stock_uom,
				"conversion_factor": 1,
				"basic_rate": unit_rate,
				"valuation_rate": unit_rate,
				"set_basic_rate_manually": 1,
				"allow_zero_valuation_rate": 1 if unit_rate <= 0 else 0,
				"is_finished_item": 1,
				"use_serial_batch_fields": 1,
			}
			if batch_id:
				target_row["batch_no"] = batch_id
			if serial_string:
				target_row["serial_no"] = serial_string

			entry.append("items", target_row)

		entry.insert(ignore_permissions=True)
		entry.submit()
		return entry

	def _ensure_output_batch(self, item_code, row_idx):
		batch_id = f"{self.name}-{item_code}-{row_idx}"
		if not frappe.db.exists("Batch", batch_id):
			new_batch = frappe.new_doc("Batch")
			new_batch.batch_id = batch_id
			new_batch.item = item_code
			new_batch.reference_doctype = "Mattress Production Entry"
			new_batch.reference_name = self.name
			new_batch.insert(ignore_permissions=True)
		return batch_id

	def _build_output_serials(self, item_code, qty, row_idx, batch_id=None):
		"""Warranty serials: MAT-YYYYMMDD-{row}-{n}-{hash} (unique)."""
		prefix = f"MAT-{nowdate().replace('-', '')}-{row_idx}"
		serial_nos = []
		for i in range(1, cint(qty) + 1):
			unique_hash = frappe.generate_hash(length=4).upper()
			if batch_id:
				serial_nos.append(f"{batch_id}-{i}-{unique_hash}")
			else:
				serial_nos.append(f"{prefix}-{i}-{unique_hash}")
		return "\n".join(serial_nos)


def _require_mattress_consumable_settings(settings=None):
	"""Ensure Settings Links for stocked mattress consumables + RM warehouse."""
	settings = settings or frappe.get_single("Pufm Manufacturing Settings")
	missing = []

	if not settings.default_raw_material_warehouse:
		missing.append("Default Raw Material Warehouse")
	elif not frappe.db.exists("Warehouse", settings.default_raw_material_warehouse):
		missing.append("Default Raw Material Warehouse (invalid)")

	for fieldname, label in CONSUMABLE_SETTINGS:
		item_code = getattr(settings, fieldname, None)
		if not item_code or not frappe.db.exists("Item", item_code):
			missing.append(label)

	if missing:
		frappe.throw(
			"Configure the following in Pufm Manufacturing Settings before submitting "
			"Mattress Production: {0}.".format(", ".join(missing))
		)
	return settings


def _row_cost_breakdown(row, settings):
	"""All mattress consumables are physical stock — no absorption path."""
	if flt(row.qty) <= 0:
		frappe.throw(f"Row {row.idx}: Quantity must be greater than zero.")

	item = frappe.get_cached_doc("Item", row.mattress_item)
	length = flt(item.custom_length)
	width = flt(item.custom_width)
	height = flt(item.custom_height)
	if not (length and width and height):
		frappe.throw(f"Row {row.idx}: Mattress item dimensions are missing.")

	inches_per_meter = get_formula_factor("inches_per_meter", settings)
	tape_meters = _tape_edge_meters(length, width, row.qty, settings)

	pvc_divisor = get_formula_factor("pvc_nylon_divisor", settings)
	pvc_faces = get_formula_factor("pvc_nylon_faces", settings)
	pvc_sqm = ((length * width * pvc_faces) / pvc_divisor) * flt(row.qty)

	thread_qty = get_formula_factor("thread_qty_per_mattress", settings) * flt(row.qty)
	label_qty = get_formula_factor("label_qty_per_mattress", settings) * flt(row.qty)

	fabric_width_inches = _resolve_fabric_width(row.fabric_item, settings)
	panel_faces = get_formula_factor("fabric_panel_faces", settings)
	side_factor = get_formula_factor("fabric_side_panels_factor", settings)
	total_area = (panel_faces * (length * width)) + ((side_factor * (length + width)) * height)
	total_area = total_area * (1 + (flt(settings.fabric_waste_factor) / 100))
	fabric_meters = (total_area / (fabric_width_inches * inches_per_meter)) * flt(row.qty)

	core_rate = _get_batch_valuation_rate(row.core_batch)
	fabric_rate = _get_batch_valuation_rate(row.fabric_batch)
	core_cost = flt(row.qty) * core_rate
	fabric_cost = fabric_meters * fabric_rate

	rm_wh = getattr(settings, "default_raw_material_warehouse", None)
	consumables = []
	consumable_specs = (
		(settings.default_tape_edge_item, tape_meters),
		(settings.default_pvc_nylon_item, pvc_sqm),
		(settings.default_thread_item, thread_qty),
		(settings.default_label_item, label_qty),
	)
	consumable_cost = 0.0
	for item_code, qty in consumable_specs:
		if not item_code or flt(qty) <= 0:
			continue
		rate = _get_item_valuation_rate(item_code, rm_wh)
		if rate <= 0:
			frappe.throw(
				"Valuation rate missing for mattress consumable {0} in warehouse {1}. "
				"Receive stock (or set Item valuation rate) before submitting.".format(
					item_code, rm_wh or "(no Raw Material Warehouse)"
				)
			)
		consumables.append({"item_code": item_code, "qty": flt(qty), "rate": rate})
		consumable_cost += flt(qty) * rate

	stocked_cost = core_cost + fabric_cost + consumable_cost

	return {
		"tape_meters": tape_meters,
		"fabric_meters": fabric_meters,
		"core_rate": core_rate,
		"fabric_rate": fabric_rate,
		"core_cost": core_cost,
		"fabric_cost": fabric_cost,
		"consumables": consumables,
		"stocked_cost": stocked_cost,
		"absorption_cost": 0.0,
		"total_row_cost": stocked_cost,
	}


def _tape_edge_meters(length_inches, width_inches, qty, settings=None):
	"""
	Tape edge consumption in meters.
	Default: two full perimeters (top + bottom edge) via perimeter multiplier.
	"""
	settings = settings or frappe.get_single("Pufm Manufacturing Settings")
	multiplier = get_formula_factor("tape_edge_perimeter_multiplier", settings)
	inches_per_meter = get_formula_factor("inches_per_meter", settings)
	waste_pct = flt(getattr(settings, "tape_edge_waste_percentage", None))
	if waste_pct < 0:
		waste_pct = 0

	inches = multiplier * (flt(length_inches) + flt(width_inches))
	meters = (inches / inches_per_meter) * flt(qty)
	return meters * (1 + (waste_pct / 100.0))


def _get_item_valuation_rate(item_code, warehouse=None):
	"""Prefer Bin rate at RM warehouse, then Item valuation_rate."""
	if item_code and warehouse:
		rate = flt(
			frappe.db.get_value(
				"Bin",
				{"item_code": item_code, "warehouse": warehouse},
				"valuation_rate",
			)
		)
		if rate > 0:
			return rate

	if item_code:
		rate = flt(frappe.db.get_value("Item", item_code, "valuation_rate"))
		if rate > 0:
			return rate

	return 0.0


def _resolve_fabric_width(item_code, settings=None):
	fallback = get_formula_factor("default_fabric_width_inches", settings)
	if not item_code:
		return fallback
	width = flt(frappe.db.get_value("Item", item_code, "custom_width"))
	return width or fallback


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


@frappe.whitelist()
def get_allowed_fabric_items_for_mattress(mattress_item):
	"""Resolve fabrics from the mattress Item's native Brand policy."""
	if not mattress_item:
		return []

	item_brand = frappe.db.get_value("Item", mattress_item, "brand")
	if not item_brand:
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
