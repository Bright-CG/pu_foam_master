frappe.ui.form.on("Pufm Production Batch", {
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

		// Stock posts only on Submit / reverses on Cancel — not on Draft or workflow status.
		if (frm.dashboard && frm.dashboard.set_headline) {
			if (frm.doc.docstatus === 0) {
				frm.dashboard.set_headline(
					__("Save as Draft freely. Submit to post the manufacture Stock Entry.")
				);
			} else if (frm.doc.docstatus === 1) {
				frm.dashboard.set_headline(
					__("Submitted — linked Stock Entry is posted. Cancel to reverse stock.")
				);
			}
		}
	},
});
