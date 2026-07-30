frappe.ui.form.on("Sales Order", {
	refresh(frm) {
		if (frm.doc.docstatus === 0) {
			return;
		}
		frm.add_custom_button(__("Create Job Order"), () => {
			frappe.new_doc("Pufm Job Order", {
				customer: frm.doc.customer,
				source_doctype: "Sales Order",
				source_document: frm.doc.name,
			});
		}, __("Create"));
	},
});
