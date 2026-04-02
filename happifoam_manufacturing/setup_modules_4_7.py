import frappe

def create_doctypes():
    app_name = "Happifoam Manufacturing"

    # 1. Custom Roles
    roles = ["Production Manager", "Approver", "Blockstore"]
    for role in roles:
        if not frappe.db.exists("Role", role):
            frappe.get_doc({
                "doctype": "Role",
                "role_name": role,
                "desk_access": 1
            }).insert(ignore_permissions=True)
            print(f"Created Role: {role}")

    # 2. Transfer Items Child Table
    if not frappe.db.exists("DocType", "Transfer Items"):
        doc = frappe.get_doc({
            "doctype": "DocType",
            "name": "Transfer Items",
            "module": app_name,
            "custom": 0,
            "istable": 1,
            "fields": [
                {"fieldname": "item_code", "label": "Item", "fieldtype": "Link", "options": "Item", "reqd": 1, "in_list_view": 1},
                {"fieldname": "qty", "label": "Quantity", "fieldtype": "Float", "reqd": 1, "in_list_view": 1},
                {"fieldname": "available_qty", "label": "Available Qty", "fieldtype": "Float", "read_only": 1, "in_list_view": 1}
            ]
        })
        doc.insert(ignore_permissions=True)
        print("Created Transfer Items")

    # 3. Stock Transfer Request
    if not frappe.db.exists("DocType", "Stock Transfer Request"):
        doc = frappe.get_doc({
            "doctype": "DocType",
            "name": "Stock Transfer Request",
            "module": app_name,
            "custom": 0,
            "is_submittable": 1,
            "naming_rule": "Expression",
            "autoname": "STR-.YYYY.-.#####",
            "fields": [
                {"fieldname": "from_warehouse", "label": "From Warehouse", "fieldtype": "Link", "options": "Warehouse", "reqd": 1, "in_list_view": 1},
                {"fieldname": "to_warehouse", "label": "To Warehouse", "fieldtype": "Link", "options": "Warehouse", "reqd": 1, "in_list_view": 1},
                {"fieldname": "requested_by", "label": "Requested By", "fieldtype": "Link", "options": "User", "reqd": 1, "default": frappe.session.user if frappe.session else "Administrator"},
                {"fieldname": "approved_by", "label": "Approved By", "fieldtype": "Link", "options": "User", "read_only": 1},
                {"fieldname": "status", "label": "Status", "fieldtype": "Select", "options": "Draft\nPending Approval\nApproved\nIn Transit\nCompleted", "default": "Draft", "reqd": 1, "in_list_view": 1},
                
                {"fieldname": "sb_items", "label": "Items", "fieldtype": "Section Break"},
                {"fieldname": "items", "label": "Transfer Items", "fieldtype": "Table", "options": "Transfer Items", "reqd": 1},
                
                {"fieldname": "sb_tracking", "label": "Tracking", "fieldtype": "Section Break"},
                {"fieldname": "stock_entry", "label": "Generated Stock Entry", "fieldtype": "Link", "options": "Stock Entry", "read_only": 1}
            ]
        })
        doc.insert(ignore_permissions=True)
        print("Created Stock Transfer Request")

    # 4. Production Cost Summary
    if not frappe.db.exists("DocType", "Production Cost Summary"):
        doc = frappe.get_doc({
            "doctype": "DocType",
            "name": "Production Cost Summary",
            "module": app_name,
            "custom": 0,
            "fields": [
                {"fieldname": "production_batch", "label": "Production Batch", "fieldtype": "Link", "options": "Production Batch", "reqd": 1},
                {"fieldname": "material_cost", "label": "Material Cost", "fieldtype": "Currency"},
                {"fieldname": "overhead_cost", "label": "Overhead Cost", "fieldtype": "Currency"},
                {"fieldname": "total_cost", "label": "Total Cost", "fieldtype": "Currency"},
                {"fieldname": "cost_per_unit", "label": "Cost per Unit", "fieldtype": "Currency"}
            ]
        })
        doc.insert(ignore_permissions=True)
        print("Created Production Cost Summary")

    # 5. KPI Snapshot
    if not frappe.db.exists("DocType", "KPI Snapshot"):
        doc = frappe.get_doc({
            "doctype": "DocType",
            "name": "KPI Snapshot",
            "module": app_name,
            "custom": 0,
            "fields": [
                {"fieldname": "date", "label": "Date", "fieldtype": "Date", "reqd": 1},
                {"fieldname": "total_production", "label": "Total Production (CBM)", "fieldtype": "Float"},
                {"fieldname": "total_sales", "label": "Total Sales", "fieldtype": "Currency"},
                {"fieldname": "total_cost", "label": "Total Cost", "fieldtype": "Currency"},
                {"fieldname": "profit", "label": "Profit", "fieldtype": "Currency"}
            ]
        })
        doc.insert(ignore_permissions=True)
        print("Created KPI Snapshot")

    frappe.db.commit()

if __name__ == "__main__":
    create_doctypes()
