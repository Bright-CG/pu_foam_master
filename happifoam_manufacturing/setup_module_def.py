import frappe

def create_module_def():
    # Verify or Create the Module Def required for the application
    module_name = "happifoam_manufacturing"
    
    if not frappe.db.exists("Module Def", module_name):
        doc = frappe.get_doc({
            "doctype": "Module Def",
            "module_name": module_name,
            "app_name": "happifoam_manufacturing"
        })
        doc.insert(ignore_permissions=True)
        print(f"Created Module Def: {module_name}")
    else:
        print(f"Module Def '{module_name}' already exists.")
        
    frappe.db.commit()

if __name__ == "__main__":
    create_module_def()
