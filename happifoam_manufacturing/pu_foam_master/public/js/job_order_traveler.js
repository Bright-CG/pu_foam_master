// Copyright (c) 2026, PU Foam Master and contributors
// Shared Job Order traveler HTML helper for factory DocTypes.

window.pufm_fetch_job_instructions = function (frm) {
	if (!frm.doc.job_order) {
		if (frm.fields_dict.job_instructions_html) {
			frm.fields_dict.job_instructions_html.$wrapper.html(
				"<p class='text-muted'>Select a Job Order to load traveler instructions.</p>"
			);
		}
		return;
	}
	frappe.call({
		method:
			"pu_foam_master.pufm_manufacturing.doctype.pufm_job_order.pufm_job_order.get_job_order_instructions_html",
		args: { job_order: frm.doc.job_order },
		callback(r) {
			if (frm.fields_dict.job_instructions_html) {
				frm.fields_dict.job_instructions_html.$wrapper.html(r.message || "");
			}
		},
	});
};
