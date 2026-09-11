# Copyright (c) 2026, PU Foam Master and contributors
"""Smoke-load all pu_foam_master DocTypes (meta + new_doc)."""

from __future__ import annotations

import frappe


def run():
	doctypes = frappe.get_all(
		"DocType",
		filters={"module": "pufm_manufacturing", "issingle": 0},
		pluck="name",
		order_by="name",
	)
	# Include single Settings
	if frappe.db.exists("DocType", "Pufm Manufacturing Settings"):
		doctypes.append("Pufm Manufacturing Settings")

	ok = []
	failed = []
	for dt in doctypes:
		try:
			meta = frappe.get_meta(dt)
			if meta.issingle:
				frappe.get_single(dt)
			elif meta.istable:
				# child table: just instantiate
				frappe.new_doc(dt)
			else:
				frappe.new_doc(dt)
			ok.append(dt)
		except Exception as exc:
			failed.append({"doctype": dt, "error": "{0}: {1}".format(type(exc).__name__, exc)})

	# Key operational doctypes — load an existing doc if present
	samples = {}
	for dt, filters in (
		("Density Configuration", {}),
		("Mattress Core Conversion", {"docstatus": ["<", 2]}),
		("Pufm Production Batch", {}),
		("Pufm Price Engine", {}),
		("Pufm Job Order", {}),
	):
		name = frappe.db.get_value(dt, filters or None, "name")
		if not name:
			samples[dt] = "none"
			continue
		try:
			doc = frappe.get_doc(dt, name)
			samples[dt] = {"name": name, "docstatus": doc.docstatus, "ok": True}
		except Exception as exc:
			samples[dt] = {"name": name, "ok": False, "error": str(exc)}
			failed.append({"doctype": dt, "error": str(exc), "name": name})

	result = {
		"payment_gateway_exists": bool(frappe.db.exists("DocType", "Payment Gateway")),
		"payments_installed": "payments" in frappe.get_installed_apps(),
		"doctypes_ok": len(ok),
		"doctypes_failed": failed,
		"samples": samples,
		"ok": not failed,
	}
	print(result)
	if failed:
		frappe.throw("Smoke failed: {0}".format(failed))
	return result
