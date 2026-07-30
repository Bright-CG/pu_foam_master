# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

from pu_foam_master.pufm_manufacturing.utils.settings import get_cbm_factor


class PufmJobOrder(Document):
	def validate(self):
		if not self.order_type:
			frappe.throw(_("Order Type is required."))
		if not self.workflow_status:
			self.workflow_status = "Pending Slicing"

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
	"""Set workflow_status on a Job Order (used by production document hooks)."""
	if not job_order or not status:
		return
	if not frappe.db.exists("Pufm Job Order", job_order):
		return
	allowed = {"Pending Slicing", "Pending Assembly", "Completed"}
	if status not in allowed:
		frappe.throw(_("Invalid Job Order status: {0}").format(status))
	frappe.db.set_value("Pufm Job Order", job_order, "workflow_status", status, update_modified=True)


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
