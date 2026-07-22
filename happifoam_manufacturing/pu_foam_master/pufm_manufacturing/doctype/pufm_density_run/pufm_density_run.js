frappe.ui.form.on("Pufm Density Run", {
	refresh(frm) {
		set_block_item_query(frm);
		calculate_expected_cbm(frm);
	},
	density_config(frm) {
		set_block_item_query(frm);
		// fetch_from may land async; recalculate after a tick as well
		calculate_expected_cbm(frm);
		frappe.after_ajax(() => calculate_expected_cbm(frm));
	},
	minutes_run(frm) {
		calculate_expected_cbm(frm);
	},
	output_rate_m3_per_min(frm) {
		calculate_expected_cbm(frm);
	},
});

function calculate_expected_cbm(frm) {
	const expected = flt(frm.doc.minutes_run) * flt(frm.doc.output_rate_m3_per_min);
	frm.set_value("expected_cbm", flt(expected, 5));
	frm.refresh_field("expected_cbm");
}

function set_block_item_query(frm) {
	if (frm.doc.density_config) {
		frm.set_query("block_item", "produced_blocks_table", () => {
			return {
				filters: [
					["Item", "item_code", "like", frm.doc.density_config + "%"],
					["Item", "is_stock_item", "=", 1],
					["Item", "disabled", "=", 0],
				],
			};
		});
	}
}

frappe.ui.form.on("Pufm Produced Block", {
	block_item: function (frm, cdt, cdn) {
		var row = locals[cdt][cdn];

		if (row.block_item) {
			frappe.db.get_value("Item", row.block_item, "custom_cbm_value", (r) => {
				if (r && r.custom_cbm_value) {
					frappe.model.set_value(cdt, cdn, "unit_cbm", r.custom_cbm_value);
					let total = flt(row.quantity) * flt(r.custom_cbm_value);
					frappe.model.set_value(cdt, cdn, "total_cbm", total);
				}
			});
		}
	},
	quantity: function (frm, cdt, cdn) {
		var row = locals[cdt][cdn];
		let total = flt(row.quantity) * flt(row.unit_cbm);
		frappe.model.set_value(cdt, cdn, "total_cbm", total);
	},
});
