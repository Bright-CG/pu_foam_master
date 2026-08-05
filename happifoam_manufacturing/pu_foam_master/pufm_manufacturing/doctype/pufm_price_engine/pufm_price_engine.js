// Copyright (c) 2026, PU Foam Master and contributors
// For license information, please see license.txt

frappe.ui.form.on("Pufm Price Engine", {
	refresh(frm) {
		recalculate_price(frm);
	},
	item_code(frm) {
		fetch_current_cost(frm);
	},
	freight_percent(frm) {
		recalculate_price(frm);
	},
	advert_percent(frm) {
		recalculate_price(frm);
	},
	vat_percent(frm) {
		recalculate_price(frm);
	},
	rebate_percent(frm) {
		recalculate_price(frm);
	},
	profit_margin_percent(frm) {
		recalculate_price(frm);
	},
	current_cost(frm) {
		recalculate_price(frm);
	},
});

function fetch_current_cost(frm) {
	if (!frm.doc.item_code) {
		frm.set_value("current_cost", 0);
		return;
	}
	frappe.call({
		method:
			"pu_foam_master.pufm_manufacturing.doctype.pufm_price_engine.pufm_price_engine.get_item_current_cost",
		args: { item_code: frm.doc.item_code },
		callback(r) {
			frm.set_value("current_cost", flt(r.message) || 0);
			recalculate_price(frm);
		},
	});
}

function recalculate_price(frm) {
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
		frappe.msgprint({
			title: __("Invalid Margin"),
			indicator: "red",
			message: __("Margin cannot be 100% or greater"),
		});
		frm.set_value("freight_percent", 0);
		frm.set_value("advert_percent", 0);
		frm.set_value("vat_percent", 0);
		frm.set_value("rebate_percent", 0);
		frm.set_value("profit_margin_percent", 0);
		frm.set_value("total_deduction_percent", 0);
		frm.set_value("proposed_selling_price", 0);
		frm.set_value("gross_profit_amount", 0);
		return;
	}

	frm.set_value("total_deduction_percent", flt(total, 2));

	const cost = flt(frm.doc.current_cost);
	if (cost <= 0) {
		frm.set_value("proposed_selling_price", 0);
		frm.set_value("gross_profit_amount", 0);
		return;
	}

	// MD formula: Cost / (1 - Margin%)
	const proposed = cost / (1 - total / 100);
	frm.set_value("proposed_selling_price", flt(proposed, 2));
	frm.set_value("gross_profit_amount", flt(proposed - cost, 2));
}
