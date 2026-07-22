import frappe
import json
import os

def run():
    print("Starting Force Sync (Stability Mode)...")
    site = frappe.local.site
    doctypes = ["Density Configuration", "Production Inputs"]
    app_name = "happifoam_manufacturing"
    
    # CRITICAL: Disable developer_mode in the session to prevent 'export_doc' which fails due to module mapping
    # This allows us to update the DB without triggering filesystem export logic
    original_dev_mode = frappe.conf.developer_mode
    frappe.conf.developer_mode = 0
    print("Session developer_mode disabled for sync.")

    # 1. Reset Custom Flag & Module in DB
    print("Resetting custom flags in DB...")
    for dt_name in doctypes:
        if frappe.db.exists("DocType", dt_name):
            frappe.db.sql(f"UPDATE `tabDocType` SET custom=0, module=%s WHERE name=%s", (app_name, dt_name))
    frappe.db.commit()

    # 2. Manual JSON Import for Child Tables (if they are missing from DB)
    print("Checking for missing DocTypes...")
    # Use absolute path inside container
    app_dir = "/home/frappe/frappe-bench/apps/happifoam_manufacturing/happifoam_manufacturing"
    
    for dt in ["production_inputs"]:
        dt_name = "Production Inputs"
        if not frappe.db.exists("DocType", dt_name):
            path = os.path.join(app_dir, "doctype", dt, f"{dt}.json")
            if os.path.exists(path):
                print(f"Loading from {path}...")
                with open(path) as f:
                    data = json.load(f)
                    doc = frappe.get_doc(data)
                    doc.flags.ignore_permissions = True
                    # insert() will now work because export_doc is bypassed due to dev_mode=0
                    doc.insert()
                    print(f"Manually inserted DocType: {dt_name}")
        else:
            print(f"DocType already exists: {dt_name}")

    # 3. Standard Reload for All
    print("Reloading DocTypes from JSON...")
    for dt_name in doctypes:
        try:
            # reload_doc will also respect dev_mode=0 for its internal save() calls
            frappe.reload_doc(app_name, "doctype", frappe.scrub(dt_name), force=True)
            print(f"Reloaded DocType: {dt_name}")
        except Exception as e:
            print(f"Error reloading {dt_name}: {str(e)}")

    # Restore dev mode
    frappe.conf.developer_mode = original_dev_mode
    frappe.clear_cache()
    frappe.db.commit()
    print("Force Sync Finished.")

if __name__ == "__main__":
    run()
