import frappe

def create_workspace():
    workspace_name = "Happifoam Manufacturing"
    
    # 1. Shortcuts (Buttons at the top)
    shortcuts = [
        {"label": "Density Configuration", "link_to": "Density Configuration", "type": "DocType", "icon": "settings"},
        {"label": "Production Batch", "link_to": "Production Batch", "type": "DocType", "icon": "list"},
        {"label": "Stock Transfer Request", "link_to": "Stock Transfer Request", "type": "DocType", "icon": "exchange"}
    ]

    # 2. Links (The vertical menu on the left)
    links = [
        {"label": "Configuration", "is_header": 1},
        {"label": "Density Configuration", "link_to": "Density Configuration", "link_type": "DocType", "type": "Link"},
        
        {"label": "Production", "is_header": 1},
        {"label": "Production Inputs", "link_to": "Production Inputs", "link_type": "DocType", "type": "Link"},
        
        {"label": "Inventory", "is_header": 1},
        {"label": "Output Item Variant", "link_to": "Output Item Variant", "link_type": "DocType", "type": "Link"}
    ]

    def _doctype_exists(entry):
        link_to = entry.get("link_to")
        return not link_to or frappe.db.exists("DocType", link_to)

    shortcuts = [s for s in shortcuts if _doctype_exists(s)]
    links = [l for l in links if l.get("is_header") or _doctype_exists(l)]

    schema = {
        "doctype": "Workspace",
        "name": workspace_name,
        "label": workspace_name,
        "title": workspace_name,
        "module": "PUFM Manufacturing",
        "public": 1,
        "is_standard": 1,
        "content": '[{"id":"h1","type":"header","data":{"text":"Configuration"}},{"id":"s1","type":"shortcut","data":{"shortcut_name":"Density Configuration"}},{"id":"h2","type":"header","data":{"text":"Production"}},{"id":"s2","type":"shortcut","data":{"shortcut_name":"Production Inputs"}},{"id":"h3","type":"header","data":{"text":"Inventory"}},{"id":"s3","type":"shortcut","data":{"shortcut_name":"Output Item Variant"}}]'
    }

    if frappe.db.exists("Workspace", workspace_name):
        doc = frappe.get_doc("Workspace", workspace_name)
        doc.update(schema)
        # Re-initialize child tables
        doc.set("shortcuts", [])
        doc.set("links", [])
        for s in shortcuts: doc.append("shortcuts", s)
        for l in links: doc.append("links", l)
        doc.save(ignore_permissions=True)
        print("Updated Workspace with clickable links")
    else:
        doc = frappe.new_doc("Workspace")
        doc.update(schema)
        for s in shortcuts: doc.append("shortcuts", s)
        for l in links: doc.append("links", l)
        doc.insert(ignore_permissions=True)
        print("Created Workspace with clickable links")
    
    frappe.db.commit()

if __name__ == "__main__":
    create_workspace()
