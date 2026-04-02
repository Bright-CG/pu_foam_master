import frappe

def run():
    doc = frappe.get_doc("DocType", "Density Configuration")
    
    # Check if output_rate exists
    has_field = any(f.fieldname == "output_rate" for f in doc.fields)
    if not has_field:
        doc.append("fields", {
            "fieldname": "output_rate",
            "label": "Output Rate (CBM/min)",
            "fieldtype": "Float",
            "insert_after": "density_value",
            "reqd": 1,
            "default": "1.0"
        })
        
    doc.module = "happifoam_manufacturing"
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    print("Updated Density Configuration with output_rate and set module to happifoam_manufacturing")

if __name__ == "__main__":
    run()
