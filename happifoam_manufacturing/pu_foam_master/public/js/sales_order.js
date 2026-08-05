frappe.ui.form.on("Sales Order", {
	refresh(frm) {
		if (frm.doc.docstatus === 2) {
			return;
		}

		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Create Job Order"), () => {
				frappe.new_doc("Pufm Job Order", {
					customer: frm.doc.customer,
					source_doctype: "Sales Order",
					source_document: frm.doc.name,
				});
			}, __("Create"));
		}

		if (!frm.is_new() && (frm.doc.items || []).length) {
			frm.add_custom_button(__("Request Production"), () => {
				frappe.call({
					method: "pu_foam_master.sales.request_production.request_production",
					args: { sales_order: frm.doc.name },
					freeze: true,
					freeze_message: __("Checking stock and creating factory docs..."),
					callback(r) {
						const data = r.message || {};
						frappe.msgprint({
							title: __("Request Production"),
							indicator: data.created && data.created.length ? "green" : "blue",
							message: data.message || __("Done"),
						});
					},
				});
			});
		}
	},
});
