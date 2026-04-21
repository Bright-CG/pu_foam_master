frappe.ui.form.on("Mattress Production Entry", {
	refresh(frm) {
		frm.set_query("mattress_item", "production_items", () => ({
			filters: { item_group: "Finished Mattresses" }
		}));
	},
	validate(frm) {
		(frm.doc.production_items || []).forEach((row) => {
			if (flt(row.qty) <= 0) {
				frappe.throw(__("Quantity must be greater than zero in all production rows."));
			}
		});
	}
});

frappe.ui.form.on("Mattress Production Item", {
	mattress_item(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.mattress_item) {
			return;
		}
		set_fabric_filter(frm, row.mattress_item);
	},
	fabric_item(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.fabric_item) {
			return;
		}
		frappe.model.set_value(cdt, cdn, "fabric_batch", "");
	}
});

function set_fabric_filter(frm, mattressItem) {
	frappe.call({
		method: "pu_foam_master.pufm_manufacturing.doctype.mattress_production_entry.mattress_production_entry.get_allowed_fabric_items_for_mattress",
		args: { mattress_item: mattressItem },
		callback: (r) => {
			const allowedItems = r.message || [];
			frm.set_query("fabric_item", "production_items", () => ({
				filters: {
					name: ["in", allowedItems.length ? allowedItems : [""]]
				}
			}));
		}
	});
}
