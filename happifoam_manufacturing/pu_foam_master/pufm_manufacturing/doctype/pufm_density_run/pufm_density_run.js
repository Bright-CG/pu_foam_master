frappe.ui.form.on("PUFM Density Run", {
	refresh(frm) {
		set_block_item_query(frm);
	},
	density_config(frm) {
		set_block_item_query(frm);
	}
});

function set_block_item_query(frm) {
	frm.set_query("block_item", "produced_blocks_table", () => {
		return {
			query: "pu_foam_master.pufm_manufacturing.doctype.pufm_density_run.pufm_density_run.get_filtered_block_items",
			filters: {
				density_config: frm.doc.density_config
			}
		};
	});
}
