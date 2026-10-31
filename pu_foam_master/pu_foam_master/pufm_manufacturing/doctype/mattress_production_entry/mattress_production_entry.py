# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cint, flt, nowdate

from pu_foam_master.pufm_manufacturing.utils.approval_workflows import (
	assert_deletable_before_supervisor_approval,
)
from pu_foam_master.pufm_manufacturing.utils.settings import (
	get_formula_factor,
	get_usage_allowance_percent,
)
from pu_foam_master.pufm_manufacturing.utils.stock_entry_valuation import (
	apply_manual_rate,
	finalize_pufm_stock_entry_balance,
	get_stock_valuation_rate,
)

CONSUMABLE_SETTINGS = (
	("default_tape_edge_item", "Default Tape Edge Item"),
	("default_pvc_nylon_item", "Default PVC/Nylon Item"),
	("default_thread_item", "Default Thread Item"),
)

LABEL_ITEM_GROUP = "Labels"


class MattressProductionEntry(Document):
	def on_trash(self):
		assert_deletable_before_supervisor_approval(self)

	def validate(self):
		if not self.company:
			frappe.throw("Company is required.")
		if not self.processed_by:
			self.processed_by = frappe.session.user
		if not self.source_warehouse:
			frappe.throw("Source/WIP Warehouse is required.")
		if not self.target_warehouse:
			frappe.throw("Target/FG Warehouse is required.")
		self._validate_job_order_type()
		if self._action == "submit":
			self._validate_core_conversion_link()
		if self._action == "submit":
			self._preflight_all_rows_before_posting()
		else:
			self._throw_if_errors(self._collect_row_field_errors())
			self._calculate_rows()

	def _validate_job_order_type(self):
		if not self.job_order:
			return
		order_type = frappe.db.get_value("Pufm Job Order", self.job_order, "order_type")
		if order_type and order_type not in ("Mattress", "Quilting"):
			frappe.throw(
				"Job Order {0} is type {1}. Mattress Production accepts Mattress or Quilting Job Orders only.".format(
					self.job_order, order_type
				)
			)

	def _validate_core_conversion_link(self):
		if not self.job_order:
			return
		order_type = frappe.db.get_value("Pufm Job Order", self.job_order, "order_type")
		if order_type == "Quilting":
			if not self.core_conversion:
				frappe.throw(
					"Core Conversion is required when assembling from a Quilting Job Order."
				)
			if not frappe.db.exists("Mattress Core Conversion", self.core_conversion):
				frappe.throw("Core Conversion {0} was not found.".format(self.core_conversion))
			conv = frappe.db.get_value(
				"Mattress Core Conversion",
				self.core_conversion,
				["job_order", "docstatus"],
				as_dict=True,
			)
			if not conv or conv.job_order != self.job_order:
				frappe.throw(
					"Core Conversion {0} does not belong to Job Order {1}.".format(
						self.core_conversion, self.job_order
					)
				)
			if cint(conv.docstatus) != 1:
				frappe.throw(
					"Core Conversion {0} must be submitted before assembly.".format(
						self.core_conversion
					)
				)
		elif self.core_conversion:
			frappe.throw(
				"Core Conversion is only used with Quilting Job Orders. Clear it or select a Quilting Job Order."
			)

	def before_submit(self):
		self._preflight_all_rows_before_posting()

	def on_submit(self):
		entries = self._create_manufacture_stock_entries()
		self.db_set("stock_entry", entries[0] if entries else None, update_modified=False)
		self.db_set("stock_entries", ",".join(entries), update_modified=False)
		self._sync_job_order_on_submit()
		self._sync_job_order_operator(self.processed_by)

	def on_cancel(self):
		for se_name in self._linked_stock_entry_names():
			if frappe.db.exists("Stock Entry", se_name):
				se = frappe.get_doc("Stock Entry", se_name)
				if se.docstatus == 1:
					se.cancel()
		self._sync_job_order_on_cancel()
		self._sync_job_order_operator(None)

	def _linked_stock_entry_names(self):
		names = []
		for raw in (self.get("stock_entries") or "").split(","):
			name = raw.strip()
			if name and name not in names:
				names.append(name)
		if self.stock_entry and self.stock_entry not in names:
			names.append(self.stock_entry)
		return names

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
			reconcile_job_order_workflow,
		)

		reconcile_job_order_workflow(self.job_order)

	def _sync_job_order_on_cancel(self):
		if not self.job_order:
			return
		if not frappe.db.exists("Pufm Job Order", self.job_order):
			return
		from pu_foam_master.pufm_manufacturing.doctype.pufm_job_order.pufm_job_order import (
			reconcile_job_order_workflow,
		)

		reconcile_job_order_workflow(self.job_order)

	def _collect_row_field_errors(self):
		errors = []
		for row in self.production_items or []:
			row.finish_type = _row_finish_type(row)
			errors.extend(_row_field_errors(row, core_conversion=self.core_conversion))
		return errors

	def _preflight_all_rows_before_posting(self):
		"""Validate every row (and settings) before any Stock Entry is created."""
		if not self.production_items:
			frappe.throw("Add at least one Production Item row before submitting.")

		settings = frappe.get_single("Pufm Manufacturing Settings")
		field_errors = self._collect_row_field_errors()
		setting_errors = _mattress_consumable_setting_errors(settings)
		errors = list(field_errors)
		errors.extend(setting_errors)
		errors.extend(_assembly_absorption_errors(settings))

		settings_ok = not setting_errors
		for row in self.production_items:
			if any(e.startswith("Row {0}:".format(row.idx)) for e in field_errors):
				continue
			if not settings_ok:
				continue
			errors.extend(
				_row_posting_errors(row, settings, source_warehouse=self.source_warehouse)
			)

		self._throw_if_errors(errors)
		return settings

	def _throw_if_errors(self, errors):
		if not errors:
			return
		frappe.throw(
			"Cannot continue until these issues are fixed:\n\n- " + "\n- ".join(errors),
			title="Mattress Production validation failed",
		)

	def _calculate_rows(self):
		settings = frappe.get_single("Pufm Manufacturing Settings")
		for row in self.production_items or []:
			try:
				costs = _row_cost_breakdown(row, settings, source_warehouse=self.source_warehouse)
				row.total_row_cost = costs["total_row_cost"]
			except Exception:
				row.total_row_cost = 0

	def _create_manufacture_stock_entries(self):
		"""One Manufacture SE per production row (ERPNext allows only one finished Item)."""
		settings = self._preflight_all_rows_before_posting()
		drafts = []
		build_errors = []
		for row in self.production_items:
			try:
				drafts.append(self._build_row_manufacture_entry(row, settings))
			except Exception as exc:
				build_errors.append(_exc_message(exc))
		self._throw_if_errors(build_errors)

		submitted = []
		try:
			for entry in drafts:
				entry.insert(ignore_permissions=True)
				submitted.append(entry.name)
				entry.submit()
		except Exception:
			self._rollback_submitted_stock_entries(submitted)
			raise
		return submitted

	def _rollback_submitted_stock_entries(self, names):
		"""Undo any Stock Entries posted in this attempt so a retry cannot double-issue FG."""
		for se_name in reversed(names or []):
			try:
				if not se_name or not frappe.db.exists("Stock Entry", se_name):
					continue
				se = frappe.get_doc("Stock Entry", se_name)
				if se.docstatus == 1:
					se.cancel()
				elif se.docstatus == 0:
					se.delete()
			except Exception:
				frappe.log_error(
					frappe.get_traceback(),
					"Mattress Production SE rollback failed: {0}".format(se_name),
				)

	def _build_row_manufacture_entry(self, row, settings):
		rm_warehouse = settings.default_raw_material_warehouse
		entry = frappe.new_doc("Stock Entry")
		entry.company = self.company
		entry.stock_entry_type = "Manufacture"
		entry.purpose = "Manufacture"
		entry.posting_date = self.posting_date
		entry.set_posting_time = 1
		entry.remarks = "Mattress Production Entry {0} row {1}".format(self.name, row.idx)

		costs = _row_cost_breakdown(row, settings, source_warehouse=self.source_warehouse)
		core_item = _get_batch_item(row.core_batch)
		fabric_item = row.fabric_item or _get_batch_item(row.fabric_batch)

		core_doc = frappe.get_cached_doc("Item", core_item)
		fabric_doc = frappe.get_cached_doc("Item", fabric_item)
		mattress_doc = frappe.get_cached_doc("Item", row.mattress_item)

		core_row = {
			"item_code": core_item,
			"s_warehouse": self.source_warehouse,
			"batch_no": row.core_batch,
			"qty": flt(row.qty),
			"uom": core_doc.stock_uom,
			"stock_uom": core_doc.stock_uom,
			"conversion_factor": 1,
			"use_serial_batch_fields": 1,
		}
		apply_manual_rate(core_row, costs["core_rate"])
		entry.append("items", core_row)

		fabric_row = {
			"item_code": fabric_item,
			"s_warehouse": self.source_warehouse,
			"batch_no": row.fabric_batch,
			"qty": costs["fabric_meters"],
			"uom": fabric_doc.stock_uom or "Meter",
			"stock_uom": fabric_doc.stock_uom or "Meter",
			"conversion_factor": 1,
			"use_serial_batch_fields": 1,
		}
		apply_manual_rate(fabric_row, costs["fabric_rate"])
		entry.append("items", fabric_row)

		if flt(costs.get("side_fabric_meters")) > 0:
			side_item = row.side_fabric_item or _get_batch_item(row.side_fabric_batch)
			side_doc = frappe.get_cached_doc("Item", side_item)
			side_row = {
				"item_code": side_item,
				"s_warehouse": self.source_warehouse,
				"batch_no": row.side_fabric_batch,
				"qty": costs["side_fabric_meters"],
				"uom": side_doc.stock_uom or "Meter",
				"stock_uom": side_doc.stock_uom or "Meter",
				"conversion_factor": 1,
				"use_serial_batch_fields": 1,
			}
			apply_manual_rate(side_row, costs["side_fabric_rate"])
			entry.append("items", side_row)

		for consumable in costs["consumables"]:
			item_doc = frappe.get_cached_doc("Item", consumable["item_code"])
			cons_row = {
				"item_code": consumable["item_code"],
				"s_warehouse": rm_warehouse,
				"qty": consumable["qty"],
				"uom": item_doc.stock_uom,
				"stock_uom": item_doc.stock_uom,
				"conversion_factor": 1,
			}
			apply_manual_rate(cons_row, consumable["rate"])
			entry.append("items", cons_row)

		# Materials only in FG basic rate; labour/depr via additional_costs then balance.
		unit_rate = flt(costs["stocked_cost"]) / flt(row.qty) if flt(row.qty) else 0
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
			"is_finished_item": 1,
			"use_serial_batch_fields": 1,
		}
		apply_manual_rate(target_row, unit_rate)
		if batch_id:
			target_row["batch_no"] = batch_id
		if serial_string:
			target_row["serial_no"] = serial_string

		entry.append("items", target_row)
		self._append_mattress_depreciation_cost(entry, settings, qty)
		self._append_mattress_labour_cost(entry, settings, qty, row.idx)
		finalize_pufm_stock_entry_balance(
			entry,
			context="Mattress Production {0} row {1}".format(self.name, row.idx),
		)
		return entry

	def _append_mattress_depreciation_cost(self, entry, settings, qty):
		rate = flt(getattr(settings, "mattress_depreciation_per_pc", 0) or 0)
		amount = rate * flt(qty)
		if amount <= 0:
			return
		account = getattr(settings, "depreciation_absorption_account", None)
		if not account:
			frappe.throw(
				"Set Depreciation Absorption Account in Pufm Manufacturing Settings "
				"to post mattress depreciation."
			)
		entry.append(
			"additional_costs",
			{
				"expense_account": account,
				"description": "Mattress Depreciation for {0}".format(self.name),
				"amount": amount,
			},
		)

	def _append_mattress_labour_cost(self, entry, settings, qty, row_idx):
		rate = flt(getattr(settings, "mattress_labour_per_pc", 0) or 0)
		amount = rate * flt(qty)
		if amount <= 0:
			return
		account = getattr(settings, "mattress_labour_absorption_account", None)
		if not account:
			frappe.throw(
				"Set Mattress Labour Absorption Account in Pufm Manufacturing Settings "
				"to post assembly labour."
			)
		entry.append(
			"additional_costs",
			{
				"expense_account": account,
				"description": "Mattress Assembly Labour for {0} row {1}".format(
					self.name, row_idx
				),
				"amount": amount,
			},
		)

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


def _mattress_consumable_setting_errors(settings=None):
	"""Return missing Settings Links for stocked mattress consumables + RM warehouse."""
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

	if not missing:
		return []
	return [
		"Configure the following in Pufm Manufacturing Settings before submitting "
		"Mattress Production: {0}.".format(", ".join(missing))
	]


def _require_mattress_consumable_settings(settings=None):
	settings = settings or frappe.get_single("Pufm Manufacturing Settings")
	errors = _mattress_consumable_setting_errors(settings)
	if errors:
		frappe.throw(errors[0])
	return settings


def _assembly_absorption_errors(settings):
	errors = []
	if flt(getattr(settings, "mattress_depreciation_per_pc", 0) or 0) > 0 and not getattr(
		settings, "depreciation_absorption_account", None
	):
		errors.append(
			"Set Depreciation Absorption Account in Pufm Manufacturing Settings "
			"because Mattress Depreciation per Piece is greater than zero."
		)
	if flt(getattr(settings, "mattress_labour_per_pc", 0) or 0) > 0 and not getattr(
		settings, "mattress_labour_absorption_account", None
	):
		errors.append(
			"Set Mattress Labour Absorption Account in Pufm Manufacturing Settings "
			"because Labor per Mattress is greater than zero."
		)
	return errors


def _row_field_errors(row, core_conversion=None):
	errors = []
	prefix = "Row {0}".format(row.idx)
	if not row.mattress_item:
		errors.append("{0}: Mattress Item is required.".format(prefix))
	if flt(row.qty) <= 0:
		errors.append("{0}: Quantity must be greater than zero.".format(prefix))
	if not row.core_batch:
		errors.append("{0}: Core Batch is required.".format(prefix))
	elif not _get_batch_item(row.core_batch):
		errors.append("{0}: Core Batch {1} was not found.".format(prefix, row.core_batch))
	else:
		try:
			from pu_foam_master.pufm_manufacturing.utils.item_cbm import (
				batch_belongs_to_conversion,
				validate_core_batch_for_mattress,
			)

			validate_core_batch_for_mattress(
				row.mattress_item, row.core_batch, row_label=prefix
			)
			if core_conversion and not batch_belongs_to_conversion(
				row.core_batch, core_conversion
			):
				errors.append(
					"{0}: Core Batch {1} was not produced by Core Conversion {2}.".format(
						prefix, row.core_batch, core_conversion
					)
				)
		except Exception as exc:
			errors.append(_exc_message(exc))
	if not row.fabric_item:
		errors.append("{0}: Fabric Item is required.".format(prefix))
	if not row.fabric_batch:
		errors.append("{0}: Fabric Batch is required.".format(prefix))
	elif not _get_batch_item(row.fabric_batch):
		errors.append("{0}: Fabric Batch {1} was not found.".format(prefix, row.fabric_batch))

	errors.extend(_label_item_errors(row))
	errors.extend(_quilted_fabric_requirement_errors(row))

	if row.fabric_item and row.fabric_batch:
		batch_item = _get_batch_item(row.fabric_batch)
		if batch_item and batch_item != row.fabric_item:
			errors.append(
				"{0}: Fabric Batch {1} belongs to {2}, not {3}.".format(
					prefix, row.fabric_batch, batch_item, row.fabric_item
				)
			)

	if not _is_side_quilted_row(row):
		row.side_fabric_item = None
		row.side_fabric_batch = None
		return errors

	if not row.side_fabric_item or not row.side_fabric_batch:
		errors.append(
			"{0}: The mattress '{1}' is Side Quilted. "
			"You must select a Side Fabric and Batch.".format(prefix, row.mattress_item)
		)
		return errors

	if row.side_fabric_item == row.fabric_item:
		errors.append(
			"{0}: Side Fabric Item must be different from the face Fabric Item.".format(prefix)
		)
	batch_item = _get_batch_item(row.side_fabric_batch)
	if batch_item and batch_item != row.side_fabric_item:
		errors.append(
			"{0}: Side Fabric Batch {1} belongs to {2}, not {3}.".format(
				prefix, row.side_fabric_batch, batch_item, row.side_fabric_item
			)
		)
	return errors


def _row_posting_errors(row, settings, source_warehouse=None):
	errors = []
	prefix = "Row {0}".format(row.idx)
	if not row.mattress_item:
		return errors

	if not frappe.db.exists("Item", row.mattress_item):
		errors.append("{0}: Mattress Item {1} does not exist.".format(prefix, row.mattress_item))
		return errors

	item = frappe.get_cached_doc("Item", row.mattress_item)
	if not (flt(item.custom_length) and flt(item.custom_width) and flt(item.custom_height)):
		errors.append("{0}: Mattress item dimensions are missing.".format(prefix))
	if not _row_finish_type(row):
		errors.append(
			"{0}: Mattress {1} has no Finish Type. Set Item Finish Type before assembling.".format(
				prefix, row.mattress_item
			)
		)

	qty = flt(row.qty)
	if cint(item.has_serial_no):
		serial_qty = cint(qty)
		if serial_qty <= 0 or abs(qty - serial_qty) > 0.0001:
			errors.append(
				"{0}: Quantity for {1} must be a whole number to generate serial numbers "
				"(got {2}).".format(prefix, row.mattress_item, qty)
			)

	if errors:
		return errors

	try:
		costs = _row_cost_breakdown(row, settings, source_warehouse=source_warehouse)
		row.total_row_cost = costs["total_row_cost"]
		errors.extend(_quilted_fabric_stock_errors(row, costs, source_warehouse))
	except Exception as exc:
		msg = _exc_message(exc)
		if not msg.startswith("Row "):
			msg = "{0}: {1}".format(prefix, msg)
		errors.append(msg)
	return errors


def _label_item_errors(row):
	errors = []
	prefix = "Row {0}".format(row.idx)
	label_item = (row.get("label_item") or "").strip()
	if not label_item:
		errors.append("{0}: Label Item is required.".format(prefix))
		return errors

	if not frappe.db.exists("Item", label_item):
		errors.append("{0}: Label Item {1} does not exist.".format(prefix, label_item))
		return errors

	item = frappe.get_cached_doc("Item", label_item)
	if cint(item.disabled):
		errors.append("{0}: Label Item {1} is disabled.".format(prefix, label_item))
	if frappe.db.exists("Item Group", LABEL_ITEM_GROUP) and item.item_group != LABEL_ITEM_GROUP:
		errors.append(
			"{0}: Label Item {1} must belong to Item Group '{2}'.".format(
				prefix, label_item, LABEL_ITEM_GROUP
			)
		)
	if cint(item.has_batch_no):
		errors.append(
			"{0}: Label Item {1} is batch-tracked. Use a non-batch Labels Item "
			"so assembly can consume FIFO without a batch.".format(prefix, label_item)
		)
	if cint(item.has_serial_no):
		errors.append(
			"{0}: Label Item {1} is serial-tracked. Labels must not use serial numbers.".format(
				prefix, label_item
			)
		)
	return errors


def _exc_message(exc):
	msg = getattr(exc, "message", None) or str(exc)
	return str(msg).replace("<br>", "\n").strip()


def _row_cost_breakdown(row, settings, source_warehouse=None):
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
	pvc_kg = _pvc_kg(length, width, height, row.qty, settings, row_idx=row.idx)

	thread_qty = get_formula_factor("thread_qty_per_mattress", settings) * flt(row.qty)
	label_qty = get_formula_factor("label_qty_per_mattress", settings) * flt(row.qty)

	face_area, side_area = _fabric_panel_areas(length, width, height, settings)
	fabric_width_inches = _resolve_fabric_width(row.fabric_item, settings)
	use_side = _is_side_quilted_row(row) and bool(
		row.get("side_fabric_item") and row.get("side_fabric_batch")
	)

	if use_side:
		fabric_meters = (face_area / (fabric_width_inches * inches_per_meter)) * flt(row.qty)
		side_width = _resolve_fabric_width(row.side_fabric_item, settings)
		side_fabric_meters = (side_area / (side_width * inches_per_meter)) * flt(row.qty)
	else:
		total_area = face_area + side_area
		fabric_meters = (total_area / (fabric_width_inches * inches_per_meter)) * flt(row.qty)
		side_fabric_meters = 0.0

	core_item = _get_batch_item(row.core_batch)
	fabric_item = row.fabric_item or _get_batch_item(row.fabric_batch)
	core_rate = get_stock_valuation_rate(
		core_item, warehouse=source_warehouse, batch_no=row.core_batch
	)
	fabric_rate = get_stock_valuation_rate(
		fabric_item, warehouse=source_warehouse, batch_no=row.fabric_batch
	)
	side_fabric_rate = 0.0
	if use_side:
		side_item = row.side_fabric_item or _get_batch_item(row.side_fabric_batch)
		side_fabric_rate = get_stock_valuation_rate(
			side_item, warehouse=source_warehouse, batch_no=row.side_fabric_batch
		)
	if core_rate <= 0:
		frappe.throw(
			"Row {0}: Valuation rate missing for core batch {1} in warehouse {2}.".format(
				row.idx, row.core_batch, source_warehouse or "(none)"
			)
		)
	if fabric_rate <= 0:
		frappe.throw(
			"Row {0}: Valuation rate missing for fabric batch {1} in warehouse {2}.".format(
				row.idx, row.fabric_batch, source_warehouse or "(none)"
			)
		)
	if use_side and side_fabric_rate <= 0:
		frappe.throw(
			"Row {0}: Valuation rate missing for side fabric batch {1} in warehouse {2}.".format(
				row.idx, row.side_fabric_batch, source_warehouse or "(none)"
			)
		)

	core_cost = flt(row.qty) * core_rate
	fabric_cost = fabric_meters * fabric_rate
	side_fabric_cost = side_fabric_meters * side_fabric_rate

	rm_wh = getattr(settings, "default_raw_material_warehouse", None)
	consumables = []
	consumable_specs = (
		(settings.default_tape_edge_item, tape_meters),
		(settings.default_pvc_nylon_item, pvc_kg),
		(settings.default_thread_item, thread_qty),
		(row.get("label_item"), label_qty),
	)
	consumable_cost = 0.0
	for item_code, qty in consumable_specs:
		if not item_code or flt(qty) <= 0:
			continue
		rate = get_stock_valuation_rate(item_code, warehouse=rm_wh)
		if rate <= 0:
			frappe.throw(
				"Valuation rate missing for mattress consumable {0} in warehouse {1}. "
				"Receive stock (or set Item valuation rate) before submitting.".format(
					item_code, rm_wh or "(no Raw Material Warehouse)"
				)
			)
		consumables.append(
			{
				"item_code": item_code,
				"qty": flt(qty),
				"rate": rate,
			}
		)
		consumable_cost += flt(qty) * rate

	stocked_cost = core_cost + fabric_cost + side_fabric_cost + consumable_cost

	return {
		"tape_meters": tape_meters,
		"pvc_kg": pvc_kg,
		"fabric_meters": fabric_meters,
		"side_fabric_meters": side_fabric_meters,
		"core_rate": core_rate,
		"fabric_rate": fabric_rate,
		"side_fabric_rate": side_fabric_rate,
		"core_cost": core_cost,
		"fabric_cost": fabric_cost,
		"side_fabric_cost": side_fabric_cost,
		"consumables": consumables,
		"stocked_cost": stocked_cost,
		"absorption_cost": 0.0,
		"total_row_cost": stocked_cost,
	}


def _row_finish_type(row):
	finish = (row.get("finish_type") or "").strip()
	if finish:
		return finish
	if row.mattress_item:
		return (frappe.db.get_value("Item", row.mattress_item, "custom_finish_type") or "").strip()
	return ""


def _is_side_quilted_row(row):
	return _row_finish_type(row) == "Side Quilted"


QUILTED_FABRIC_GROUP = "Quilted Fabric"


def _item_in_group(item_code, item_group):
	if not item_code:
		return False
	if not frappe.db.exists("Item Group", item_group):
		return True
	return frappe.db.get_value("Item", item_code, "item_group") == item_group


def _batch_stock_qty(item_code, warehouse, batch_no):
	"""Available qty for item+warehouse+batch (ERPNext v15 Serial/Batch Bundle aware).

	Do not sum SLE.batch_no — v15 often leaves batch_no blank on SLE and stores
	the batch only on Serial and Batch Bundle.
	"""
	if not item_code or not warehouse or not batch_no:
		return 0.0
	from erpnext.stock.doctype.batch.batch import get_batch_qty

	return flt(
		get_batch_qty(
			batch_no=batch_no,
			warehouse=warehouse,
			item_code=item_code,
		)
		or 0
	)


def _quilted_fabric_requirement_errors(row):
	"""FQ/SQ must consume Quilted Fabric. Plain cores are not blocked."""
	errors = []
	prefix = "Row {0}".format(row.idx)
	finish = _row_finish_type(row)
	if finish == "Fully Quilted":
		if row.fabric_item and not _item_in_group(row.fabric_item, QUILTED_FABRIC_GROUP):
			errors.append(
				"{0}: Fully Quilted mattresses must consume Quilted Fabric "
				"(Item Group {1}). Quilt it on a Quilting Record first, or pick a quilted batch.".format(
					prefix, QUILTED_FABRIC_GROUP
				)
			)
	elif finish == "Side Quilted":
		if row.side_fabric_item and not _item_in_group(row.side_fabric_item, QUILTED_FABRIC_GROUP):
			errors.append(
				"{0}: Side Quilted mattresses must consume Quilted Fabric on the side "
				"(Item Group {1}). Quilt it on a Quilting Record first, or pick a quilted batch.".format(
					prefix, QUILTED_FABRIC_GROUP
				)
			)
	return errors


def _quilted_fabric_stock_errors(row, costs, source_warehouse):
	errors = []
	prefix = "Row {0}".format(row.idx)
	finish = _row_finish_type(row)
	checks = []
	if finish == "Fully Quilted":
		checks.append(
			(
				row.fabric_item,
				row.fabric_batch,
				flt(costs.get("fabric_meters")),
				"quilted fabric",
			)
		)
	elif finish == "Side Quilted":
		checks.append(
			(
				row.side_fabric_item,
				row.side_fabric_batch,
				flt(costs.get("side_fabric_meters")),
				"quilted side fabric",
			)
		)
	for item_code, batch_no, needed, label in checks:
		if not item_code or not batch_no or needed <= 0:
			continue
		available = _batch_stock_qty(item_code, source_warehouse, batch_no)
		if available + 0.0001 < needed:
			errors.append(
				"{0}: Not enough {1} in warehouse {2} (batch {3}). "
				"Need {4} m, have {5} m. Run Quilting Record or pick another batch.".format(
					prefix,
					label,
					source_warehouse or "(none)",
					batch_no,
					flt(needed, 3),
					flt(available, 3),
				)
			)
	return errors


def _fabric_panel_areas(length, width, height, settings):
	"""Return (face_area, side_area) in square inches, including fabric waste."""
	panel_faces = get_formula_factor("fabric_panel_faces", settings)
	side_factor = get_formula_factor("fabric_side_panels_factor", settings)
	waste = 1 + (flt(settings.fabric_waste_factor) / 100)
	face_area = panel_faces * (length * width) * waste
	side_area = (side_factor * (length + width) * height) * waste
	return face_area, side_area


def _tape_edge_meters(length_inches, width_inches, qty, settings=None):
	"""
	Tape edge consumption in meters.
	Base: perimeter multiplier × (L+W) / inches_per_meter × qty,
	then uplift by Tape Edge Usage Allowance % (default 25%).
	"""
	settings = settings or frappe.get_single("Pufm Manufacturing Settings")
	multiplier = get_formula_factor("tape_edge_perimeter_multiplier", settings)
	inches_per_meter = get_formula_factor("inches_per_meter", settings)
	allowance_pct = get_usage_allowance_percent("tape_edge_usage_allowance", settings)

	inches = multiplier * (flt(length_inches) + flt(width_inches))
	meters = (inches / inches_per_meter) * flt(qty)
	return meters * (1 + (allowance_pct / 100.0))


def _pvc_kg(length_inches, width_inches, height_inches, qty, settings=None, row_idx=None):
	"""
	PVC wrap weight (Kg).

	W_in = width + height + width + height = 2*(W+H)
	L_in = height + length
	Convert inches → meters, then kg = W_m × L_m × GSM / 1000 × qty,
	then uplift by PVC Usage Allowance % (default 25%).
	"""
	settings = settings or frappe.get_single("Pufm Manufacturing Settings")
	gsm = flt(getattr(settings, "pvc_gsm", None))
	if gsm <= 0:
		prefix = "Row {0}: ".format(row_idx) if row_idx else ""
		frappe.throw(
			"{0}Set PVC GSM (g/m2) in Pufm Manufacturing Settings before consuming PVC.".format(
				prefix
			)
		)

	inches_per_meter = get_formula_factor("inches_per_meter", settings)
	allowance_pct = get_usage_allowance_percent("pvc_usage_allowance", settings)

	wrap_w_in = (2.0 * (flt(width_inches) + flt(height_inches)))
	wrap_l_in = flt(height_inches) + flt(length_inches)
	wrap_w_m = wrap_w_in / inches_per_meter
	wrap_l_m = wrap_l_in / inches_per_meter
	base_kg = (wrap_w_m * wrap_l_m * gsm / 1000.0) * flt(qty)
	return base_kg * (1 + (allowance_pct / 100.0))


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
		rate = flt(frappe.db.get_value("Batch", batch_no, "valuation_rate"))
		if rate > 0:
			return rate

	# Prefer direct SLE.batch_no (older postings), then Serial and Batch Bundle link (v15).
	row = frappe.db.sql(
		"""
		SELECT sle.valuation_rate, sle.incoming_rate, sle.stock_value_difference, sle.actual_qty
		FROM `tabStock Ledger Entry` sle
		LEFT JOIN `tabSerial and Batch Entry` sbe
			ON sbe.parent = sle.serial_and_batch_bundle
		WHERE IFNULL(sle.is_cancelled, 0) = 0
			AND (sle.batch_no = %s OR sbe.batch_no = %s)
		ORDER BY sle.posting_date DESC, sle.posting_time DESC, sle.creation DESC
		LIMIT 1
		""",
		(batch_no, batch_no),
		as_dict=True,
	)
	if not row:
		return 0
	r = row[0]
	for field in ("valuation_rate", "incoming_rate"):
		rate = flt(r.get(field))
		if rate > 0:
			return rate
	qty = flt(r.get("actual_qty"))
	if qty:
		rate = abs(flt(r.get("stock_value_difference")) / qty)
		if rate > 0:
			return rate
	return 0


def _get_batch_item(batch_no):
	return frappe.db.get_value("Batch", batch_no, "item")


@frappe.whitelist()
def get_allowed_fabric_items_for_mattress(mattress_item):
	"""Resolve fabrics from Item ERP Brand + product line (Mattress Brand Policy)."""
	if not mattress_item:
		return []

	item_brand = frappe.db.get_value("Item", mattress_item, "brand")
	if not item_brand:
		return []

	from pu_foam_master.pufm_manufacturing.doctype.mattress_brand_policy.mattress_brand_policy import (
		get_allowed_fabric_items,
	)
	from pu_foam_master.pufm_manufacturing.utils.mattress_sku import get_product_line_for_item

	product_line = get_product_line_for_item(mattress_item)
	return get_allowed_fabric_items(item_brand, product_line)


def _filter_fabrics_by_group(item_codes, item_group):
	if not item_codes or not item_group or not frappe.db.exists("Item Group", item_group):
		return []
	return [
		code
		for code in item_codes
		if frappe.db.get_value("Item", code, "item_group") == item_group
	]


def _fabric_candidates(mattress_item, preferred_item_group):
	"""Brand Policy fabrics in the preferred group, else the whole Item Group."""
	allowed = get_allowed_fabric_items_for_mattress(mattress_item)
	grouped = _filter_fabrics_by_group(allowed, preferred_item_group)
	if grouped:
		return grouped
	if preferred_item_group and frappe.db.exists("Item Group", preferred_item_group):
		return frappe.get_all(
			"Item",
			filters={"item_group": preferred_item_group, "disabled": 0},
			pluck="name",
		)
	return allowed or []


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def mattress_fabric_item_query(doctype, txt, searchfield, start, page_len, filters):
	"""Brand-policy fabrics for the mattress Item.brand, with Item Group fallback."""
	filters = frappe._dict(filters or {})
	allowed = _fabric_candidates(
		filters.get("mattress_item"), filters.get("preferred_item_group")
	)
	if not allowed:
		return []

	txt = f"%{txt or ''}%"
	return frappe.db.sql(
		"""
		SELECT name, item_name
		FROM `tabItem`
		WHERE disabled = 0
			AND name IN %(allowed)s
			AND (name LIKE %(txt)s OR item_name LIKE %(txt)s)
		ORDER BY name
		LIMIT %(start)s, %(page_len)s
		""",
		{
			"allowed": tuple(allowed),
			"txt": txt,
			"start": start,
			"page_len": page_len,
		},
	)
