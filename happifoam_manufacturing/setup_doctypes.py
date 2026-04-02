import os
import frappe

def create_doctypes():
    app_name = "Manufacturing"

    # 1. Production Inputs (Child Table)
    if not frappe.db.exists("DocType", "Production Inputs"):
        doc = frappe.get_doc({
            "doctype": "DocType",
            "name": "Production Inputs",
            "module": app_name,
            "custom": 0,
            "istable": 1,
            "fields": [
                {"fieldname": "item_code", "label": "Input", "fieldtype": "Link", "options": "Item", "reqd": 1, "in_list_view": 1},
                {"fieldname": "flow_factor", "label": "Flow Factor", "fieldtype": "Float", "reqd": 1, "in_list_view": 1},
                {"fieldname": "set_at", "label": "Set At", "fieldtype": "Float", "reqd": 1, "in_list_view": 1},
                {"fieldname": "flow_min", "label": "Flow Min", "fieldtype": "Float", "read_only": 1, "in_list_view": 1},
                {"fieldname": "qty_per_m3", "label": "Qty per m3", "fieldtype": "Float", "read_only": 1, "in_list_view": 1}
            ]
        })
        doc.insert(ignore_permissions=True)
        print("Created Production Inputs Table")
    else:
        print("Production Inputs Table already exists")

    # 2. Output Item Variant (Child Table)
    if not frappe.db.exists("DocType", "Output Item Variant"):
        doc = frappe.get_doc({
            "doctype": "DocType",
            "name": "Output Item Variant",
            "module": app_name,
            "custom": 0,
            "istable": 1,
            "fields": [
                {"fieldname": "item_type", "label": "Item Type", "fieldtype": "Select", "options": "Base Block\nMattress Core\nFoam Sheet", "reqd": 1, "in_list_view": 1},
                {"fieldname": "branding", "label": "Branding", "fieldtype": "Select", "options": "Legend\nGalaxy\nHospital\nStandard", "in_list_view": 1},
                {"fieldname": "width", "label": "Width (Inches)", "fieldtype": "Float", "reqd": 1, "in_list_view": 1},
                {"fieldname": "height", "label": "Height (Inches)", "fieldtype": "Float", "reqd": 1, "in_list_view": 1},
                {"fieldname": "length", "label": "Length (Inches)", "fieldtype": "Float", "reqd": 1, "in_list_view": 1},
                {"fieldname": "unit_cbm", "label": "Unit CBM", "fieldtype": "Float", "read_only": 1, "in_list_view": 1}
            ]
        })
        doc.insert(ignore_permissions=True)
        print("Created Output Item Variant Table")
    else:
        print("Output Item Variant Table already exists")

    # 3. Density Configuration
    if frappe.db.exists("DocType", "Density Configuration"):
        doc = frappe.get_doc("DocType", "Density Configuration")
        doc.fields = [] # Reset fields to ensure clean update
        doc.append("fields", {"fieldname": "density_name", "label": "Density Name", "fieldtype": "Data", "reqd": 1})
        doc.append("fields", {"fieldname": "density_code", "label": "Density Code", "fieldtype": "Data", "reqd": 1})
        doc.append("fields", {"fieldname": "density_value", "label": "Density Value (kg/m³)", "fieldtype": "Float", "reqd": 1})
        doc.append("fields", {"fieldname": "description", "label": "Description", "fieldtype": "Small Text"})
        
        doc.append("fields", {"fieldname": "machine_settings_sb", "label": "Machine Settings", "fieldtype": "Section Break"})
        doc.append("fields", {"fieldname": "blow_index", "label": "Blow Index", "fieldtype": "Float"})
        doc.append("fields", {"fieldname": "conveyor_speed", "label": "Conveyor Speed", "fieldtype": "Float"})
        doc.append("fields", {"fieldname": "calibration_factor", "label": "Calibration Factor", "fieldtype": "Float"})
        
        doc.append("fields", {"fieldname": "dimensions_sb", "label": "Block Dimensions", "fieldtype": "Section Break"})
        doc.append("fields", {"fieldname": "width_inches", "label": "Width Inches", "fieldtype": "Float"})
        doc.append("fields", {"fieldname": "height_inches", "label": "Height Inches", "fieldtype": "Float"})
        doc.append("fields", {"fieldname": "width_meters", "label": "Width Meters", "fieldtype": "Float", "read_only": 1})
        doc.append("fields", {"fieldname": "height_meters", "label": "Height Meters", "fieldtype": "Float", "read_only": 1})
        doc.append("fields", {"fieldname": "output_rate_m3_per_min", "label": "Output Rate m3 per Min", "fieldtype": "Float", "read_only": 1})

        doc.append("fields", {"fieldname": "raw_materials_sb", "label": "Raw Materials", "fieldtype": "Section Break"})
        doc.append("fields", {"fieldname": "production_inputs", "label": "Production Inputs", "fieldtype": "Table", "options": "Production Inputs"})

        doc.append("fields", {"fieldname": "output_variants_sb", "label": "Output Variants", "fieldtype": "Section Break"})
        doc.append("fields", {"fieldname": "output_item_variants", "label": "Output Item Variants", "fieldtype": "Table", "options": "Output Item Variant"})

        doc.append("fields", {"fieldname": "cb_control", "label": "Control Settings", "fieldtype": "Section Break"})
        doc.append("fields", {"fieldname": "auto_generate_items", "label": "Auto Generate Items", "fieldtype": "Check", "default": "0"})
        doc.append("fields", {"fieldname": "items_generated", "label": "Items Generated", "fieldtype": "Check", "default": "0", "read_only": 1})

        doc.custom = 0 # Ensure it's not custom so it exports
        doc.save(ignore_permissions=True)
        print("Updated Density Configuration")
    else:
        # Create from scratch if doesn't exist
        doc = frappe.get_doc({
            "doctype": "DocType",
            "name": "Density Configuration",
            "module": app_name,
            "custom": 0,
            "naming_rule": "Expression",
            "autoname": "DEN-.###",
            "fields": [
                {"fieldname": "density_name", "label": "Density Name", "fieldtype": "Data", "reqd": 1},
                {"fieldname": "density_code", "label": "Density Code", "fieldtype": "Data", "reqd": 1},
                {"fieldname": "density_value", "label": "Density Value (kg/m³)", "fieldtype": "Float", "reqd": 1},
                {"fieldname": "description", "label": "Description", "fieldtype": "Small Text"},
                
                {"fieldname": "machine_settings_sb", "label": "Machine Settings", "fieldtype": "Section Break"},
                {"fieldname": "blow_index", "label": "Blow Index", "fieldtype": "Float"},
                {"fieldname": "conveyor_speed", "label": "Conveyor Speed", "fieldtype": "Float"},
                {"fieldname": "calibration_factor", "label": "Calibration Factor", "fieldtype": "Float"},
                
                {"fieldname": "dimensions_sb", "label": "Block Dimensions", "fieldtype": "Section Break"},
                {"fieldname": "width_inches", "label": "Width Inches", "fieldtype": "Float"},
                {"fieldname": "height_inches", "label": "Height Inches", "fieldtype": "Float"},
                {"fieldname": "width_meters", "label": "Width Meters", "fieldtype": "Float", "read_only": 1},
                {"fieldname": "height_meters", "label": "Height Meters", "fieldtype": "Float", "read_only": 1},
                {"fieldname": "output_rate_m3_per_min", "label": "Output Rate m3 per Min", "fieldtype": "Float", "read_only": 1},

                {"fieldname": "raw_materials_sb", "label": "Raw Materials", "fieldtype": "Section Break"},
                {"fieldname": "production_inputs", "label": "Production Inputs", "fieldtype": "Table", "options": "Production Inputs"},

                {"fieldname": "output_variants_sb", "label": "Output Variants", "fieldtype": "Section Break"},
                {"fieldname": "output_item_variants", "label": "Output Item Variants", "fieldtype": "Table", "options": "Output Item Variant"},

                {"fieldname": "cb_control", "label": "Control Settings", "fieldtype": "Section Break"},
                {"fieldname": "auto_generate_items", "label": "Auto Generate Items", "fieldtype": "Check", "default": "0"},
                {"fieldname": "items_generated", "label": "Items Generated", "fieldtype": "Check", "default": "0", "read_only": 1}
            ]
        })
        doc.insert(ignore_permissions=True)
        print("Created Density Configuration")

    # 4. Item Custom Fields
    item_custom_fields = [
        {"fieldname": "custom_density_val", "label": "Density Value", "fieldtype": "Float", "insert_after": "item_group"},
        {"fieldname": "custom_length_in", "label": "Length (In)", "fieldtype": "Float", "insert_after": "custom_density_val"},
        {"fieldname": "custom_width_in", "label": "Width (In)", "fieldtype": "Float", "insert_after": "custom_length_in"},
        {"fieldname": "custom_height_in", "label": "Height (In)", "fieldtype": "Float", "insert_after": "custom_width_in"},
        {"fieldname": "custom_weight_kg", "label": "Weight (kg)", "fieldtype": "Float", "insert_after": "custom_height_in"},
        {"fieldname": "custom_cbm_val", "label": "CBM", "fieldtype": "Float", "insert_after": "custom_weight_kg"}
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


if __name__ == "__main__":
    create_doctypes()
