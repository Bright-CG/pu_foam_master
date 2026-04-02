import frappe

def create_workspace():
    workspace_name = "Happifoam Manufacturing"
    schema = {
        "doctype": "Workspace",
        "name": workspace_name,
        "title": workspace_name,
        "module": "Happifoam Manufacturing",
        "public": 1,
        "content": '[{"id":"1","type":"header","data":{"text":"Configuration"}},{"id":"2","type":"shortcut","data":{"shortcut_name":"Density Configuration"}},{"id":"3","type":"header","data":{"text":"Production"}},{"id":"4","type":"shortcut","data":{"shortcut_name":"Production Batch"}},{"id":"5","type":"header","data":{"text":"Inventory"}},{"id":"6","type":"shortcut","data":{"shortcut_name":"Stock Transfer Request"}},{"id":"7","type":"header","data":{"text":"Reports"}},{"id":"8","type":"shortcut","data":{"shortcut_name":"Depot Stock Dashboard"}},{"id":"9","type":"shortcut","data":{"shortcut_name":"Production Variance Dashboard"}}]'
    }

    if frappe.db.exists("Workspace", workspace_name):
        doc = frappe.get_doc("Workspace", workspace_name)
        doc.update(schema)
        if doc.get("is_standard"):
            doc.is_standard = 0
        doc.save(ignore_permissions=True)
        print("Updated Workspace (v16 schema)")
    else:
        doc = frappe.new_doc("Workspace")
        doc.update(schema)
        doc.insert(ignore_permissions=True)
        print("Created Workspace (v16 schema)")
    
    frappe.db.commit()

if __name__ == "__main__":
    create_workspace()
