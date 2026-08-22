# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

from pu_foam_master.pufm_manufacturing.utils.settings import get_cbm_factor

WORKFLOW_PENDING_SLICING = "Pending Slicing"
WORKFLOW_PENDING_QUILTING = "Pending Quilting"
WORKFLOW_PENDING_ASSEMBLY = "Pending Assembly"
WORKFLOW_COMPLETED = "Completed"
ALLOWED_WORKFLOW_STATUSES = {
	WORKFLOW_PENDING_SLICING,
	WORKFLOW_PENDING_QUILTING,
	WORKFLOW_PENDING_ASSEMBLY,
	WORKFLOW_COMPLETED,
}

ORDER_TYPE_MATTRESS = "Mattress"
ORDER_TYPE_SHEETINGS = "Sheetings"
ORDER_TYPE_QUILTING = "Quilting"


class PufmJobOrder(Document):
	def before_insert(self):
		self._reset_to_pending_slicing()

	def validate(self):
		if not self.order_type:
			frappe.throw(_("Order Type is required."))

		if self.is_new() or self.docstatus == 0:
			self._reset_to_pending_slicing()
		elif not self.workflow_status:
			self.workflow_status = WORKFLOW_PENDING_SLICING

		if self.order_type == ORDER_TYPE_SHEETINGS and self.workflow_status == WORKFLOW_PENDING_ASSEMBLY:
			self.workflow_status = WORKFLOW_PENDING_SLICING

		if self.order_type == ORDER_TYPE_MATTRESS:
			if not self.mattress_instructions:
				frappe.throw(_("Add at least one Mattress Instruction row."))
			self.sheeting_instructions = []
			self.quilting_instructions = []
			self._validate_mattress_rows()
		elif self.order_type == ORDER_TYPE_SHEETINGS:
			if not self.sheeting_instructions:
				frappe.throw(_("Add at least one Sheeting Instruction row."))
			self.mattress_instructions = []
			self.quilting_instructions = []
			self._recalculate_sheeting_cbm()
		elif self.order_type == ORDER_TYPE_QUILTING:
			rows = self.get("quilting_instructions") or []
			if len(rows) != 1:
				frappe.throw(_("Quilting Job Orders must have exactly one Quilting Instruction row."))
			self.mattress_instructions = []
			self.sheeting_instructions = []
			self._validate_quilting_row(rows[0])
		else:
			frappe.throw(_("Order Type must be Mattress, Sheetings, or Quilting."))

	def on_submit(self):
		expected = expected_workflow_status(self.name, self.order_type)
		if self.workflow_status != expected:
			self.db_set("workflow_status", expected, update_modified=False)
		if expected == WORKFLOW_PENDING_SLICING:
			self.db_set("sliced_by", None, update_modified=False)
			self.db_set("assembled_by", None, update_modified=False)

	def _reset_to_pending_slicing(self):
		self.workflow_status = WORKFLOW_PENDING_SLICING
		self.sliced_by = None
		self.assembled_by = None

	def _validate_mattress_rows(self):
		for row in self.get("mattress_instructions") or []:
			if not row.item_code:
				frappe.throw(_("Row {0}: Item Code is required.").format(row.idx))
			if cint(row.quantity) <= 0:
				frappe.throw(_("Row {0}: Quantity must be greater than zero.").format(row.idx))

	def _validate_quilting_row(self, row):
		if not row.source_block:
			frappe.throw(_("Source Block is required."))
		if flt(row.block_qty) <= 0:
			frappe.throw(_("Block Qty must be greater than zero."))
		if not row.output_sheeting_item:
			frappe.throw(_("Output Sheeting Roll Item is required."))
		if not row.fabric_item:
			frappe.throw(_("Fabric Item is required."))
		if not row.target_quilted_item:
			frappe.throw(_("Target Quilted Item is required."))

	def _recalculate_sheeting_cbm(self):
		cbm_factor = get_cbm_factor()
		for row in self.get("sheeting_instructions") or []:
			if not row.source_block:
				frappe.throw(_("Row {0}: Source Block is required.").format(row.idx))
			qty = cint(row.quantity) or 0
			length = flt(row.length_inches)
			width = flt(row.width_inches)
			thickness = flt(row.thickness_inches)
			if length <= 0 or width <= 0 or thickness <= 0 or qty <= 0:
				row.calculated_cbm = 0
				continue
			row.calculated_cbm = flt((length * width * thickness * qty) / cbm_factor, 5)


def get_quilting_instruction_row(doc):
	rows = doc.get("quilting_instructions") or []
	return rows[0] if rows else None


@frappe.whitelist()
def get_job_order_instructions_html(job_order):
	if not job_order:
		return "<p class='text-muted'>No Job Order selected.</p>"
	if not frappe.db.exists("Pufm Job Order", job_order):
		return "<p class='text-danger'>Job Order not found.</p>"

	doc = frappe.get_doc("Pufm Job Order", job_order)
	progress_html = get_job_order_progress_html(doc)
	body_html = _job_order_body_html(doc)
	remarks = frappe.utils.escape_html(doc.production_remarks or "")
	customer = frappe.utils.escape_html(doc.customer or "")
	status = frappe.utils.escape_html(doc.workflow_status or "")

	return f"""
	<div class="pufm-job-traveler" style="border:1px solid #d1d8dd;border-radius:6px;padding:12px;background:#fafbfc;">
	  <div style="margin-bottom:8px;">
	    <strong>Job Order:</strong> {frappe.utils.escape_html(doc.name)}
	    &nbsp;|&nbsp; <strong>Type:</strong> {frappe.utils.escape_html(doc.order_type or '')}
	    &nbsp;|&nbsp; <strong>Status:</strong> {status}
	    &nbsp;|&nbsp; <strong>Customer:</strong> {customer}
	  </div>
	  {progress_html}
	  {body_html}
	  <div style="margin-top:8px;"><strong>Remarks:</strong> {remarks or '-'}</div>
	</div>
	"""


@frappe.whitelist()
def get_mattress_production_traveler_html(job_order, core_conversion=None):
	"""Job traveler plus output cores from linked conversion (Quilting JO assembly)."""
	base = get_job_order_instructions_html(job_order)
	if not core_conversion:
		return base
	cores_html = _conversion_core_outputs_html(core_conversion)
	if not cores_html:
		return base
	insert_at = base.rfind("<div style=\"margin-top:8px;\"><strong>Remarks:")
	if insert_at == -1:
		return base + cores_html
	return base[:insert_at] + cores_html + base[insert_at:]


def _job_order_body_html(doc):
	if doc.order_type == ORDER_TYPE_MATTRESS:
		header = "<tr><th>Item</th><th>Finish</th><th>Qty</th></tr>"
		body_rows = []
		for row in doc.get("mattress_instructions") or []:
			item_name = frappe.db.get_value("Item", row.item_code, "item_name") or row.item_code or ""
			finish = frappe.db.get_value("Item", row.item_code, "custom_finish_type") or ""
			body_rows.append(
				"<tr>"
				f"<td>{frappe.utils.escape_html(item_name)}</td>"
				f"<td>{frappe.utils.escape_html(finish or '—')}</td>"
				f"<td>{cint(row.quantity)}</td>"
				"</tr>"
			)
		empty_msg = "No mattress assembly lines on this Job Order."
	elif doc.order_type == ORDER_TYPE_QUILTING:
		row = get_quilting_instruction_row(doc)
		if not row:
			return "<p class='text-muted'>No quilting instruction on this Job Order.</p>"
		header = (
			"<tr><th>Source Block</th><th>Block Qty</th><th>Sheeting Roll</th>"
			"<th>Fabric</th><th>Target QF Item</th><th>Plan (m)</th></tr>"
		)
		body_rows = [
			"<tr>"
			f"<td>{frappe.utils.escape_html(row.source_block or '')}</td>"
			f"<td>{flt(row.block_qty)}</td>"
			f"<td>{frappe.utils.escape_html(row.output_sheeting_item or '')}</td>"
			f"<td>{frappe.utils.escape_html(row.fabric_item or '')}</td>"
			f"<td>{frappe.utils.escape_html(row.target_quilted_item or '')}</td>"
			f"<td>{flt(row.planned_qty_meters)}</td>"
			"</tr>"
		]
		empty_msg = ""
	else:
		header = (
			"<tr><th>Source Block</th><th>L</th><th>W</th><th>T</th>"
			"<th>Qty</th><th>CBM</th><th>Note</th></tr>"
		)
		body_rows = []
		for row in doc.get("sheeting_instructions") or []:
			body_rows.append(
				"<tr>"
				f"<td>{frappe.utils.escape_html(row.source_block or '')}</td>"
				f"<td>{flt(row.length_inches)}</td>"
				f"<td>{flt(row.width_inches)}</td>"
				f"<td>{flt(row.thickness_inches)}</td>"
				f"<td>{cint(row.quantity)}</td>"
				f"<td>{flt(row.calculated_cbm, 5)}</td>"
				f"<td>{frappe.utils.escape_html(row.row_note or '')}</td>"
				"</tr>"
			)
		empty_msg = "No sheeting lines on this Job Order."

	if body_rows:
		return (
			f"<table class='table table-bordered' style='margin:0;background:#fff;'>"
			f"{header}{''.join(body_rows)}</table>"
		)
	return f"<p class='text-muted' style='margin:0;'>{frappe.utils.escape_html(empty_msg)}</p>"


def get_job_order_progress_html(doc):
	if doc.order_type != ORDER_TYPE_QUILTING:
		return ""

	name = doc.name if not doc.is_new() else None
	if not name:
		return ""

	conversion_done = _job_has_submitted_core_conversion(name)
	quilting_done = _job_has_submitted_quilting(name)
	assembly_done = _job_has_submitted_assembly(name)
	needs_assembly = quilting_jo_requires_core_assembly(name)

	def line(label, done, required=True):
		if not required:
			state = _("Not Required")
			color = "#888"
		elif done:
			state = _("Done")
			color = "green"
		else:
			state = _("Pending")
			color = "#d35400"
		return (
			f"<li><strong>{frappe.utils.escape_html(label)}:</strong> "
			f"<span style='color:{color};'>{frappe.utils.escape_html(state)}</span></li>"
		)

	items = [
		line(_("Conversion"), conversion_done),
		line(_("Quilting"), quilting_done),
		line(_("Core Assembly"), assembly_done, required=needs_assembly),
	]
	return (
		"<div style='margin-bottom:8px;padding:8px;background:#fff;border-radius:4px;'>"
		f"<strong>{_('Progress')}:</strong><ul style='margin:4px 0 0 16px;'>{''.join(items)}</ul>"
		"</div>"
	)


def _conversion_core_outputs_html(conversion_name):
	rows = get_conversion_core_outputs(conversion_name)
	if not rows:
		return ""
	body = "".join(
		"<tr>"
		f"<td>{frappe.utils.escape_html(r['item_code'])}</td>"
		f"<td>{flt(r['qty'])}</td>"
		f"<td>{frappe.utils.escape_html(r.get('batch_no') or '—')}</td>"
		"</tr>"
		for r in rows
	)
	return (
		"<div style='margin-top:8px;padding:8px;background:#fff;border-radius:4px;'>"
		f"<strong>{_('Output cores from conversion')} ({frappe.utils.escape_html(conversion_name)}):</strong>"
		"<table class='table table-bordered' style='margin:8px 0 0;background:#fff;'>"
		f"<tr><th>{_('Core Item')}</th><th>{_('Qty')}</th><th>{_('Batch')}</th></tr>"
		f"{body}</table></div>"
	)


def get_conversion_core_outputs(conversion_name):
	from pu_foam_master.pufm_manufacturing.utils.item_traceability import is_foam_core_item

	if not conversion_name or not frappe.db.exists("Mattress Core Conversion", conversion_name):
		return []
	outputs = frappe.get_all(
		"Block Conversion Output",
		filters={"parent": conversion_name},
		fields=["item_code", "qty"],
	)
	result = []
	for row in outputs:
		if not is_foam_core_item(row.item_code):
			continue
		batch_no = _conversion_output_batch(conversion_name, row.item_code)
		result.append(
			{"item_code": row.item_code, "qty": flt(row.qty), "batch_no": batch_no}
		)
	return result


def _conversion_output_batch(conversion_name, item_code):
	batch_id = "{0}-{1}".format(conversion_name, item_code)
	if frappe.db.exists("Batch", batch_id):
		return batch_id
	name = frappe.db.get_value(
		"Batch",
		{"item": item_code, "reference_name": conversion_name},
		"name",
	)
	return name or batch_id


def quilting_jo_requires_core_assembly(job_order):
	if not job_order:
		return False
	order_type = frappe.db.get_value("Pufm Job Order", job_order, "order_type")
	if order_type != ORDER_TYPE_QUILTING:
		return False
	conversion = _get_submitted_conversion_name(job_order)
	if not conversion:
		return False
	return bool(get_conversion_core_outputs(conversion))


def _get_submitted_conversion_name(job_order):
	return frappe.db.get_value(
		"Mattress Core Conversion",
		{"job_order": job_order, "docstatus": 1},
		"name",
		order_by="modified desc",
	)


@frappe.whitelist()
def get_core_conversion_prefill(job_order):
	"""Prefill Mattress Core Conversion from a Quilting Job Order (editable on floor)."""
	if not job_order or not frappe.db.exists("Pufm Job Order", job_order):
		frappe.throw(_("Job Order not found."))
	doc = frappe.get_doc("Pufm Job Order", job_order)
	if doc.order_type != ORDER_TYPE_QUILTING:
		frappe.throw(_("Job Order {0} is not a Quilting Job Order.").format(job_order))
	row = get_quilting_instruction_row(doc)
	if not row:
		frappe.throw(_("Quilting Job Order has no instruction row."))
	return {
		"job_order": job_order,
		"inputs": [
			{
				"item_code": row.source_block,
				"qty": flt(row.block_qty),
			}
		],
		"outputs": [
			{
				"item_code": row.output_sheeting_item,
				"qty": 1,
			}
		],
	}


@frappe.whitelist()
def get_quilting_record_prefill(job_order):
	if not job_order or not frappe.db.exists("Pufm Job Order", job_order):
		frappe.throw(_("Job Order not found."))
	doc = frappe.get_doc("Pufm Job Order", job_order)
	if doc.order_type != ORDER_TYPE_QUILTING:
		frappe.throw(_("Job Order {0} is not a Quilting Job Order.").format(job_order))
	row = get_quilting_instruction_row(doc)
	if not row:
		frappe.throw(_("Quilting Job Order has no instruction row."))
	conversion = _get_submitted_conversion_name(job_order)
	if not conversion:
		frappe.throw(
			_("Submit a Mattress Core Conversion for Job Order {0} before starting quilting.").format(
				job_order
			)
		)
	sales_order = None
	if doc.source_doctype == "Sales Order" and doc.source_document:
		sales_order = doc.source_document
	return {
		"job_order": job_order,
		"core_conversion": conversion,
		"sales_order": sales_order,
		"fabric_item": row.fabric_item,
		"sheeting_roll_item": row.output_sheeting_item,
		"finished_item": row.target_quilted_item,
		"planned_qty_meters": flt(row.planned_qty_meters),
	}


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def sheeting_batch_query_for_conversion(doctype, txt, searchfield, start, page_len, filters):
	"""Batch picker: sheeting/foam-roll batches produced by the linked conversion."""
	conversion = (filters or {}).get("core_conversion")
	item_code = (filters or {}).get("item_code")
	if not conversion or not item_code:
		return []

	txt = (txt or "").strip()
	like = "%{0}%".format(txt) if txt else "%"
	# Batches stamped by conversion submit (CONV-...-ITEM or reference_name).
	return frappe.db.sql(
		"""
		SELECT name, item
		FROM `tabBatch`
		WHERE item = %(item)s
			AND IFNULL(disabled, 0) = 0
			AND (
				reference_name = %(conversion)s
				OR batch_id LIKE %(prefix)s
				OR name LIKE %(prefix)s
			)
			AND (name LIKE %(txt)s OR IFNULL(batch_id, '') LIKE %(txt)s)
		ORDER BY creation DESC
		LIMIT %(start)s, %(page_len)s
		""",
		{
			"item": item_code,
			"conversion": conversion,
			"prefix": "{0}-%".format(conversion),
			"txt": like,
			"start": start,
			"page_len": page_len,
		},
	)


@frappe.whitelist()
def get_mattress_production_prefill(job_order):
	"""Prefill assembly from Quilting JO — link JO + conversion only (no mattress rows)."""
	if not job_order or not frappe.db.exists("Pufm Job Order", job_order):
		frappe.throw(_("Job Order not found."))
	doc = frappe.get_doc("Pufm Job Order", job_order)
	if doc.order_type != ORDER_TYPE_QUILTING:
		frappe.throw(_("Job Order {0} is not a Quilting Job Order.").format(job_order))
	conversion = _get_submitted_conversion_name(job_order)
	if not conversion:
		frappe.throw(
			_("Submit a Mattress Core Conversion for Job Order {0} before starting assembly.").format(
				job_order
			)
		)
	sales_order = doc.source_document if doc.source_doctype == "Sales Order" else None
	return {
		"job_order": job_order,
		"core_conversion": conversion,
		"sales_order": sales_order,
	}


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def core_batch_query_for_conversion(doctype, txt, searchfield, start, page_len, filters):
	"""Batch picker: only core batches from the linked conversion."""
	conversion = (filters or {}).get("core_conversion")
	mattress_item = (filters or {}).get("mattress_item")
	if not conversion:
		return []

	from pu_foam_master.pufm_manufacturing.utils.item_cbm import implied_core_item

	core_filter = implied_core_item(mattress_item) if mattress_item else None
	batches = []
	for row in get_conversion_core_outputs(conversion):
		if core_filter and row["item_code"] != core_filter:
			continue
		batch_no = row.get("batch_no")
		if batch_no and (not txt or txt.lower() in batch_no.lower()):
			batches.append([batch_no, row["item_code"]])

	# dedupe
	seen = set()
	unique = []
	for b in batches:
		if b[0] in seen:
			continue
		seen.add(b[0])
		unique.append(b)
	return unique[start : start + page_len]


@frappe.whitelist()
def sync_job_order_status(job_order, status):
	"""Set workflow_status from production hooks (legacy entry — prefer reconcile)."""
	if not job_order or not status:
		return
	reconcile_job_order_workflow(job_order)


def reconcile_job_order_workflow(job_order):
	"""Recompute workflow_status from linked production documents."""
	if not job_order or not frappe.db.exists("Pufm Job Order", job_order):
		return
	order_type = frappe.db.get_value("Pufm Job Order", job_order, "order_type")
	expected = expected_workflow_status(job_order, order_type)
	current = frappe.db.get_value("Pufm Job Order", job_order, "workflow_status")
	if current == expected:
		return
	values = {"workflow_status": expected}
	if expected == WORKFLOW_PENDING_SLICING:
		values["sliced_by"] = None
		values["assembled_by"] = None
	elif expected in (WORKFLOW_PENDING_QUILTING, WORKFLOW_PENDING_ASSEMBLY):
		values["assembled_by"] = None
	frappe.db.set_value("Pufm Job Order", job_order, values, update_modified=True)


def expected_workflow_status(job_order, order_type=None):
	order_type = order_type or frappe.db.get_value("Pufm Job Order", job_order, "order_type")

	if order_type == ORDER_TYPE_SHEETINGS:
		if _job_has_submitted_sheeting_conversion(job_order):
			return WORKFLOW_COMPLETED
		return WORKFLOW_PENDING_SLICING

	if order_type == ORDER_TYPE_QUILTING:
		if _quilting_jo_is_complete(job_order):
			return WORKFLOW_COMPLETED
		if _job_has_submitted_core_conversion(job_order):
			return WORKFLOW_PENDING_QUILTING
		return WORKFLOW_PENDING_SLICING

	# Mattress
	if _job_has_submitted_assembly(job_order):
		return WORKFLOW_COMPLETED
	if _job_has_submitted_core_conversion(job_order):
		return WORKFLOW_PENDING_ASSEMBLY
	return WORKFLOW_PENDING_SLICING


def _quilting_jo_is_complete(job_order):
	if not _job_has_submitted_quilting(job_order):
		return False
	if quilting_jo_requires_core_assembly(job_order):
		return _job_has_submitted_assembly(job_order)
	return True


def _job_has_submitted_core_conversion(job_order):
	return bool(
		frappe.db.exists(
			"Mattress Core Conversion",
			{"job_order": job_order, "docstatus": 1},
		)
	)


def _job_has_submitted_assembly(job_order):
	return bool(
		frappe.db.exists(
			"Mattress Production Entry",
			{"job_order": job_order, "docstatus": 1},
		)
	)


def _job_has_submitted_sheeting_conversion(job_order):
	return bool(
		frappe.db.exists(
			"Pufm Sheeting Conversion",
			{"job_order": job_order, "docstatus": 1},
		)
	)


def _job_has_submitted_quilting(job_order):
	if not job_order:
		return False
	return bool(
		frappe.db.exists(
			"Quilting Record",
			{"job_order": job_order, "docstatus": 1},
		)
	)


def repair_job_order_workflow_status(job_order=None):
	filters = {}
	if job_order:
		filters["name"] = job_order
	names = frappe.get_all("Pufm Job Order", filters=filters, pluck="name")
	fixed = []
	for name in names:
		doc = frappe.get_doc("Pufm Job Order", name)
		expected = expected_workflow_status(name, doc.order_type)
		if doc.workflow_status == expected:
			continue
		values = {"workflow_status": expected}
		if expected == WORKFLOW_PENDING_SLICING:
			values["sliced_by"] = None
			values["assembled_by"] = None
		elif expected in (WORKFLOW_PENDING_QUILTING, WORKFLOW_PENDING_ASSEMBLY):
			values["assembled_by"] = None
		frappe.db.set_value("Pufm Job Order", name, values, update_modified=True)
		fixed.append("{0}: {1} -> {2}".format(name, doc.workflow_status, expected))

	if fixed:
		frappe.db.commit()
		print("[pufm_job_order] Repaired workflow status:\n- " + "\n- ".join(fixed))
	else:
		print("[pufm_job_order] No Job Order workflow status repairs needed.")
	return fixed


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def mattress_item_query(doctype, txt, searchfield, start, page_len, filters):
	txt = f"%{txt or ''}%"
	group = "Finished Mattresses"
	if frappe.db.exists("Item Group", group):
		return frappe.db.sql(
			"""
			SELECT name, item_name
			FROM `tabItem`
			WHERE disabled = 0
				AND is_stock_item = 1
				AND item_group = %(group)s
				AND (name LIKE %(txt)s OR item_name LIKE %(txt)s)
			ORDER BY name
			LIMIT %(start)s, %(page_len)s
			""",
			{"group": group, "txt": txt, "start": start, "page_len": page_len},
		)
	return frappe.db.sql(
		"""
		SELECT name, item_name
		FROM `tabItem`
		WHERE disabled = 0
			AND is_stock_item = 1
			AND (
				name LIKE '%%-PLAIN'
				OR name LIKE '%%-SQ'
				OR name LIKE '%%-FQ'
			)
			AND (name LIKE %(txt)s OR item_name LIKE %(txt)s)
		ORDER BY name
		LIMIT %(start)s, %(page_len)s
		""",
		{"txt": txt, "start": start, "page_len": page_len},
	)
