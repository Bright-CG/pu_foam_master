# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

from pu_foam_master.pufm_manufacturing.utils.settings import get_cbm_factor

WORKFLOW_PENDING_SLICING = "Pending Slicing"
WORKFLOW_PENDING_ASSEMBLY = "Pending Assembly"
WORKFLOW_COMPLETED = "Completed"
ALLOWED_WORKFLOW_STATUSES = {
	WORKFLOW_PENDING_SLICING,
	WORKFLOW_PENDING_ASSEMBLY,
	WORKFLOW_COMPLETED,
}


class PufmJobOrder(Document):
	def before_insert(self):
		# Always start at slicing. Duplicate/Amend must not carry advanced status.
		self._reset_to_pending_slicing()

	def validate(self):
		if not self.order_type:
			frappe.throw(_("Order Type is required."))

		# Draft / new: system state only — ignore list-filter or duplicate prefill.
		if self.is_new() or self.docstatus == 0:
			self._reset_to_pending_slicing()
		elif not self.workflow_status:
			self.workflow_status = WORKFLOW_PENDING_SLICING

		# Sheetings never sit on Pending Assembly.
		if self.order_type == "Sheetings" and self.workflow_status == WORKFLOW_PENDING_ASSEMBLY:
			self.workflow_status = WORKFLOW_PENDING_SLICING

		if self.order_type == "Mattress":
			if not self.mattress_instructions:
				frappe.throw(_("Add at least one Mattress Instruction row."))
			self.sheeting_instructions = []
			self._validate_mattress_rows()
		elif self.order_type == "Sheetings":
			if not self.sheeting_instructions:
				frappe.throw(_("Add at least one Sheeting Instruction row."))
			self.mattress_instructions = []
			self._recalculate_sheeting_cbm()
		else:
			frappe.throw(_("Order Type must be Mattress or Sheetings."))

	def on_submit(self):
		# Submitted traveler always begins at Pending Slicing unless linked work already exists.
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


@frappe.whitelist()
def get_job_order_instructions_html(job_order):
	"""Return HTML traveler table for factory tools (Mattress Core Conversion / Mattress)."""
	if not job_order:
		return "<p class='text-muted'>No Job Order selected.</p>"

	if not frappe.db.exists("Pufm Job Order", job_order):
		return "<p class='text-danger'>Job Order not found.</p>"

	doc = frappe.get_doc("Pufm Job Order", job_order)
	body_rows = []

	if doc.order_type == "Mattress":
		header = "<tr><th>Item</th><th>Qty</th></tr>"
		for row in doc.get("mattress_instructions") or []:
			item_name = (
				frappe.db.get_value("Item", row.item_code, "item_name") or row.item_code or ""
			)
			body_rows.append(
				"<tr>"
				f"<td>{frappe.utils.escape_html(item_name)}</td>"
				f"<td>{cint(row.quantity)}</td>"
				"</tr>"
			)
		empty_msg = "No mattress assembly lines on this Job Order."
	else:
		header = (
			"<tr><th>Source Block</th><th>L</th><th>W</th><th>T</th>"
			"<th>Qty</th><th>CBM</th><th>Note</th></tr>"
		)
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
		table_html = (
			f"<table class='table table-bordered' style='margin:0;background:#fff;'>"
			f"{header}{''.join(body_rows)}</table>"
		)
	else:
		table_html = (
			f"<p class='text-muted' style='margin:0;'>"
			f"{frappe.utils.escape_html(empty_msg)}</p>"
		)

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
	  {table_html}
	  <div style="margin-top:8px;"><strong>Remarks:</strong> {remarks or '-'}</div>
	</div>
	"""


@frappe.whitelist()
def sync_job_order_status(job_order, status):
	"""Set workflow_status from production document hooks (conversion / assembly)."""
	if not job_order or not status:
		return
	if not frappe.db.exists("Pufm Job Order", job_order):
		return
	if status not in ALLOWED_WORKFLOW_STATUSES:
		frappe.throw(_("Invalid Job Order status: {0}").format(status))

	order_type = frappe.db.get_value("Pufm Job Order", job_order, "order_type")

	if status == WORKFLOW_PENDING_ASSEMBLY:
		if order_type != "Mattress":
			frappe.throw(
				_("Pending Assembly is only valid for Mattress Job Orders (got {0}).").format(
					order_type or _("blank")
				)
			)
		if not _job_has_submitted_core_conversion(job_order):
			frappe.throw(
				_(
					"Cannot set Job Order {0} to Pending Assembly without a submitted "
					"Mattress Core Conversion."
				).format(job_order)
			)

	if status == WORKFLOW_COMPLETED:
		if order_type == "Mattress":
			if not _job_has_submitted_assembly(job_order):
				frappe.throw(
					_(
						"Cannot set Job Order {0} to Completed without a submitted "
						"Mattress Production Entry."
					).format(job_order)
				)
		elif order_type == "Sheetings":
			if not _job_has_submitted_sheeting_conversion(job_order):
				frappe.throw(
					_(
						"Cannot set Job Order {0} to Completed without a submitted "
						"Pufm Sheeting Conversion."
					).format(job_order)
				)
		else:
			frappe.throw(_("Unknown Order Type on Job Order {0}.").format(job_order))

	frappe.db.set_value("Pufm Job Order", job_order, "workflow_status", status, update_modified=True)


def expected_workflow_status(job_order, order_type=None):
	"""Derive status from submitted linked production docs (source of truth)."""
	order_type = order_type or frappe.db.get_value("Pufm Job Order", job_order, "order_type")
	if order_type == "Sheetings":
		if _job_has_submitted_sheeting_conversion(job_order):
			return WORKFLOW_COMPLETED
		return WORKFLOW_PENDING_SLICING

	# Mattress
	if _job_has_submitted_assembly(job_order):
		return WORKFLOW_COMPLETED
	if _job_has_submitted_core_conversion(job_order):
		return WORKFLOW_PENDING_ASSEMBLY
	return WORKFLOW_PENDING_SLICING


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


def repair_job_order_workflow_status(job_order=None):
	"""
	Recompute workflow_status from linked production docs.
	Mattress: slicing → assembly → completed.
	Sheetings: slicing → completed (no assembly step).
	"""
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
		elif expected == WORKFLOW_PENDING_ASSEMBLY:
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
	"""Finished mattress SKUs: prefer Finished Mattresses group, else *-PLAIN/-SQ/-FQ."""
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
