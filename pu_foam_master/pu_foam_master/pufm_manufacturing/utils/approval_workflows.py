# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

"""Ship approval Workflows for pour / conversion / sheeting / mattress assembly.

Stock posting stays on DocType on_submit. These Workflows only gate when Submit is allowed.

Frappe v15 Workflow Document State.allow_edit and Workflow Transition.allowed are
single Role Links — duplicate rows when multiple roles share a state or action.
"""

from __future__ import annotations

import frappe
from frappe import _

STATE_DRAFT = "Draft"
STATE_SUPERVISOR = "Pending Supervisor Approval"
STATE_STORE = "Pending Store Confirmation"
STATE_COMPLETED = "Completed"

WORKFLOW_STATES = (STATE_DRAFT, STATE_SUPERVISOR, STATE_STORE, STATE_COMPLETED)

# document_type -> workflow definition (role lists; expanded to one Link row each)
WORKFLOW_SPECS = {
	"Pufm Production Batch": {
		"name": "PUFM Production Batch Approval",
		"entry_roles": [
			"PUFM Block Production",
			"PUFM Production Manager",
			"PUFM Manager",
			"System Manager",
		],
		"supervisor_roles": [
			"PUFM Production Manager",
			"PUFM Manager",
			"System Manager",
		],
		"confirm_roles": [
			"PUFM Store",
			"PUFM Confirmation",
			"PUFM Manager",
			"System Manager",
		],
		"completed_edit_roles": ["PUFM Manager", "System Manager"],
		"bypass_roles": [
			"PUFM Production Manager",
			"PUFM Manager",
			"System Manager",
		],
	},
	"Mattress Core Conversion": {
		"name": "PUFM Mattress Core Conversion Approval",
		"entry_roles": [
			"PUFM Conversion",
			"PUFM Conversion Supervisor",
			"PUFM Manager",
			"System Manager",
		],
		"supervisor_roles": [
			"PUFM Conversion Supervisor",
			"PUFM Manager",
			"System Manager",
		],
		"confirm_roles": [
			"PUFM Confirmation",
			"PUFM Manager",
			"System Manager",
		],
		"completed_edit_roles": ["PUFM Manager", "System Manager"],
		"bypass_roles": ["PUFM Manager", "System Manager"],
	},
	"Pufm Sheeting Conversion": {
		"name": "PUFM Sheeting Conversion Approval",
		"entry_roles": [
			"PUFM Conversion",
			"PUFM Conversion Supervisor",
			"PUFM Manager",
			"System Manager",
		],
		"supervisor_roles": [
			"PUFM Conversion Supervisor",
			"PUFM Manager",
			"System Manager",
		],
		"confirm_roles": [
			"PUFM Confirmation",
			"PUFM Manager",
			"System Manager",
		],
		"completed_edit_roles": ["PUFM Manager", "System Manager"],
		"bypass_roles": ["PUFM Manager", "System Manager"],
	},
	"Mattress Production Entry": {
		"name": "PUFM Mattress Production Entry Approval",
		"entry_roles": [
			"PUFM Assembly",
			"PUFM Assembly Supervisor",
			"PUFM Manager",
			"System Manager",
		],
		"supervisor_roles": [
			"PUFM Assembly Supervisor",
			"PUFM Manager",
			"System Manager",
		],
		"confirm_roles": [
			"PUFM Store",
			"PUFM Confirmation",
			"PUFM Manager",
			"System Manager",
		],
		"completed_edit_roles": ["PUFM Manager", "System Manager"],
		"bypass_roles": ["PUFM Manager", "System Manager"],
	},
}


def ensure_pufm_approval_workflows():
	"""Idempotent: Workflow States + active Workflows for the four production DocTypes."""
	from pu_foam_master.setup_defaults import ensure_pufm_roles

	ensure_pufm_roles()
	_ensure_workflow_states()
	_ensure_workflow_actions(
		(
			"Send for Approval",
			"Approve",
			"Reject",
			"Confirm Receipt",
			"Bypass Submit",
		)
	)
	for doctype, spec in WORKFLOW_SPECS.items():
		if not frappe.db.exists("DocType", doctype):
			continue
		_ensure_workflow_state_field(doctype)
		_ensure_workflow(doctype, spec)
	_migrate_legacy_production_batch_states()
	frappe.clear_cache()
	print("[approval_workflows] Ensured PUFM approval Workflows.")


def _ensure_workflow_actions(actions):
	for action in actions:
		if frappe.db.exists("Workflow Action Master", action):
			continue
		frappe.get_doc(
			{"doctype": "Workflow Action Master", "workflow_action_name": action}
		).insert(ignore_permissions=True)


def _ensure_workflow_states():
	for state in WORKFLOW_STATES:
		if frappe.db.exists("Workflow State", state):
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Workflow State",
				"workflow_state_name": state,
				"style": "Primary" if state == STATE_COMPLETED else "",
			}
		)
		doc.insert(ignore_permissions=True)


def _ensure_workflow_state_field(doctype):
	"""Ensure standard workflow_state Link field exists (hidden; Workflow drives Actions)."""
	meta = frappe.get_meta(doctype)
	if meta.has_field("workflow_state"):
		# Cosmetic Select on Production Batch is replaced via DocType JSON sync on migrate.
		return
	frappe.get_doc(
		{
			"doctype": "Custom Field",
			"dt": doctype,
			"fieldname": "workflow_state",
			"label": "Workflow State",
			"fieldtype": "Link",
			"options": "Workflow State",
			"allow_on_submit": 1,
			"hidden": 1,
			"no_copy": 1,
			"insert_after": meta.fields[0].fieldname if meta.fields else None,
		}
	).insert(ignore_permissions=True)


def _state_rows(state, doc_status, roles):
	"""One Workflow Document State row per allow_edit Role (Link field)."""
	return [
		{
			"state": state,
			"doc_status": doc_status,
			"allow_edit": role,
			"is_optional_state": 0,
		}
		for role in roles
	]


def _transition_rows(state, action, next_state, roles):
	"""One Workflow Transition row per allowed Role (Link field)."""
	return [
		{
			"state": state,
			"action": action,
			"next_state": next_state,
			"allowed": role,
			"allow_self_approval": 1,
		}
		for role in roles
	]


def _ensure_workflow(doctype, spec):
	name = spec["name"]
	entry = spec["entry_roles"]
	supervisor = spec["supervisor_roles"]
	confirm = spec["confirm_roles"]
	completed_edit = spec["completed_edit_roles"]
	bypass = spec["bypass_roles"]

	states = []
	states.extend(_state_rows(STATE_DRAFT, "0", entry))
	states.extend(_state_rows(STATE_SUPERVISOR, "0", supervisor))
	states.extend(_state_rows(STATE_STORE, "0", confirm))
	states.extend(_state_rows(STATE_COMPLETED, "1", completed_edit))

	transitions = []
	transitions.extend(
		_transition_rows(STATE_DRAFT, "Send for Approval", STATE_SUPERVISOR, entry)
	)
	transitions.extend(
		_transition_rows(STATE_SUPERVISOR, "Approve", STATE_STORE, supervisor)
	)
	transitions.extend(
		_transition_rows(STATE_SUPERVISOR, "Reject", STATE_DRAFT, supervisor)
	)
	transitions.extend(
		_transition_rows(STATE_STORE, "Confirm Receipt", STATE_COMPLETED, confirm)
	)
	transitions.extend(
		_transition_rows(STATE_STORE, "Reject", STATE_SUPERVISOR, confirm)
	)
	for from_state in (STATE_DRAFT, STATE_SUPERVISOR, STATE_STORE):
		transitions.extend(
			_transition_rows(from_state, "Bypass Submit", STATE_COMPLETED, bypass)
		)

	payload = {
		"doctype": "Workflow",
		"workflow_name": name,
		"document_type": doctype,
		"is_active": 1,
		"override_status": 0,
		"send_email_alert": 0,
		"workflow_state_field": "workflow_state",
	}

	if frappe.db.exists("Workflow", name):
		doc = frappe.get_doc("Workflow", name)
		doc.update(payload)
		doc.states = []
		doc.transitions = []
		for row in states:
			doc.append("states", row)
		for row in transitions:
			doc.append("transitions", row)
		doc.save(ignore_permissions=True)
	else:
		doc = frappe.get_doc(payload)
		for row in states:
			doc.append("states", row)
		for row in transitions:
			doc.append("transitions", row)
		doc.insert(ignore_permissions=True)

	# Deactivate any other active workflows on this DocType
	others = frappe.get_all(
		"Workflow",
		filters={"document_type": doctype, "is_active": 1, "name": ["!=", name]},
		pluck="name",
	)
	for other in others:
		frappe.db.set_value("Workflow", other, "is_active", 0)


def _migrate_legacy_production_batch_states():
	"""Map old cosmetic Select values to new Workflow State names."""
	if not frappe.db.exists("DocType", "Pufm Production Batch"):
		return
	if not frappe.db.has_column("Pufm Production Batch", "workflow_state"):
		return
	mapping = {
		"Pending MD Approval": STATE_SUPERVISOR,
		"Pending Store Confirmation": STATE_STORE,
		"Completed": STATE_COMPLETED,
		"Draft": STATE_DRAFT,
	}
	for old, new in mapping.items():
		frappe.db.sql(
			"""
			UPDATE `tabPufm Production Batch`
			SET workflow_state = %s
			WHERE workflow_state = %s
			""",
			(new, old),
		)


def assert_deletable_before_supervisor_approval(doc):
	"""Store/Confirmation never delete; others only before supervisor approval."""
	if doc.docstatus != 0:
		frappe.throw(_("Cannot delete a submitted document."))

	state = (doc.get("workflow_state") or STATE_DRAFT).strip()
	roles = set(frappe.get_roles(frappe.session.user))
	if frappe.session.user == "Administrator" or "System Manager" in roles or "PUFM Manager" in roles:
		if state in (STATE_DRAFT, STATE_SUPERVISOR):
			return
		frappe.throw(
			_("Only Draft or Pending Supervisor Approval documents can be deleted.")
		)

	blocked = {"PUFM Store", "PUFM Confirmation"}
	if roles.intersection(blocked) and not roles.intersection(
		{
			"PUFM Production Manager",
			"PUFM Conversion Supervisor",
			"PUFM Assembly Supervisor",
			"PUFM Manager",
			"System Manager",
		}
	):
		frappe.throw(_("Store / Confirmation roles cannot delete this document."))

	if state not in (STATE_DRAFT, STATE_SUPERVISOR):
		frappe.throw(
			_("Delete is only allowed before supervisor approval (Draft / Pending Supervisor Approval).")
		)
