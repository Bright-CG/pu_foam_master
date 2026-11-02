frappe.ui.form.on("Rebate Balance Transfer", {
	main_customer(frm) {
		if (!frm.doc.main_customer) {
			frm.set_value("rebate_customer", "");
			return;
		}
		frappe.call({
			method:
				"pu_foam_master.pufm_manufacturing.doctype.rebate_balance_transfer.rebate_balance_transfer.get_rebate_customer_for_main",
			args: { main_customer: frm.doc.main_customer },
			callback(r) {
				const msg = r.message || {};
				if (!msg.rebate_customer) {
					frappe.msgprint(
						__(
							"This customer has no linked rebate wallet. Set Linked Rebate Customer on the Customer master."
						),
						{ indicator: "orange" }
					);
					frm.set_value("rebate_customer", "");
					return;
				}
				frm.set_value("rebate_customer", msg.rebate_customer);
				if (msg.available_credit != null) {
					frappe.show_alert({
						message: __("Available rebate credit: {0}", [
							frappe.format(msg.available_credit, { fieldtype: "Currency" }),
						]),
						indicator: "blue",
					});
				}
			},
		});
	},
});
