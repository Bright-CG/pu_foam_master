// Copyright (c) 2026, PU Foam Master and contributors
// For license information, please see license.txt

frappe.ui.form.on("Item", {
	refresh(frm) {
		recalc_item_cbm(frm);
	},
	custom_width(frm) {
		recalc_item_cbm(frm);
	},
	custom_height(frm) {
		recalc_item_cbm(frm);
	},
	custom_length(frm) {
		recalc_item_cbm(frm);
	},
});

function recalc_item_cbm(frm) {
	const width = flt(frm.doc.custom_width);
	const height = flt(frm.doc.custom_height);
	const length = flt(frm.doc.custom_length);
	if (width <= 0 || height <= 0 || length <= 0) {
		return;
	}
	frappe.db.get_single_value("Pufm Manufacturing Settings", "cbm_factor").then((factor) => {
		const cbmFactor = flt(factor) || 61023.74;
		const cbm = flt((length * width * height) / cbmFactor, 5);
		if (flt(frm.doc.custom_cbm_value) !== cbm) {
			frm.set_value("custom_cbm_value", cbm);
		}
	});
}
