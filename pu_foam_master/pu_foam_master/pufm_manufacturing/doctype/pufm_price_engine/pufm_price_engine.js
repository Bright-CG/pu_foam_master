// Copyright (c) 2026, PU Foam Master and contributors
// For license information, please see license.txt

frappe.ui.form.on("Pufm Price Engine", {
	refresh(frm) {
		recalculate_matrix(frm, { silent: true });
	},
	fetch_items_button(frm) {
		fetch_item_matrix(frm);
	},
	freight_percent(frm) {
		recalculate_matrix(frm, { field: "freight_percent" });
	},
	advert_percent(frm) {
		recalculate_matrix(frm, { field: "advert_percent" });
	},
	vat_percent(frm) {
		recalculate_matrix(frm, { field: "vat_percent" });
	},
	rebate_percent(frm) {
		recalculate_matrix(frm, { field: "rebate_percent" });
	},
	profit_margin_percent(frm) {
		recalculate_matrix(frm, { field: "profit_margin_percent" });
	},
});

function fetch_item_matrix(frm) {
	if (frm.doc.docstatus === 1) {
		return;
	}
	if (!frm.doc.item_group) {
		frappe.msgprint({
			title: __("Missing Item Group"),
			indicator: "orange",
			message: __("Select an Item Group before fetching items."),
		});
		return;
	}

	frappe.call({
		method:
			"pu_foam_master.pufm_manufacturing.doctype.pufm_price_engine.pufm_price_engine.fetch_item_matrix",
		args: { item_group: frm.doc.item_group },
		freeze: true,
		freeze_message: __("Exploding BOMs and building price matrix..."),
		callback(r) {
			frm.clear_table("items");
			(r.message || []).forEach((row) => {
				const child = frm.add_child("items");
				child.item_code = row.item_code;
				child.item_name = row.item_name;
				child.bom_reference = row.bom_reference;
				child.material_breakdown = row.material_breakdown;
				child.current_cost = flt(row.current_cost);
				child.proposed_selling_price = 0;
				child.gross_profit_amount = 0;
			});
			recalculate_matrix(frm, { silent: true });
			frm.refresh_field("items");
			frappe.show_alert({
				message: __("Loaded {0} items into the price matrix.", [(r.message || []).length]),
				indicator: "green",
			});
		},
	});
}

function recalculate_matrix(frm, opts) {
	opts = opts || {};
	if (frm.doc.docstatus === 1) {
		return;
	}

	const total =
		flt(frm.doc.freight_percent) +
		flt(frm.doc.advert_percent) +
		flt(frm.doc.vat_percent) +
		flt(frm.doc.rebate_percent) +
		flt(frm.doc.profit_margin_percent);

	if (total >= 100) {
		if (!opts.silent) {
			frappe.msgprint({
				title: __("Invalid Margin"),
				indicator: "red",
				message: __("Margin cannot be 100% or greater"),
			});
		}
		if (opts.field) {
			frm.set_value(opts.field, 0);
		}
		frm.doc.total_deduction_percent = 0;
		frm.refresh_field("total_deduction_percent");
		return;
	}

	frm.doc.total_deduction_percent = flt(total, 2);
	frm.refresh_field("total_deduction_percent");

	const denominator = 1 - total / 100;
	(frm.doc.items || []).forEach((row) => {
		const cost = flt(row.current_cost);
		if (cost <= 0 || denominator <= 0) {
			row.proposed_selling_price = 0;
			row.gross_profit_amount = 0;
			return;
		}
		row.proposed_selling_price = flt(cost / denominator, 2);
		row.gross_profit_amount = flt(row.proposed_selling_price - cost, 2);
	});
	frm.refresh_field("items");
}
