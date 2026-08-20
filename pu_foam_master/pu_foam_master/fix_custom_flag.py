import frappe


def run():
	"""Repair Density Configuration DocType flags for white-label installs."""
	site = frappe.local.site
	doctypes = ["Density Configuration", "Production Inputs"]
	module_name = "pufm_manufacturing"
	app_name = "pu_foam_master"

	print(f"Starting repair for site: {site}")

	# 1. Ensure Module Def exists and is linked correctly
	try:
		if not frappe.db.exists("Module Def", module_name):
			frappe.get_doc(
				{
					"doctype": "Module Def",
					"module_name": module_name,
					"app_name": app_name,
				}
			).insert(ignore_permissions=True)
			print(f"Created Module Def: {module_name}")
	except Exception as e:
		print(f"Module Def check failed: {str(e)}")

	# 2. Reset Custom Flag in DB
	for dt in doctypes:
		try:
			if frappe.db.exists("DocType", dt):
				frappe.db.sql(
					"""
					UPDATE `tabDocType`
					SET custom = 0, module = %s
					WHERE name = %s
					""",
					(module_name, dt),
				)
				print(f"Reset custom flag for: {dt}")
		except Exception as e:
			print(f"Failed to reset custom for {dt}: {str(e)}")

	frappe.db.commit()

	# 3. Force Reload from JSON
	for dt in doctypes:
		try:
			frappe.reload_doc(module_name, "doctype", frappe.scrub(dt), force=True)
			print(f"Successfully reloaded: {dt}")
		except Exception as e:
			print(f"Failed to reload {dt}: {str(e)}")

	# 4. Clear Cache
	frappe.clear_cache()
	print("Repair complete.")


if __name__ == "__main__":
	run()
