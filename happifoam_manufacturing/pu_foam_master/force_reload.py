import frappe
import os
import sys

def run():
    print("Starting Recovery with Standard Pattern...")
    
    # 1. Environment Verification
    try:
        import happifoam_manufacturing
        print(f"App Package Found: {happifoam_manufacturing.__file__}")
    except ImportError:
        print("CRITICAL: happifoam_manufacturing package not found in sys.path")
        return

    module_name = "hf_manufacturing"
    app_name = "happifoam_manufacturing"

    # 2. Ensure Module Def exists
    if not frappe.db.exists("Module Def", module_name):
        print(f"Creating Module Def: {module_name}")
        m = frappe.get_doc({
            "doctype": "Module Def",
            "module_name": module_name,
            "app_name": app_name,
            "custom": 0
        })
        m.insert(ignore_permissions=True)
    
    # 3. Manual Module Mapping for this session
    if not hasattr(frappe.local, 'module_app'):
        frappe.local.module_app = {}
    frappe.local.module_app[module_name] = app_name
    print(f"Forced mapping: {module_name} -> {app_name}")

    # 4. Reload DocTypes
    doctypes = ["Density Configuration", "Production Inputs"]
    for dt_name in doctypes:
        try:
            scrubbed = frappe.scrub(dt_name)
            # Re-verify path exists
            module_path = frappe.get_module_path(module_name)
            expected_json = os.path.join(module_path, "doctype", scrubbed, f"{scrubbed}.json")
            
            if os.path.exists(expected_json):
                print(f"Found JSON for {dt_name} at: {expected_json}")
                frappe.reload_doc(module_name, "doctype", scrubbed, force=True)
                print(f"Successfully recovered {dt_name}")
            else:
                print(f"ERROR: JSON MISSING for {dt_name} at: {expected_json}")
        except Exception as e:
            print(f"Failed to recover {dt_name}: {str(e)}")

    frappe.db.commit()
    frappe.clear_cache()
    print("Recovery Finished.")

if __name__ == "__main__":
    run()
