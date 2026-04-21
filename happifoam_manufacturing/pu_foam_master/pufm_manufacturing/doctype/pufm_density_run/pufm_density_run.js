frappe.ui.form.on("Pufm Density Run", {
	refresh(frm) {
		set_block_item_query(frm);
	},
	density_config(frm) {
		set_block_item_query(frm);
	}
});

function set_block_item_query(frm) {
	// Check if density_config has a value before filtering
	if (frm.doc.density_config) {
		frm.set_query("block_item", "produced_blocks_table", () => {
			return {
				filters: [
					["Item", "item_code", "like", frm.doc.density_config + "%"],
					["Item", "is_stock_item", "=", 1],
					["Item", "disabled", "=", 0]
				]
			};
		});
	}
}


// This section handles logic inside the Produced Blocks table rows
frappe.ui.form.on('Pufm Produced Block', {
	block_item: function (frm, cdt, cdn) {
		var row = locals[cdt][cdn];

		// When an item is selected, fetch its CBM value immediately
		if (row.block_item) {
			frappe.db.get_value('Item', row.block_item, 'custom_cbm_value', (r) => {
				if (r && r.custom_cbm_value) {
					// Update the 'unit_cbm' field in this specific row
					frappe.model.set_value(cdt, cdn, 'unit_cbm', r.custom_cbm_value);

					// Manually trigger the total calculation for this row
					let total = flt(row.quantity) * flt(r.custom_cbm_value);
					frappe.model.set_value(cdt, cdn, 'total_cbm', total);
				}
			});
		}
	},
	quantity: function (frm, cdt, cdn) {
		var row = locals[cdt][cdn];
		// Re-calculate total when quantity changes
		let total = flt(row.quantity) * flt(row.unit_cbm);
		frappe.model.set_value(cdt, cdn, 'total_cbm', total);
	}
});