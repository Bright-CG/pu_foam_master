# Copyright (c) 2026, PU Foam Master and contributors
"""One-shot: move Density Configuration ops from shadowed BOM Operation → PUFM BOM Operation."""

import frappe
from frappe.utils import flt


def run():
	old_table = "tabBOM Operation"
	new_table = "tabPUFM BOM Operation"
	parenttype = "Density Configuration"

	src = frappe.db.sql(
		"""
		SELECT name, creation, modified, modified_by, owner, docstatus, idx,
			operation, workstation,
			COALESCE(NULLIF(time, 0), time_in_mins, 0) AS time,
			hour_rate, operating_cost,
			parent, parentfield, parenttype
		FROM `tabBOM Operation`
		WHERE parenttype = %s
		""",
		(parenttype,),
		as_dict=True,
	)
	print("source_rows", len(src))

	moved = 0
	for row in src:
		if frappe.db.exists("PUFM BOM Operation", row.name):
			frappe.db.sql("DELETE FROM `tabPUFM BOM Operation` WHERE name = %s", (row.name,))
		doc = frappe.get_doc(
			{
				"doctype": "PUFM BOM Operation",
				"name": row.name,
				"creation": row.creation,
				"modified": row.modified,
				"modified_by": row.modified_by,
				"owner": row.owner,
				"docstatus": row.docstatus,
				"idx": row.idx,
				"operation": row.operation,
				"workstation": row.workstation,
				"time": flt(row.time),
				"hour_rate": flt(row.hour_rate),
				"operating_cost": flt(row.operating_cost),
				"parent": row.parent,
				"parentfield": row.parentfield,
				"parenttype": row.parenttype,
			}
		)
		doc.db_insert()
		moved += 1

	frappe.db.sql(
		"DELETE FROM `tabBOM Operation` WHERE parenttype = %s",
		(parenttype,),
	)
	frappe.db.sql(
		"""
		UPDATE `tabDocField`
		SET options = 'PUFM BOM Operation'
		WHERE parent = 'Density Configuration' AND fieldname = 'bom_operations'
		"""
	)
	frappe.db.commit()
	frappe.clear_cache(doctype="Density Configuration")
	frappe.clear_cache(doctype="PUFM BOM Operation")
	frappe.clear_cache(doctype="BOM Operation")

	# Drop leftover custom column on ERPNext table if present
	if frappe.db.has_column("BOM Operation", "time"):
		try:
			frappe.db.sql("ALTER TABLE `tabBOM Operation` DROP COLUMN `time`")
			frappe.db.commit()
			print("dropped_legacy_time_column")
		except Exception as exc:
			print("drop_time_failed", str(exc))

	left_old = frappe.db.sql(
		"SELECT COUNT(*) FROM `tabBOM Operation` WHERE parenttype = %s",
		(parenttype,),
	)[0][0]
	new_count = frappe.db.sql(
		"SELECT COUNT(*) FROM `tabPUFM BOM Operation` WHERE parenttype = %s",
		(parenttype,),
	)[0][0]
	result = {"moved": moved, "pufm_rows": new_count, "leftover_density_on_erpnext": left_old}
	print(result)
	return result
