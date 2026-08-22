# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

"""Safe install/migrate runners — never abort site install for optional setup steps."""

from __future__ import annotations

import frappe


AFTER_INSTALL_STEPS = (
	("pu_foam_master.setup_defaults.ensure_default_item_groups", "Item Groups"),
	("pu_foam_master.setup_defaults.ensure_pufm_roles", "PUFM Roles"),
	("pu_foam_master.custom_fields.ensure_item_custom_fields", "Item custom fields"),
	("pu_foam_master.custom_fields.ensure_sales_invoice_rebate_fields", "SI rebate fields"),
	("pu_foam_master.setup_defaults.ensure_customer_rebate_fields", "Customer rebate fields"),
	("pu_foam_master.setup_defaults.ensure_default_rebate_tiers", "Rebate Tiers"),
	("pu_foam_master.setup_defaults.ensure_standard_mattress_sizes", "Mattress sizes"),
	("pu_foam_master.setup_workspace.create_workspace", "Workspace"),
)


def run_after_install():
	"""Single after_install entry: run each step independently and keep going on failure."""
	for path, label in AFTER_INSTALL_STEPS:
		_run_step(path, label)


def _run_step(path, label):
	try:
		frappe.get_attr(path)()
		print("[pu_foam_master after_install] OK: {0}".format(label))
	except Exception:
		frappe.log_error(
			title="pu_foam_master after_install failed: {0}".format(label),
			message=frappe.get_traceback(),
		)
		print(
			"[pu_foam_master after_install] SKIPPED (non-fatal): {0} — see Error Log".format(
				label
			)
		)
