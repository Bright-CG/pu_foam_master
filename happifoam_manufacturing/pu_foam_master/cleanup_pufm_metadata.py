import frappe
import os
import json

def execute():
    """
    Deletes any old Property Setter, Custom Field, or Client Script/Custom Script
    records in the database that still reference the old PUFM strings.
    Also ensures 'custom': 0 is maintained in all DocType JSON files.
    """
    # 1. Cleanup stale metadata from DB
    metadata_types = {
        "Property Setter": "doc_type",
        "Custom Field": "dt",
        "Client Script": "dt",
        "Custom Script": "dt"
    }

    print("Starting metadata cleanup...")
    for doctype, filter_field in metadata_types.items():
        if frappe.db.exists("DocType", doctype):
            stale_records = frappe.get_all(doctype, filters={filter_field: ("like", "PUFM%")})
            for record in stale_records:
                frappe.delete_doc(doctype, record.name, force=1)
                print(f"Deleted {doctype}: {record.name}")
                
    print("Cleanup of old PUFM DB metadata complete.")
    frappe.db.commit()

    # 2. Ensure "custom": 0 is maintained in all JSON files
    print("Checking JSON files for 'custom': 0 property...")
    app_path = frappe.get_app_path("pu_foam_master")
    doctype_dir = os.path.join(app_path, "pufm_manufacturing", "doctype")
    
    if os.path.exists(doctype_dir):
        for doctype_name in os.listdir(doctype_dir):
            if os.path.isdir(os.path.join(doctype_dir, doctype_name)):
                doctype_path = os.path.join(doctype_dir, doctype_name, f"{doctype_name}.json")
                if os.path.exists(doctype_path):
                    with open(doctype_path, 'r') as f:
                        try:
                            data = json.load(f)
                        except Exception as e:
                            print(f"Error parsing {doctype_path}: {e}")
                            continue
                    
                    if "custom" not in data or data.get("custom") != 0:
                        data["custom"] = 0
                        with open(doctype_path, 'w') as f:
                            json.dump(data, f, indent=4)
                        print(f"Maintained 'custom': 0 in {doctype_name}.json")
                        
    print("Phase 3 script execution complete.")
