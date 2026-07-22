frappe.ui.form.on("Rebate Settlement Tool", {
	fetch_eligible_customers(frm) {
		if (!frm.doc.from_date || !frm.doc.to_date) {
			frappe.msgprint(__("Please set From Date and To Date first."));
			return;
		}
		frappe.call({
			method: "pu_foam_master.pufm_manufacturing.doctype.rebate_settlement_tool.rebate_settlement_tool.get_customers",
			args: {
				from_date: frm.doc.from_date,
				to_date: frm.doc.to_date,
				customer_group: frm.doc.customer_group,
			},
			callback(r) {
				frm.clear_table("entries");
				(r.message || []).forEach((row) => {
					const child = frm.add_child("entries");
					Object.assign(child, row);
				});
				frm.refresh_field("entries");
			},
		});
	},
});
