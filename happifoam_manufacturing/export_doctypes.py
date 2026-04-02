import frappe

def run():
    try:
        for dt in ["Block Size Table", "Density Configuration"]:
            if frappe.db.exists("DocType", dt):
                doc = frappe.get_doc("DocType", dt)
                if doc.custom == 1:
                    doc.custom = 0
                    doc.save(ignore_permissions=True)
                    print(f"Exported {dt} to App")
        frappe.db.commit()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    run()
