// Copyright (c) 2026, Happifoam and contributors
// For license information, please see license.txt

frappe.ui.form.on("Pufm Manufacturing Settings", {
	refresh(frm) {
		calculate_overheads(frm, true);
	},
	conversion_glue_cost_per_cbm(frm) {
		calculate_overheads(frm);
	},
	conversion_power_cost_per_cbm(frm) {
		calculate_overheads(frm);
	},
	conversion_labor_cost_per_cbm(frm) {
		calculate_overheads(frm);
	},
	gum_cost_per_m(frm) {
		calculate_overheads(frm);
	},
	thread_cost_per_m_quilt(frm) {
		calculate_overheads(frm);
	},
	non_woven_cost_per_m(frm) {
		calculate_overheads(frm);
	},
	quilting_labor_per_m(frm) {
		calculate_overheads(frm);
	},
});

function calculate_overheads(frm, silent) {
	const conv_total =
		flt(frm.doc.conversion_glue_cost_per_cbm) +
		flt(frm.doc.conversion_power_cost_per_cbm) +
		flt(frm.doc.conversion_labor_cost_per_cbm);
	const quilt_total =
		flt(frm.doc.gum_cost_per_m) +
		flt(frm.doc.thread_cost_per_m_quilt) +
		flt(frm.doc.non_woven_cost_per_m) +
		flt(frm.doc.quilting_labor_per_m);

	if (silent) {
		if (flt(frm.doc.conversion_rate_per_cbm) !== conv_total) {
			frm.doc.conversion_rate_per_cbm = conv_total;
			frm.refresh_field("conversion_rate_per_cbm");
		}
		if (flt(frm.doc.total_quilting_rate_per_m) !== quilt_total) {
			frm.doc.total_quilting_rate_per_m = quilt_total;
			frm.refresh_field("total_quilting_rate_per_m");
		}
		return;
	}

	frm.set_value("conversion_rate_per_cbm", conv_total);
	frm.set_value("total_quilting_rate_per_m", quilt_total);
}
