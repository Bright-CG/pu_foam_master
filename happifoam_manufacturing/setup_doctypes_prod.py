import frappe

def create_doctypes():
    app_name = "Happifoam Manufacturing"

    # 1. Produced Item
    if not frappe.db.exists("DocType", "Produced Item"):
        doc = frappe.get_doc({
            "doctype": "DocType",
            "name": "Produced Item",
            "module": app_name,
            "custom": 0,
            "istable": 1,
            "fields": [
                {"fieldname": "density_run_id", "label": "Density Run ID", "fieldtype": "Data", "reqd": 1, "in_list_view": 1},
                {"fieldname": "item_code", "label": "Item Code", "fieldtype": "Link", "options": "Item", "reqd": 1, "in_list_view": 1},
                {"fieldname": "qty", "label": "Quantity", "fieldtype": "Float", "reqd": 1, "in_list_view": 1},
                {"fieldname": "cbm_per_unit", "label": "CBM per Unit", "fieldtype": "Float", "reqd": 1, "fetch_from": "item_code.custom_cbm"},
                {"fieldname": "total_cbm", "label": "Total CBM", "fieldtype": "Float", "read_only": 1, "in_list_view": 1}
            ]
        })
        doc.insert(ignore_permissions=True)
        print("Created Produced Item")

    # 2. Density Run
    if not frappe.db.exists("DocType", "Density Run"):
        doc = frappe.get_doc({
            "doctype": "DocType",
            "name": "Density Run",
            "module": app_name,
            "custom": 0,
            "istable": 1,
            "fields": [
                {"fieldname": "density", "label": "Density", "fieldtype": "Link", "options": "Density Configuration", "reqd": 1, "in_list_view": 1},
                {"fieldname": "runtime_minutes", "label": "Runtime (Minutes)", "fieldtype": "Float", "reqd": 1, "in_list_view": 1},
                {"fieldname": "output_rate", "label": "Output Rate", "fieldtype": "Float", "reqd": 1},
                {"fieldname": "expected_cbm", "label": "Expected CBM", "fieldtype": "Float", "read_only": 1, "in_list_view": 1},
                {"fieldname": "actual_cbm", "label": "Actual CBM", "fieldtype": "Float", "read_only": 1, "in_list_view": 1},
                {"fieldname": "variance_cbm", "label": "Variance CBM", "fieldtype": "Float", "read_only": 1},
                {"fieldname": "variance_percent", "label": "Yield Variance (%)", "fieldtype": "Float", "read_only": 1, "in_list_view": 1},
                {"fieldname": "variance_flag", "label": "Variance Flag", "fieldtype": "Select", "options": "\nNormal\nWarning\nCritical", "read_only": 1},
                {"fieldname": "requires_attention", "label": "Requires Attention", "fieldtype": "Check", "read_only": 1},
                {"fieldname": "cost_share", "label": "Cost Share", "fieldtype": "Currency", "read_only": 1}
            ]
        })
        doc.insert(ignore_permissions=True)
        print("Created Density Run")

    # 3. Production Batch
    if not frappe.db.exists("DocType", "Production Batch"):
        doc = frappe.get_doc({
            "doctype": "DocType",
            "name": "Production Batch",
            "module": app_name,
            "custom": 0,
            "is_submittable": 1,
            "naming_rule": "Expression",
            "autoname": "PB-YYYY-.####",
            "fields": [
                {"fieldname": "date", "label": "Date", "fieldtype": "Date", "reqd": 1, "default": "Today", "in_list_view": 1},
                {"fieldname": "production_manager", "label": "Production Manager", "fieldtype": "Link", "options": "User", "default": frappe.session.user if frappe.session else "Administrator"},
                {"fieldname": "approval_status", "label": "Approval Status", "fieldtype": "Select", "options": "Draft\nPending Approval\nApproved\nRejected", "default": "Draft", "read_only": 1, "in_list_view": 1},
                {"fieldname": "approved_by", "label": "Approved By", "fieldtype": "Link", "options": "User", "read_only": 1},
                {"fieldname": "blockstore_status", "label": "Blockstore Status", "fieldtype": "Select", "options": "Pending\nConfirmed", "default": "Pending", "read_only": 1, "in_list_view": 1},
                {"fieldname": "confirmed_by", "label": "Confirmed By", "fieldtype": "Link", "options": "User", "read_only": 1},
                
                {"fieldname": "sb_runs", "label": "Production Runs", "fieldtype": "Section Break"},
                {"fieldname": "density_runs", "label": "Density Runs", "fieldtype": "Table", "options": "Density Run", "reqd": 1},
                
                {"fieldname": "sb_items", "label": "Produced Items", "fieldtype": "Section Break"},
                {"fieldname": "produced_items", "label": "Produced Items", "fieldtype": "Table", "options": "Produced Item"},
                
                {"fieldname": "sb_totals", "label": "Production Totals", "fieldtype": "Section Break"},
                {"fieldname": "total_expected_cbm", "label": "Total Expected CBM", "fieldtype": "Float", "read_only": 1},
                {"fieldname": "total_actual_cbm", "label": "Total Actual CBM", "fieldtype": "Float", "read_only": 1},
                {"fieldname": "total_variance_cbm", "label": "Total Variance CBM", "fieldtype": "Float", "read_only": 1},
                {"fieldname": "total_variance_percent", "label": "Total Yield Variance (%)", "fieldtype": "Float", "read_only": 1, "in_list_view": 1},
                
                {"fieldname": "sb_costs", "label": "Costing", "fieldtype": "Section Break"},
                {"fieldname": "labour_cost", "label": "Labour Cost", "fieldtype": "Currency"},
                {"fieldname": "power_cost", "label": "Power Cost", "fieldtype": "Currency"},
                {"fieldname": "overhead_cost", "label": "Overhead Cost", "fieldtype": "Currency"},
                {"fieldname": "total_production_cost", "label": "Total Production Cost", "fieldtype": "Currency", "read_only": 1},
                
                {"fieldname": "stock_entry_created", "label": "Stock Entry Created", "fieldtype": "Check", "read_only": 1, "hidden": 1}
            ]
        })
        doc.insert(ignore_permissions=True)
        print("Created Production Batch")

    frappe.db.commit()

if __name__ == "__main__":
    create_doctypes()
