frappe.ui.form.on("Pufm Production Batch", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("Add New Density Run"), () => {
				frappe.new_doc("Pufm Density Run", {
					parent_batch: frm.doc.name
				});
			});

			frm.add_custom_button(__("View Density Runs"), () => {
				frappe.set_route("List", "Pufm Density Run", {
					parent_batch: frm.doc.name
				});
			});
		}
	}
});
