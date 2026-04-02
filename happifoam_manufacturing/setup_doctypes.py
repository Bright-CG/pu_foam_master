import os
import frappe

def create_doctypes():
    app_name = "Happifoam Manufacturing"

    # 1. Block Size Table
    if not frappe.db.exists("DocType", "Block Size Table"):
        doc = frappe.get_doc({
            "doctype": "DocType",
            "name": "Block Size Table",
            "module": app_name,
            "custom": 1,
            "istable": 1,
            "fields": [
                {"fieldname": "size_name", "label": "Size Name", "fieldtype": "Data", "reqd": 1, "in_list_view": 1},
                {"fieldname": "length", "label": "Length (mm)", "fieldtype": "Float", "reqd": 1, "in_list_view": 1},
                {"fieldname": "width", "label": "Width (mm)", "fieldtype": "Float", "reqd": 1, "in_list_view": 1},
                {"fieldname": "height", "label": "Height (mm)", "fieldtype": "Float", "reqd": 1, "in_list_view": 1}
            ]
        })
        doc.insert(ignore_permissions=True)
        print("Created Block Size Table")
    else:
        print("Block Size Table already exists")

    # 2. Density Configuration
    if not frappe.db.exists("DocType", "Density Configuration"):
        doc = frappe.get_doc({
            "doctype": "DocType",
            "name": "Density Configuration",
            "module": app_name,
            "custom": 1,
            "naming_rule": "Expression",
            "autoname": "DEN-.###",
            "fields": [
                {"fieldname": "density_name", "label": "Density Name", "fieldtype": "Data", "reqd": 1},
                {"fieldname": "density_code", "label": "Density Code", "fieldtype": "Data", "reqd": 1},
                {"fieldname": "density_value", "label": "Density Value (kg/m³)", "fieldtype": "Float", "reqd": 1},
                {"fieldname": "description", "label": "Description", "fieldtype": "Small Text"},
                {"fieldname": "cb_sizing", "label": "Block Sizing", "fieldtype": "Section Break"},
                {"fieldname": "block_sizes", "label": "Available Block Sizes", "fieldtype": "Table", "options": "Block Size Table", "reqd": 1},
                {"fieldname": "cb_control", "label": "Control Settings", "fieldtype": "Section Break"},
                {"fieldname": "auto_generate_items", "label": "Auto Generate Items", "fieldtype": "Check", "default": "0"},
                {"fieldname": "items_generated", "label": "Items Generated", "fieldtype": "Check", "default": "0", "read_only": 1}
            ]
        })
        doc.insert(ignore_permissions=True)
        print("Created Density Configuration")
    else:
        print("Density Configuration already exists")

    # 3. Item Custom Fields
    item_custom_fields = [
        {"fieldname": "custom_density", "label": "Density", "fieldtype": "Float", "insert_after": "item_group"},
        {"fieldname": "custom_length", "label": "Length", "fieldtype": "Float", "insert_after": "custom_density"},
        {"fieldname": "custom_width", "label": "Width", "fieldtype": "Float", "insert_after": "custom_length"},
        {"fieldname": "custom_height", "label": "Height", "fieldtype": "Float", "insert_after": "custom_width"},
        {"fieldname": "custom_weight", "label": "Weight (kg)", "fieldtype": "Float", "insert_after": "custom_height"},
        {"fieldname": "custom_cbm", "label": "CBM", "fieldtype": "Float", "insert_after": "custom_weight"}
    ]

    for cf in item_custom_fields:
        if not frappe.db.exists("Custom Field", f"Item-{cf['fieldname']}"):
            cf.update({
                "doctype": "Custom Field",
                "dt": "Item",
                "module": app_name
            })
            frappe.get_doc(cf).insert(ignore_permissions=True)
            print(f"Created Custom Field: {cf['fieldname']}")

    frappe.db.commit()
    print("Done setting up Doctypes")

if __name__ == "__main__":
    create_doctypes()
