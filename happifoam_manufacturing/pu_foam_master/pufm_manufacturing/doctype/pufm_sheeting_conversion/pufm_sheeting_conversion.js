// Copyright (c) 2026, PU Foam Master and contributors
// For license information, please see license.txt

frappe.ui.form.on("Pufm Sheeting Conversion", {
	setup(frm) {
		frm.set_query("source_block", "sheeting_outputs", () => {
			return {
				filters: {
					disabled: 0,
					is_stock_item: 1,
				},
			};
		});
		frm.set_query("job_order", () => {
			return {
				filters: {
					docstatus: ["<", 2],
					order_type: "Sheetings",
				},
			};
		});
	},
	onload(frm) {
		if (frm.is_new() && !frm.doc.company) {
			const company = frappe.defaults.get_user_default("Company");
			if (company) {
				frm.set_value("company", company);
			}
		}
		if (frm.is_new() && !frm.doc.processed_by) {
			frm.set_value("processed_by", frappe.session.user);
		}
	},
	refresh(frm) {
		if (frm.doc.job_order) {
			pufm_render_sheeting_instructions(frm);
		}
	},
	job_order(frm) {
		pufm_render_sheeting_instructions(frm);
	},
});

frappe.ui.form.on("Pufm Sheeting Output", {
	length_inches(frm, cdt, cdn) {
		recalc_sheeting_output_cbm(cdt, cdn);
	},
	width_inches(frm, cdt, cdn) {
		recalc_sheeting_output_cbm(cdt, cdn);
	},
	thickness_inches(frm, cdt, cdn) {
		recalc_sheeting_output_cbm(cdt, cdn);
	},
	quantity(frm, cdt, cdn) {
		recalc_sheeting_output_cbm(cdt, cdn);
	},
});

function recalc_sheeting_output_cbm(cdt, cdn) {
	const row = locals[cdt][cdn];
	frappe.db.get_single_value("Pufm Manufacturing Settings", "cbm_factor").then((factor) => {
		const cbmFactor = flt(factor) || 61023.74;
		const length = flt(row.length_inches);
		const width = flt(row.width_inches);
		const thickness = flt(row.thickness_inches);
		const qty = flt(row.quantity);
		if (length <= 0 || width <= 0 || thickness <= 0 || qty <= 0) {
			frappe.model.set_value(cdt, cdn, "calculated_cbm", 0);
			return;
		}
		const cbm = (length * width * thickness * qty) / cbmFactor;
		frappe.model.set_value(cdt, cdn, "calculated_cbm", flt(cbm, 5));
	});
}

function pufm_render_sheeting_instructions(frm) {
	if (!frm.fields_dict.conversion_instructions_html) {
		return;
	}
	if (!frm.doc.job_order) {
		frm.fields_dict.conversion_instructions_html.$wrapper.html(
			"<p class='text-muted'>Select a Job Order to load sheeting instructions.</p>"
		);
		return;
	}
	frappe.call({
		method:
			"pu_foam_master.pufm_manufacturing.doctype.pufm_job_order.pufm_job_order.get_job_order_instructions_html",
		args: { job_order: frm.doc.job_order },
		callback(r) {
			frm.fields_dict.conversion_instructions_html.$wrapper.html(
				r.message || "<p class='text-muted'>No instructions available.</p>"
			);
		},
	});
}
