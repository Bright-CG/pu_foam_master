// Copyright (c) 2026, Happifoam and contributors
// For license information, please see license.txt

frappe.ui.form.on("Rebound Production Entry", {
	setup(frm) {
		frm.set_query("scrap_warehouse", () => ({
			filters: { company: frm.doc.company, disabled: 0 },
		}));
		frm.set_query("mdi_warehouse", () => ({
			filters: { company: frm.doc.company, disabled: 0 },
		}));
		frm.set_query("target_warehouse", () => ({
			filters: { company: frm.doc.company, disabled: 0 },
		}));
	},
	onload(frm) {
		if (frm.is_new() && !frm.doc.company) {
			const user_company = frappe.defaults.get_user_default("Company");
			if (user_company) {
				frm.set_value("company", user_company);
			}
		}
	},
	rebound_configuration(frm) {
		recalculate(frm);
	},
	target_block_item(frm) {
		if (!frm.doc.target_block_item) {
			return;
		}
		frappe.call({
			method: "pu_foam_master.pufm_manufacturing.doctype.rebound_production_entry.rebound_production_entry.get_item_dimensions",
			args: { item_code: frm.doc.target_block_item },
			callback(r) {
				if (!r.message) {
					return;
				}
				frm.set_value("length_inches", r.message.custom_length || 0);
				frm.set_value("width_inches", r.message.custom_width || 0);
				frm.set_value("height_inches", r.message.custom_height || 0);
				recalculate(frm);
			},
		});
	},
	length_inches(frm) {
		recalculate(frm);
	},
	width_inches(frm) {
		recalculate(frm);
	},
	height_inches(frm) {
		recalculate(frm);
	},
	quantity_produced(frm) {
		recalculate(frm);
	},
});

function recalculate(frm) {
	if (!frm.doc.rebound_configuration) {
		return;
	}
	frappe.db.get_doc("Rebound Configuration", frm.doc.rebound_configuration).then((config) => {
		const length = flt(frm.doc.length_inches);
		const width = flt(frm.doc.width_inches);
		const height = flt(frm.doc.height_inches);
		const qty = flt(frm.doc.quantity_produced);
		const total_cbm = (length * width * height * qty) / 61023.74;

		frm.set_value("total_volume_cbm", total_cbm);
		frm.set_value("expected_scrap_kg", flt(config.scrap_kg_per_cbm) * total_cbm);
		frm.set_value("expected_mdi_kg", flt(config.mdi_kg_per_cbm) * total_cbm);

		if (!flt(frm.doc.actual_scrap_kg)) {
			frm.set_value("actual_scrap_kg", flt(config.scrap_kg_per_cbm) * total_cbm);
		}
		if (!flt(frm.doc.actual_mdi_kg)) {
			frm.set_value("actual_mdi_kg", flt(config.mdi_kg_per_cbm) * total_cbm);
		}
	});
}
