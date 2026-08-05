// Copyright (c) 2026, PU Foam Master and contributors
// For license information, please see license.txt

frappe.ui.form.on("Pufm Rebond Item Generator", {
	setup(frm) {
		frm.set_query("rebond_density", () => {
			return {
				query:
					"pu_foam_master.pufm_manufacturing.doctype.pufm_rebond_item_generator.pufm_rebond_item_generator.rebond_density_query",
			};
		});
	},
	generate_button(frm) {
		if (!frm.doc.rebond_density) {
			frappe.msgprint(__("Please select a Rebond Density Item."));
			return;
		}
		if (!frm.doc.block_sizes) {
			frappe.msgprint(__("Please enter block sizes (e.g. 75x72x10, 75x84x8)."));
			return;
		}
		frappe.call({
			method:
				"pu_foam_master.pufm_manufacturing.doctype.pufm_rebond_item_generator.pufm_rebond_item_generator.generate_rebond_items",
			args: {
				rebond_density: frm.doc.rebond_density,
				block_sizes: frm.doc.block_sizes,
			},
			freeze: true,
			freeze_message: __("Generating Rebound block items..."),
			callback(r) {
				const data = r.message || {};
				frappe.msgprint({
					title: __("Rebond Items"),
					indicator: "green",
					message: data.message || __("Done"),
				});
				frm.reload_doc();
			},
		});
	},
});
