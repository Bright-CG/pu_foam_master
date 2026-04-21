frappe.ui.form.on("Mattress Item Generator", {
	refresh(frm) {
		frm.add_custom_button(__("Generate Items"), () => trigger_item_generation(frm));
	},
	fetch_sizes(frm) {
		fetch_standard_sizes(frm);
	},
	generate_items(frm) {
		trigger_item_generation(frm);
	}
});

frappe.ui.form.on("Generator Size", {
	width(frm, cdt, cdn) {
		calculate_unit_cbm(frm, cdt, cdn);
	},
	length(frm, cdt, cdn) {
		calculate_unit_cbm(frm, cdt, cdn);
	},
	height(frm, cdt, cdn) {
		calculate_unit_cbm(frm, cdt, cdn);
	}
});

function fetch_standard_sizes(frm) {
	frappe.call({
		method: "frappe.client.get_list",
		args: {
			doctype: "Standard Mattress Size",
			fields: ["name", "width_inches", "length_inches", "height_inches"],
			limit_page_length: 500,
			order_by: "creation asc"
		},
		callback: (r) => {
			const rows = r.message || [];
			frm.clear_table("sizes");
			rows.forEach((size) => {
				const child = frm.add_child("sizes");
				child.size_template = size.name;
				child.width = flt(size.width_inches);
				child.length = flt(size.length_inches);
				child.height = flt(size.height_inches);
				child.unit_cbm = compute_cbm(child.width, child.length, child.height);
			});
			frm.refresh_field("sizes");
		}
	});
}

function trigger_item_generation(frm) {
	if (frm.is_new()) {
		frappe.msgprint(__("Please save the document before generating items."));
		return;
	}

	frappe.call({
		method: "pu_foam_master.pufm_manufacturing.doctype.mattress_item_generator.mattress_item_generator.generate_mattress_items",
		args: { docname: frm.doc.name },
		callback: (r) => {
			const data = r.message || {};
			frm.reload_doc();
			const links = (data.items || []).slice(0, 20).map((item) => `<a href="/app/item/${encodeURIComponent(item)}">${item}</a>`);
			frappe.msgprint({
				title: __("Success"),
				indicator: "green",
				message: __("Successfully created/verified {0} items.<br>{1}", [data.count || 0, links.join("<br>")])
			});
		}
	});
}

function calculate_unit_cbm(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	frappe.model.set_value(cdt, cdn, "unit_cbm", compute_cbm(row.width, row.length, row.height));
	frm.refresh_field("sizes");
}

function compute_cbm(width, length, height) {
	return (flt(width) * flt(length) * flt(height)) / 61023.74;
}
