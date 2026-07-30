# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

"""One-off DocType rename. Run BEFORE filesystem rename:

    bench --site <site> execute pu_foam_master.utils.execute_rename.execute
"""

from __future__ import annotations

import frappe


def execute():
	old = "Foam Block Conversion"
	new = "Mattress Core Conversion"

	if not frappe.db.exists("DocType", old):
		if frappe.db.exists("DocType", new):
			print(f"Already renamed: DocType '{new}' exists. Skipping.")
			return {"status": "already_renamed", "doctype": new}
		frappe.throw(f"DocType '{old}' not found and '{new}' does not exist.")

	count_before = frappe.db.count(old)

	# Standard app DocTypes require developer_mode for rename_doc
	original_dev_mode = frappe.conf.get("developer_mode")
	frappe.conf.developer_mode = 1
	try:
		frappe.rename_doc("DocType", old, new, force=True)
		frappe.db.commit()
	finally:
		frappe.conf.developer_mode = original_dev_mode

	count_after = frappe.db.count(new)
	print("Database rename successful.")
	print(f"  {old} -> {new}")
	print(f"  documents before={count_before} after={count_after}")
	return {
		"status": "renamed",
		"from": old,
		"to": new,
		"documents_before": count_before,
		"documents_after": count_after,
	}
