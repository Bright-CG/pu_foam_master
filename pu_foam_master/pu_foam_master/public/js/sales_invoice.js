frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		if (frm.doc.docstatus === 0) {
			return;
		}
		frm.add_custom_button(__("Create Job Order"), () => {
			frappe.new_doc("Pufm Job Order", {
				customer: frm.doc.customer,
				source_doctype: "Sales Invoice",
				source_document: frm.doc.name,
			});
		}, __("Create"));
	},
	custom_apply_instant_rebate(frm) {
		calculate_instant_rebate(frm);
	},
	custom_instant_rebate_percentage(frm) {
		calculate_instant_rebate(frm);
	},
});

["net_total", "discount_amount"].forEach((fieldname) => {
	frappe.ui.form.on("Sales Invoice", fieldname, (frm) => {
		calculate_instant_rebate(frm);
	});
});

function calculate_instant_rebate(frm) {
	if (!frm.doc.custom_apply_instant_rebate) {
		frm.set_value("custom_instant_rebate_amount", 0);
		return;
	}
	const base = flt(frm.doc.net_total) - flt(frm.doc.discount_amount);
	const amount = base * flt(frm.doc.custom_instant_rebate_percentage) / 100;
	frm.set_value("custom_instant_rebate_amount", amount);
}
