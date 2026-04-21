frappe.ui.form.on("Mattress Brand Policy", {
	refresh(frm) {
		frm.set_query("fabric_item", "allowed_fabrics", () => ({
			filters: {
				item_group: ["in", ["Quilted Fabric", "Plain Fabric"]]
			}
		}));
	}
});

frappe.ui.form.on("Allowed Fabric", {
	fabric_item(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.fabric_item) {
			frappe.model.set_value(cdt, cdn, "fabric_type", "");
			return;
		}

		frappe.db.get_doc("Item", row.fabric_item).then((item) => {
			const fabricType = item.item_name || item.custom_fabric_type || "";
			frappe.model.set_value(cdt, cdn, "fabric_type", fabricType);
		});
	}
});
