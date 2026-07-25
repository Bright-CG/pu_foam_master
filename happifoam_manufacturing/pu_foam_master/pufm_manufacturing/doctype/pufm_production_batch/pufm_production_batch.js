frappe.ui.form.on("Pufm Production Batch", {
	setup(frm) {
		// Density Runs are linked docs (not a child table); warehouse filter lives on
		// Pufm Density Run. Keep company scoped via User Permissions on Company Link.
		frm.set_query("target_warehouse", "density_runs", () => {
			return {
				filters: {
					company: frm.doc.company,
					disabled: 0,
				},
			};
		});
	},
	onload(frm) {
		if (frm.is_new() && !frm.doc.company) {
			const user_company = frappe.defaults.get_user_default("Company");
			if (user_company) {
				frm.set_value("company", user_company);
			}
		}
	},
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("Add New Density Run"), () => {
				frappe.new_doc("Pufm Density Run", {
					parent_batch: frm.doc.name,
				});
			});

			frm.add_custom_button(__("View Density Runs"), () => {
				frappe.set_route("List", "Pufm Density Run", {
					parent_batch: frm.doc.name,
				});
			});
		}
	},
});
