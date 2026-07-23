frappe.ui.form.on("Pufm Production Batch", {
	setup(frm) {
		frm.set_query("company", () => {
			return {
				query: "pu_foam_master.pufm_manufacturing.doctype.pufm_production_batch.pufm_production_batch.company_query",
			};
		});
	},
	onload(frm) {
		if (frm.is_new() && !frm.doc.company) {
			frappe.db.exists("Company", "Solarfoam").then((exists) => {
				if (exists) {
					frm.set_value("company", "Solarfoam");
				} else {
					frm.set_value("company", frappe.defaults.get_user_default("Company"));
				}
			});
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
