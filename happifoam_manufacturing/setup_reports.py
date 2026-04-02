import frappe

def create_reports():
    reports = [
        {"name": "Depot Stock Dashboard", "ref_dt": "Bin"},
        {"name": "Production Variance Dashboard", "ref_dt": "Production Batch"},
        {"name": "Production Efficiency Report", "ref_dt": "Density Run"}
    ]
    
    for r in reports:
        if not frappe.db.exists("Report", r["name"]):
            doc = frappe.get_doc({
                "doctype": "Report",
                "report_name": r["name"],
                "ref_doctype": r["ref_dt"],
                "report_type": "Report Builder",
                "is_standard": "Yes",
                "module": "Happifoam Manufacturing"
            })
            doc.insert(ignore_permissions=True)
            print(f"Created Report: {r['name']}")
            
    frappe.db.commit()

if __name__ == "__main__":
    create_reports()
