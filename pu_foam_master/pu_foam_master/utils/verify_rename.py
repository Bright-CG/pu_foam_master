# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

"""Post-rename verification. Run:
bench --site <site> execute pu_foam_master.utils.verify_rename.execute
"""

from __future__ import annotations

import frappe


def execute():
	old = "Foam Block Conversion"
	new = "Mattress Core Conversion"
	results = {}

	# 1) Documents survived
	old_exists = frappe.db.exists("DocType", old)
	new_exists = frappe.db.exists("DocType", new)
	doc_names = frappe.get_all(new, pluck="name", order_by="name asc") if new_exists else []
	table_ok = frappe.db.table_exists(f"tab{new}")
	old_table = frappe.db.table_exists(f"tab{old}")
	results["documents"] = {
		"old_doctype_exists": bool(old_exists),
		"new_doctype_exists": bool(new_exists),
		"new_table_exists": bool(table_ok),
		"old_table_exists": bool(old_table),
		"count": len(doc_names),
		"names": doc_names,
		"survived": new_exists and len(doc_names) == 4 and not old_exists,
	}

	# Linked stock / batches
	linked_se = []
	for name in doc_names:
		se = frappe.db.get_value(new, name, "stock_entry")
		if se:
			linked_se.append(se)
	batch_count = frappe.db.count("Batch", {"reference_doctype": new})
	results["links"] = {
		"stock_entries": linked_se,
		"batches_reference_new_doctype": batch_count,
	}

	# 2) Start Slicing target (source of truth in Job Order JS)
	js_path = frappe.get_app_path(
		"pu_foam_master",
		"pufm_manufacturing",
		"doctype",
		"pufm_job_order",
		"pufm_job_order.js",
	)
	js_text = open(js_path, encoding="utf-8").read()
	opens_new = 'frappe.new_doc("Mattress Core Conversion"' in js_text
	still_old = 'frappe.new_doc("Foam Block Conversion"' in js_text
	# Controller loadable
	controller_ok = False
	try:
		frappe.get_meta(new)
		frappe.get_doc({"doctype": new})  # unsaved draft construct
		controller_ok = True
	except Exception as exc:
		results["start_slicing_error"] = str(exc)
	results["start_slicing"] = {
		"js_opens_mattress_core_conversion": opens_new and not still_old,
		"controller_loads": controller_ok,
		"ok": opens_new and not still_old and controller_ok and new_exists,
	}

	# 3) Production Variance Report SQL
	report_ok = False
	report_error = None
	report_rows = 0
	try:
		from pu_foam_master.pufm_manufacturing.report.production_variance_report.production_variance_report import (
			execute as run_report,
		)

		_cols, data = run_report(filters={})
		report_rows = len(data or [])
		conversion_rows = [
			r for r in (data or []) if (r.get("reference_doctype") == new)
		]
		report_ok = True
		results["variance_report"] = {
			"loaded": True,
			"total_rows": report_rows,
			"mattress_core_conversion_rows": len(conversion_rows),
			"ok": True,
		}
	except Exception as exc:
		report_error = str(exc)
		results["variance_report"] = {"loaded": False, "error": report_error, "ok": False}

	print("=== RENAME VERIFICATION ===")
	print(f"Q1 documents survived (4): {results['documents']['survived']} -> {doc_names}")
	print(f"Q2 Start Slicing opens new DocType: {results['start_slicing']['ok']}")
	print(f"Q3 Variance report loads: {results['variance_report']['ok']}")
	if report_error:
		print(f"   report error: {report_error}")
	print(f"linked stock entries: {linked_se}")
	print(f"batches with new reference_doctype: {batch_count}")
	return results
