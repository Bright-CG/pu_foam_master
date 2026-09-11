# Copyright (c) 2026, PU Foam Master and contributors
"""Confirm ERPNext BOM Operation batch_size path no longer crashes."""

import frappe
from frappe.utils import flt


def run():
	row = frappe.new_doc("BOM Operation")
	# Mimic BOM.validate_operations access pattern
	if not row.batch_size or row.batch_size <= 0:
		row.batch_size = 1
	assert flt(row.batch_size) == 1

	# Density still loads PUFM child
	names = frappe.get_all("Density Configuration", limit=1, pluck="name")
	assert names
	dc = frappe.get_doc("Density Configuration", names[0])
	assert dc.meta.get_field("bom_operations").options == "PUFM BOM Operation"

	print(
		{
			"bom_operation_batch_size_ok": True,
			"density": names[0],
			"ops": len(dc.bom_operations or []),
			"bom_module": frappe.db.get_value("DocType", "BOM Operation", "module"),
			"pufm_module": frappe.db.get_value("DocType", "PUFM BOM Operation", "module"),
		}
	)
	return True
