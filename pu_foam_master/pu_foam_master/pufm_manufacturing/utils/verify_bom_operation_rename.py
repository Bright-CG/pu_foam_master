# Copyright (c) 2026, PU Foam Master and contributors

import frappe


def run():
	bom_module = frappe.db.get_value("DocType", "BOM Operation", "module")
	bom = frappe.get_meta("BOM Operation")
	pufm = frappe.get_meta("PUFM BOM Operation")
	dc = frappe.get_doc("Density Configuration", "D18")
	options = frappe.db.get_value(
		"DocField",
		{"parent": "Density Configuration", "fieldname": "bom_operations"},
		"options",
	)
	leftover = frappe.db.sql(
		"SELECT COUNT(*) FROM `tabBOM Operation` WHERE parenttype=%s",
		("Density Configuration",),
	)[0][0]
	pufm_count = frappe.db.sql(
		"SELECT COUNT(*) FROM `tabPUFM BOM Operation` WHERE parenttype=%s",
		("Density Configuration",),
	)[0][0]

	# ERPNext-style access that previously crashed
	row = frappe.new_doc("BOM Operation")
	assert hasattr(row, "batch_size") or bom.has_field("batch_size")
	if not getattr(row, "batch_size", None):
		row.batch_size = 1

	result = {
		"bom_module": bom_module,
		"bom_has_batch_size": bom.has_field("batch_size"),
		"pufm_fields": [f.fieldname for f in pufm.fields],
		"density_options": options,
		"d18_ops": [
			{
				"operation": r.operation,
				"workstation": r.workstation,
				"time": r.time,
				"hour_rate": r.hour_rate,
			}
			for r in (dc.bom_operations or [])
		],
		"leftover_density_on_erpnext_table": leftover,
		"pufm_density_rows": pufm_count,
		"ok": bom_module == "Manufacturing"
		and bom.has_field("batch_size")
		and options == "PUFM BOM Operation"
		and leftover == 0
		and pufm_count >= 1
		and len(dc.bom_operations or []) >= 1,
	}
	if not result["ok"]:
		frappe.throw("Verification failed: {0}".format(result))
	print(result)
	return result
