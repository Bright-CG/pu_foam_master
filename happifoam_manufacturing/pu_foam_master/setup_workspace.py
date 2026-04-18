import frappe


def create_workspace():
    workspace_name = "Happifoam Manufacturing"

    # ── 1. Shortcuts (quick-access buttons rendered at the top of the workspace) ──
    # Only standalone DocTypes that users navigate to directly.
    # Child tables (Production Inputs, BOM Operation, PUFM Produced Block) are excluded.
    shortcuts = [
        {
            "label": "Density Configuration",
            "link_to": "Density Configuration",
            "type": "DocType",
            "icon": "settings",
        },
        {
            "label": "Production Reporting",
            "link_to": "PUFM Production Batch",
            "type": "DocType",
            "icon": "manufacturing",
        },
        {
            "label": "Density Run",
            "link_to": "PUFM Density Run",
            "type": "DocType",
            "icon": "list",
        },
    ]

    # ── 2. Links (sidebar navigation menu) ───────────────────────────────────────
    links = [
        # ── Configuration ────────────────────────────────────────────────────────
        {"label": "Configuration", "is_header": 1},
        {
            "label": "Density Configuration",
            "link_to": "Density Configuration",
            "link_type": "DocType",
            "type": "Link",
        },
        # ── Production ───────────────────────────────────────────────────────────
        {"label": "Production", "is_header": 1},
        {
            "label": "Production Reporting",
            "link_to": "PUFM Production Batch",
            "link_type": "DocType",
            "type": "Link",
        },
        {
            "label": "PUFM Density Run",
            "link_to": "PUFM Density Run",
            "link_type": "DocType",
            "type": "Link",
        },
    ]

    # Content JSON must contain shortcut_name that matches the label in shortcuts list
    content = (
        '['
        '{"id":"h1","type":"header","data":{"text":"Configuration","col":12}},'
        '{"id":"s1","type":"shortcut","data":{"shortcut_name":"Density Configuration","col":4}},'
        '{"id":"h2","type":"header","data":{"text":"Production","col":12}},'
        '{"id":"s2","type":"shortcut","data":{"shortcut_name":"Production Reporting","col":4}},'
        '{"id":"s3","type":"shortcut","data":{"shortcut_name":"Density Run","col":4}}'
        ']'
    )

    schema = {
        "doctype": "Workspace",
        "name": workspace_name,
        "label": workspace_name,
        "title": workspace_name,
        "module": "pufm_manufacturing",
        "public": 1,
        "is_standard": 1,
        "content": content,
    }

    # ── Upsert Logic ─────────────────────────────────────────────────────────────
    if frappe.db.exists("Workspace", workspace_name):
        doc = frappe.get_doc("Workspace", workspace_name)
    else:
        doc = frappe.new_doc("Workspace")
        doc.name = workspace_name

    doc.update(schema)

    # Force clear and rebuild child tables (Shortcuts and Links)
    doc.set("shortcuts", [])
    doc.set("links", [])

    for s in shortcuts:
        doc.append("shortcuts", s)
    for l in links:
        doc.append("links", l)

    doc.save(ignore_permissions=True)
    print(f"[setup_workspace] Successfully synced '{workspace_name}' workspace.")

    frappe.db.commit()


if __name__ == "__main__":
    create_workspace()
