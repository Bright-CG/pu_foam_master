import frappe

def run():
    module_name = "happifoam_manufacturing"
    if not frappe.db.exists("Module Def", module_name):
        frappe.get_doc({
            "doctype": "Module Def",
            "module_name": module_name,
            "app_name": "happifoam_manufacturing"
        }).insert(ignore_permissions=True)
        print(f"Created Module Def: {module_name}")
    else:
        print(f"Module Def {module_name} already exists")

    doctypes = ["Density Configuration", "Production Inputs", "Production Batch", "Stock Transfer Request"]
    for dt in doctypes:
        if frappe.db.exists("DocType", dt):
            frappe.db.set_value("DocType", dt, "module", module_name)
            print(f"Fixed Module for {dt}")
    
    frappe.db.commit()

if __name__ == "__main__":
    run()
