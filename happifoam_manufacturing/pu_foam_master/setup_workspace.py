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
    # Architecture:
    #   Section 1 – Configuration
    #     • Density Configuration  (standalone DocType – master recipe)
    #   Section 2 – Production
    #     • Production Reporting   (PUFM Production Batch – daily batch folder)
    #     • PUFM Density Run       (individual production run inside a batch)
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
            "label": "Production Reporting",   # maps to PUFM Production Batch
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

    # ── Guard: skip any entry whose target DocType doesn't exist in the DB yet ───
    def _doctype_exists(entry):
        link_to = entry.get("link_to")
        return not link_to or frappe.db.exists("DocType", link_to)

    shortcuts = [s for s in shortcuts if _doctype_exists(s)]
    links = [l for l in links if l.get("is_header") or _doctype_exists(l)]

    # ── Content JSON: drives the visual layout of the workspace page body ────────
    # Each block has a unique id; shortcut_name must match the 'label' field above.
    content = (
        '['
        # Configuration header + shortcut
        '{"id":"h1","type":"header","data":{"text":"Configuration","col":12}},'
        '{"id":"s1","type":"shortcut","data":{"shortcut_name":"Density Configuration","col":4}},'
        # Production header + shortcuts
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

    # ── Upsert: update if workspace exists, create otherwise ─────────────────────
    if frappe.db.exists("Workspace", workspace_name):
        doc = frappe.get_doc("Workspace", workspace_name)
        doc.update(schema)
        # Wipe and rebuild child tables so stale entries don't persist
        doc.set("shortcuts", [])
        doc.set("links", [])
        for s in shortcuts:
            doc.append("shortcuts", s)
        for l in links:
            doc.append("links", l)
        doc.save(ignore_permissions=True)
        print(f"[setup_workspace] Updated '{workspace_name}' workspace.")
    else:
        doc = frappe.new_doc("Workspace")
        doc.update(schema)
        for s in shortcuts:
            doc.append("shortcuts", s)
        for l in links:
            doc.append("links", l)
        doc.insert(ignore_permissions=True)
        print(f"[setup_workspace] Created '{workspace_name}' workspace.")

    frappe.db.commit()


if __name__ == "__main__":
    create_workspace()
