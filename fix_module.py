import frappe


def run():
	"""One-off helper: ensure Module Def exists for the manufacturing module."""
	module_name = "pufm_manufacturing"
	if not frappe.db.exists("Module Def", module_name):
		frappe.get_doc(
			{
				"doctype": "Module Def",
				"module_name": module_name,
				"app_name": "pu_foam_master",
				"package": "PU Foam Master",
			}
		).insert(ignore_permissions=True)
		print(f"Created Module Def: {module_name}")
	else:
		print(f"Module Def {module_name} already exists")

	doctypes = [
		"Density Configuration",
		"Production Inputs",
		"Pufm Production Batch",
	]
	for dt in doctypes:
		if frappe.db.exists("DocType", dt):
			frappe.db.set_value("DocType", dt, "module", module_name)
			print(f"Fixed Module for {dt}")

	frappe.db.commit()


if __name__ == "__main__":
	run()
