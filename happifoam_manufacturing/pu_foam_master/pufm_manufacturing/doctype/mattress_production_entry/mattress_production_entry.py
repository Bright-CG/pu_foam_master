# Copyright (c) 2026, Happifoam and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cint, flt, nowdate

# Inches per meter (divide inches by this to get meters)
INCH_TO_METER = 39.37
TAPE_EDGE_ITEM = "Tape Edge"


class MattressProductionEntry(Document):
	def validate(self):
		if not self.company:
			frappe.throw("Company is required.")
		if not self.source_warehouse:
			frappe.throw("Source/WIP Warehouse is required.")
		if not self.target_warehouse:
			frappe.throw("Target/FG Warehouse is required.")
		self._calculate_rows()

	def before_submit(self):
		self._calculate_rows()

	def on_submit(self):
		entry = self._create_repack_stock_entry()
		self.db_set("stock_entry", entry.name, update_modified=False)

	def _calculate_rows(self):
		settings = frappe.get_single("Pufm Manufacturing Settings")
		tape_item = _resolve_tape_edge_item()
		tape_rate = _get_tape_edge_rate(settings)

		for row in self.production_items or []:
			costs = _row_cost_breakdown(row, settings, tape_item, tape_rate)
			row.total_row_cost = costs["total_row_cost"]

	def _create_repack_stock_entry(self):
		settings = frappe.get_single("Pufm Manufacturing Settings")
		tape_item = _resolve_tape_edge_item()
		tape_doc = frappe.get_cached_doc("Item", tape_item) if tape_item else None
		tape_uom = (tape_doc.stock_uom if tape_doc else None) or "Meter"
		tape_rate = _get_tape_edge_rate(settings)
		absorption_account = getattr(settings, "consumables_absorption_account", None)

		entry = frappe.new_doc("Stock Entry")
		entry.company = self.company
		entry.stock_entry_type = "Repack"
		entry.purpose = "Repack"
		entry.posting_date = self.posting_date
		entry.set_posting_time = 1

		total_absorption_cost = 0.0

		for row in self.production_items or []:
			costs = _row_cost_breakdown(row, settings, tape_item, tape_rate)
			fabric_meters = costs["fabric_meters"]
			tape_meters = costs["tape_meters"]
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
					"qty": fabric_meters,
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

			# --- Source: Tape Edge (physical stock only when Item exists) ---
			if tape_item and flt(tape_meters) > 0:
				entry.append(
					"items",
					{
						"item_code": tape_item,
						"s_warehouse": self.source_warehouse,
						"qty": tape_meters,
						"uom": tape_uom,
						"stock_uom": tape_uom,
						"conversion_factor": 1,
						"basic_rate": tape_rate,
						"valuation_rate": tape_rate,
						"set_basic_rate_manually": 1,
						"allow_zero_valuation_rate": 1 if tape_rate <= 0 else 0,
					},
				)

			total_absorption_cost += flt(costs["absorption_cost"])

			# FG rate from stocked materials only; absorption covers non-stocked consumables
			stocked_cost = flt(costs["stocked_cost"])
			unit_rate = stocked_cost / flt(row.qty) if flt(row.qty) else 0

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

		if total_absorption_cost > 0:
			if not absorption_account:
				frappe.throw(
					"Set Consumables Absorption Account in Pufm Manufacturing Settings "
					"to post non-stocked mattress consumable costs."
				)
			entry.append(
				"additional_costs",
				{
					"expense_account": absorption_account,
					"description": "Mattress consumables for {0}".format(self.name),
					"amount": total_absorption_cost,
				},
			)

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


def _row_cost_breakdown(row, settings, tape_item, tape_rate):
	"""Split stocked material cost vs absorption (non-stocked consumables)."""
	if flt(row.qty) <= 0:
		frappe.throw(f"Row {row.idx}: Quantity must be greater than zero.")

	item = frappe.get_cached_doc("Item", row.mattress_item)
	length = flt(item.custom_length)
	width = flt(item.custom_width)
	height = flt(item.custom_height)
	if not (length and width and height):
		frappe.throw(f"Row {row.idx}: Mattress item dimensions are missing.")

	tape_meters = _tape_edge_meters(length, width, row.qty)
	tape_cost = tape_meters * flt(tape_rate)

	pvc_usage = (length * width) / 1550
	pvc_cost = pvc_usage * flt(row.qty) * flt(settings.pvc_rate_per_sqm)
	thread_label_cost = (
		flt(settings.thread_rate_per_mat) + flt(settings.label_rate_per_pc)
	) * flt(row.qty)

	fabric_width_inches = _resolve_fabric_width(row.fabric_item)
	total_area = (2 * (length * width)) + ((2 * (length + width)) * height)
	total_area = total_area * (1 + (flt(settings.fabric_waste_factor) / 100))
	fabric_meters = (total_area / (fabric_width_inches * INCH_TO_METER)) * flt(row.qty)

	core_rate = _get_batch_valuation_rate(row.core_batch)
	fabric_rate = _get_batch_valuation_rate(row.fabric_batch)
	core_cost = flt(row.qty) * core_rate
	fabric_cost = fabric_meters * fabric_rate

	# Tape is stocked only when Tape Edge Item exists; otherwise absorb via account
	stocked_tape = flt(tape_cost) if tape_item else 0.0
	absorbed_tape = 0.0 if tape_item else flt(tape_cost)
	absorption_cost = pvc_cost + thread_label_cost + absorbed_tape
	stocked_cost = core_cost + fabric_cost + stocked_tape
	total_row_cost = stocked_cost + absorption_cost

	return {
		"tape_meters": tape_meters,
		"fabric_meters": fabric_meters,
		"core_rate": core_rate,
		"fabric_rate": fabric_rate,
		"core_cost": core_cost,
		"fabric_cost": fabric_cost,
		"tape_cost": tape_cost,
		"pvc_cost": pvc_cost,
		"thread_label_cost": thread_label_cost,
		"stocked_cost": stocked_cost,
		"absorption_cost": absorption_cost,
		"total_row_cost": total_row_cost,
	}


def _tape_edge_meters(length_inches, width_inches, qty):
	"""
	Tape edge consumption in meters.
	Two full perimeters (top + bottom edge): 4 * (L + W) inches -> meters.
	"""
	inches = 4.0 * (flt(length_inches) + flt(width_inches))
	return (inches / INCH_TO_METER) * flt(qty)


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
