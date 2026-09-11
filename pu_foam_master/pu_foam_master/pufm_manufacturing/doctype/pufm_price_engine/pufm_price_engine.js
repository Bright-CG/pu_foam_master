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
	base_dollar_rate(frm) {
		recalculate_matrix(frm);
	},
	current_dollar_rate(frm) {
		recalculate_matrix(frm);
	},
	dollar_exposure_percent(frm) {
		recalculate_matrix(frm);
	},
});

frappe.ui.form.on("Pufm Price Engine Item", {
	selling_price(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		row.gross_profit_amount = flt(flt(row.selling_price) - flt(row.current_cost), 2);
		frm.refresh_field("items");
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
				child.dollar_adjusted_price = 0;
				child.selling_price = 0;
				child.gross_profit_amount = 0;
			});
			recalculate_matrix(frm, { silent: true, seed_selling_price: true });
			frm.refresh_field("items");
			frappe.show_alert({
				message: __("Loaded {0} items into the price matrix.", [(r.message || []).length]),
				indicator: "green",
			});
		},
	});
}

function dollar_adjustment_percents(frm) {
	const base = flt(frm.doc.base_dollar_rate);
	const current = flt(frm.doc.current_dollar_rate);
	const exposure = Math.max(flt(frm.doc.dollar_exposure_percent), 0);
	if (base <= 0 || current <= 0) {
		return { rate_adj: 0, effective: 0 };
	}
	const rate_adj = (current / base - 1) * 100;
	const effective = rate_adj * (exposure / 100);
	return { rate_adj, effective };
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

	const { rate_adj, effective } = dollar_adjustment_percents(frm);
	frm.doc.dollar_rate_adjustment_percent = flt(rate_adj, 4);
	frm.doc.effective_price_adjustment_percent = flt(effective, 4);
	frm.refresh_field("dollar_rate_adjustment_percent");
	frm.refresh_field("effective_price_adjustment_percent");

	const denominator = 1 - total / 100;
	const effective_factor = 1 + effective / 100;
	const force_seed = !!opts.seed_selling_price;

	(frm.doc.items || []).forEach((row) => {
		const cost = flt(row.current_cost);
		const previous_adjusted = flt(row.dollar_adjusted_price);
		const previous_selling = flt(row.selling_price);

		if (cost <= 0 || denominator <= 0) {
			row.proposed_selling_price = 0;
			row.dollar_adjusted_price = 0;
			if (force_seed || previous_selling <= 0) {
				row.selling_price = 0;
			}
			row.gross_profit_amount = flt(flt(row.selling_price) - cost, 2);
			return;
		}

		const proposed = flt(cost / denominator, 2);
		const adjusted = flt(proposed * effective_factor, 2);
		row.proposed_selling_price = proposed;
		row.dollar_adjusted_price = adjusted;

		// Seed blank Selling Price, or keep tracking adjusted when MD has not overridden
		if (force_seed || previous_selling <= 0) {
			row.selling_price = adjusted;
		} else if (Math.abs(previous_selling - previous_adjusted) < 0.005) {
			row.selling_price = adjusted;
		}

		row.gross_profit_amount = flt(flt(row.selling_price) - cost, 2);
	});
	frm.refresh_field("items");
}
