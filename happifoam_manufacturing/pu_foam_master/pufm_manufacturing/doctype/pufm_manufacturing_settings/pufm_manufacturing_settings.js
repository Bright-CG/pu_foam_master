// Copyright (c) 2026, PU Foam Master and contributors
// For license information, please see license.txt

frappe.ui.form.on("Pufm Manufacturing Settings", {
	refresh(frm) {
		calculate_overheads(frm, true);
		if (frappe.user_roles.includes("System Manager") || frappe.user_roles.includes("PUFM Manager")) {
			frm.add_custom_button(__("Reset Formulas to Default"), () => {
				frappe.confirm(
					__(
						"Restore consumption formula factors to factory defaults? " +
							"Item links, warehouses, accounts, and consumable rates are not changed."
					),
					() => {
						frappe.call({
							method:
								"pu_foam_master.pufm_manufacturing.doctype.pufm_manufacturing_settings.pufm_manufacturing_settings.reset_formula_defaults",
							freeze: true,
							freeze_message: __("Resetting formula defaults..."),
							callback(r) {
								if (r.message) {
									frm.reload_doc();
									frappe.show_alert({
										message: __("Formula factors restored to factory defaults."),
										indicator: "green",
									});
								}
							},
						});
					}
				);
			});
		}
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
