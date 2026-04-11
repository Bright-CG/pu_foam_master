import frappe

def create_workspace():
    workspace_name = "Happifoam Manufacturing"
    
    # Define shortcuts and links separately for a cleaner setup
    shortcuts = [
        {"type": "Shortcut", "label": "Density Configuration", "link_to": "Density Configuration", "icon": "settings"},
        {"type": "Shortcut", "label": "Production Batch", "link_to": "Production Batch", "icon": "list"},
        {"type": "Shortcut", "label": "Stock Transfer Request", "link_to": "Stock Transfer Request", "icon": "exchange"},
        {"type": "Shortcut", "label": "Depot Stock Dashboard", "link_to": "Depot Stock Dashboard", "icon": "dashboard"},
        {"type": "Shortcut", "label": "Production Variance Dashboard", "link_to": "Production Variance Dashboard", "icon": "dashboard"}
    ]

    links = [
        {"type": "Link", "label": "Configuration", "is_header": 1},
        {"type": "Link", "label": "Density Configuration", "link_to": "Density Configuration", "link_type": "DocType"},
        {"type": "Link", "label": "Production", "is_header": 1},
        {"type": "Link", "label": "Production Batch", "link_to": "Production Batch", "link_type": "DocType"},
        {"type": "Link", "label": "Inventory", "is_header": 1},
        {"type": "Link", "label": "Stock Transfer Request", "link_to": "Stock Transfer Request", "link_type": "DocType"},
        {"type": "Link", "label": "Reports", "is_header": 1}
    ]

    schema = {
        "doctype": "Workspace",
        "name": workspace_name,
        "title": workspace_name,
        "module": "happifoam_manufacturing",
        "public": 1,
        "is_standard": 1,
        "content": '[{"id":"1","type":"header","data":{"text":"Happifoam Manufacturing"}},{"id":"2","type":"shortcut","data":{"shortcut_name":"Density Configuration"}},{"id":"3","type":"shortcut","data":{"shortcut_name":"Production Batch"}},{"id":"4","type":"shortcut","data":{"shortcut_name":"Stock Transfer Request"}}]'
    }

    if frappe.db.exists("Workspace", workspace_name):
        doc = frappe.get_doc("Workspace", workspace_name)
        doc.update(schema)
        # Clear child tables to ensure fresh setup
        doc.shortcuts = []
        doc.links = []
        for s in shortcuts: doc.append("shortcuts", s)
        for l in links: doc.append("links", l)
        doc.save(ignore_permissions=True)
        print("Updated Workspace")
    else:
        doc = frappe.new_doc("Workspace")
        doc.update(schema)
        for s in shortcuts: doc.append("shortcuts", s)
        for l in links: doc.append("links", l)
        doc.insert(ignore_permissions=True)
        print("Created Workspace")
    
    frappe.db.commit()

if __name__ == "__main__":
    create_workspace()
