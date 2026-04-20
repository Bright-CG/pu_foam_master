import frappe
import os

def execute():
    main_doctypes = [
        "Pufm Production Batch",
        "Pufm Density Run",
        "Density Configuration",
        "Pufm Manufacturing Settings",
        "Foam Block Conversion",
    ]
    
    child_tables = [
        "BOM Operation",
        "Production Inputs",
        "Pufm Produced Block",
        "Output Item Variant",
        "Block Conversion Input",
        "Block Conversion Output",
    ]
    
    module_name = "pufm_manufacturing"
    app_name = "pu_foam_master" # Ensure this matches the app name in bench
    
    submittable_map = {
        "Pufm Production Batch": 1,
        "Pufm Density Run": 1,
        "Density Configuration": 0,
        "Pufm Manufacturing Settings": 0,
        "Foam Block Conversion": 1,
    }
    
    for dt in main_doctypes + child_tables:
        try:
            # Always ensure it is loaded into the DB first
            if not frappe.db.exists("DocType", dt):
                dt_scrubbed = frappe.scrub(dt)
                frappe.reload_doc(module_name, "doctype", dt_scrubbed, force=True)
                print(f"✅ {dt} - Restored to DB")
            
            # Fetch and apply required settings unconditionally to fix the Frappe acronym bug
            doctype_doc = frappe.get_doc("DocType", dt)
            doctype_doc.module = module_name
            # Set custom = 0 as we are abandoning the custom workaround
            doctype_doc.custom = 0
            
            if dt in main_doctypes:
                doctype_doc.is_submittable = submittable_map.get(dt, 0)
                
                # Ensure "System Manager" permissions exist
                has_sys_mgr = any(p.role == "System Manager" for p in doctype_doc.permissions)
                if not has_sys_mgr:
                    doctype_doc.append("permissions", {
                        "role": "System Manager",
                        "read": 1,
                        "write": 1,
                        "create": 1,
                        "delete": 1,
                        "submit": doctype_doc.is_submittable,
                        "cancel": doctype_doc.is_submittable,
                        "amend": doctype_doc.is_submittable
                    })
            elif dt in child_tables:
                # Ensure child tables are correctly identified
                doctype_doc.istable = 1
            
            doctype_doc.save(ignore_permissions=True)
            frappe.db.commit()
            print(f"✅ {dt} - Updated successfully (Module: {module_name}, Custom: {doctype_doc.custom})")
        except Exception as e:
            print(f"❌ {dt} - Failed to sync: {str(e)}")

# This allows running via bench execute directly if the file is imported or passed
if __name__ == "__main__":
    execute()
