// Copyright (c) 2026, PU Foam Master and contributors
// For license information, please see license.txt

frappe.ui.form.on("Quilting Record", {
	setup(frm) {
		frm.set_query("target_warehouse", () => ({
			filters: {
				company: frm.doc.company,
				disabled: 0,
			},
		}));
		frm.set_query("source_warehouse", "inputs", () => ({
			filters: {
				company: frm.doc.company,
				disabled: 0,
			},
		}));
		frm.set_query("batch_no", "inputs", (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			if (!row.item_code || !row.source_warehouse) {
				frappe.msgprint(
					__("Please select an Item and Source Warehouse first to see available batches.")
				);
				return { filters: { name: ["in", [""]] } };
			}
			return {
				query: "erpnext.controllers.queries.get_batch_no",
				filters: {
					item_code: row.item_code,
					warehouse: row.source_warehouse,
				},
			};
		});
	},
	onload(frm) {
		if (frm.is_new() && !frm.doc.company) {
			const user_company = frappe.defaults.get_user_default("Company");
			if (user_company) {
				frm.set_value("company", user_company);
			}
		}
	},
	refresh(frm) {
		calculate_variance(frm, true);
	},
	output_qty_meters(frm) {
		calculate_variance(frm);
	},
	company(frm) {
		if (frm.doc.target_warehouse) {
			frappe.db.get_value("Warehouse", frm.doc.target_warehouse, "company").then((r) => {
				const wh_company = r && r.message && r.message.company;
				if (wh_company && wh_company !== frm.doc.company) {
					frm.set_value("target_warehouse", null);
				}
			});
		}
		(frm.doc.inputs || []).forEach((row) => {
			if (!row.source_warehouse) {
				return;
			}
			frappe.db.get_value("Warehouse", row.source_warehouse, "company").then((r) => {
				const wh_company = r && r.message && r.message.company;
				if (wh_company && wh_company !== frm.doc.company) {
					frappe.model.set_value(row.doctype, row.name, "source_warehouse", null);
					frappe.model.set_value(row.doctype, row.name, "batch_no", null);
				}
			});
		});
	},
});

frappe.ui.form.on("Quilting Input", {
	item_code(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "batch_no", "");
		calculate_variance(frm);
	},
	source_warehouse(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "batch_no", "");
	},
	qty(frm) {
		calculate_variance(frm);
	},
});

function calculate_variance(frm, silent) {
	let total_input = 0;
	(frm.doc.inputs || []).forEach((row) => {
		if (flt(row.qty) > total_input) {
			total_input = flt(row.qty);
		}
	});

	const variance = frm.doc.output_qty_meters
		? total_input - flt(frm.doc.output_qty_meters)
		: 0;

	if (silent) {
		if (flt(frm.doc.total_input_meters) !== total_input) {
			frm.doc.total_input_meters = total_input;
			frm.refresh_field("total_input_meters");
		}
		if (flt(frm.doc.variance_meters) !== variance) {
			frm.doc.variance_meters = variance;
			frm.refresh_field("variance_meters");
		}
		return;
	}

	frm.set_value("total_input_meters", total_input);
	if (frm.doc.output_qty_meters) {
		frm.set_value("variance_meters", variance);
	}
}
