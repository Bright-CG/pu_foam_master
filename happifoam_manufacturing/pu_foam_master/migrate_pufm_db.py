import frappe

def execute():
    # Mapping of old DocType names to new DocType names
    rename_map = {
        "PUFM Production Batch": "Pufm Production Batch",
        "PUFM Density Run": "Pufm Density Run",
        "PUFM Produced Block": "Pufm Produced Block",
        "PUFM Manufacturing Settings": "Pufm Manufacturing Settings"
    }
    
    # Single DocTypes (Don't have their own tables)
    singles = ["PUFM Manufacturing Settings"]

    print("🚀 Starting Database Migration: PUFM -> Pufm")

    for old, new in rename_map.items():
        print(f"\nProcessing {old}...")

        # 1. Rename tabDocType entry
        frappe.db.sql("UPDATE `tabDocType` SET name=%s WHERE name=%s", (new, old))
        print(f"  ✅ Renamed DocType metadata: {new}")

        # 2. Rename Physical Table (if not a Single DocType)
        if old not in singles:
            old_table = f"tab{old}"
            new_table = f"tab{new}"
            
            # Check if old table exists before renaming
            if frappe.db.table_exists(old):
                frappe.db.sql(f"RENAME TABLE `{old_table}` TO `{new_table}`")
                print(f"  ✅ Renamed Table: {old_table} -> {new_table}")
            else:
                print(f"  ⚠️  Table {old_table} not found, skipping rename.")
        else:
            # Update Single values in tabSingles
            frappe.db.sql("UPDATE `tabSingles` SET doctype=%s WHERE doctype=%s", (new, old))
            print(f"  ✅ Updated tabSingles for {new}")

    # 3. Update parenttype for child records
    # Specifically for Pufm Produced Block which lives under Pufm Density Run
    print("\nUpdating child table parent references...")
    frappe.db.sql("""
        UPDATE `tabPufm Produced Block` 
        SET parenttype = 'Pufm Density Run' 
        WHERE parenttype = 'PUFM Density Run'
    """)
    print("  ✅ Updated parenttype in tabPufm Produced Block")

    # 4. Final Commit
    frappe.db.commit()
    print("\n🎉 Database migration completed successfully.")
    print("👉 Next Step: Run 'bench migrate' to align schema changes.")
