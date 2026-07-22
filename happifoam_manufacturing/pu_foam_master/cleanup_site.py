import frappe
from frappe.model.delete_doc import delete_doc
import happifoam_manufacturing.setup_doctypes as s
import happifoam_manufacturing.setup_workspace as w

def run():
    print("Starting Force Sync...")
    
    # 1. Cleanup existing records to force re-creation
    doctypes_to_clean = ['Density Configuration', 'Production Inputs', 'Block Size Table']
    for dt in doctypes_to_clean:
        if frappe.db.exists('DocType', dt):
            print(f"Deleting DocType: {dt}")
            delete_doc('DocType', dt, force=1)
    
    if frappe.db.exists('Workspace', 'Happifoam Manufacturing'):
        print("Deleting Workspace: Happifoam Manufacturing")
        delete_doc('Workspace', 'Happifoam Manufacturing', force=1)
        
    frappe.db.commit()
    
    # 2. Run Setups
    print("Running DocType Setup...")
    s.create_doctypes()
    
    print("Running Workspace Setup...")
    w.create_workspace()
    
    frappe.db.commit()
    print("Force Sync Completed Successfully")

if __name__ == "__main__":
    run()
