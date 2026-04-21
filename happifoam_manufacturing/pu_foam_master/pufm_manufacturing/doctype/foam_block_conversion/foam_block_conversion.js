frappe.ui.form.on("Foam Block Conversion", {
	refresh(frm) {
		frm.set_query("material_request", () => ({
			filters: { material_request_type: "Manufacture" }
		}));
		recalculate_summary(frm);
	},
	onload(frm) {
		set_conversion_rate(frm);
	},
	inputs_add(frm) {
		recalculate_summary(frm);
	},
	inputs_remove(frm) {
		recalculate_summary(frm);
	},
	outputs_add(frm) {
		recalculate_summary(frm);
	},
	outputs_remove(frm) {
		recalculate_summary(frm);
	},
	validate(frm) {
		recalculate_summary(frm);
	}
});

frappe.ui.form.on("Block Conversion Input", {
	item_code(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.item_code) {
			return;
		}
		frappe.db.get_value("Item", row.item_code, "custom_cbm_value").then((r) => {
			const unitCbm = flt((r.message || {}).custom_cbm_value);
			frappe.model.set_value(cdt, cdn, "unit_cbm", unitCbm);
			recalculate_input_row(frm, cdt, cdn);
		});
	},
	qty(frm, cdt, cdn) {
		recalculate_input_row(frm, cdt, cdn);
	}
});

frappe.ui.form.on("Block Conversion Output", {
	item_code(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.item_code) {
			return;
		}
		frappe.call({
			method: "frappe.client.get",
			args: {
				doctype: "Item",
				name: row.item_code
			},
			callback: function(res) {
				const item = res.message || {};
				frappe.model.set_value(cdt, cdn, "uom", item.stock_uom || null);
				frappe.model.set_value(cdt, cdn, "width", flt(item.custom_width));
				frappe.model.set_value(cdt, cdn, "height", flt(item.custom_height));
				frappe.model.set_value(cdt, cdn, "length", flt(item.custom_length));
				recalculate_output_row(frm, cdt, cdn);
			}
		});
	},
	qty(frm, cdt, cdn) {
		recalculate_output_row(frm, cdt, cdn);
	},
	width(frm, cdt, cdn) {
		recalculate_output_row(frm, cdt, cdn);
	},
	height(frm, cdt, cdn) {
		recalculate_output_row(frm, cdt, cdn);
	},
	length(frm, cdt, cdn) {
		recalculate_output_row(frm, cdt, cdn);
	}
});

function set_conversion_rate(frm) {
	if (frm.doc.conversion_rate) {
		return;
	}
	frappe.db.get_single_value("Pufm Manufacturing Settings", "conversion_rate_per_cbm").then((rate) => {
		frm.set_value("conversion_rate", flt(rate));
		recalculate_summary(frm);
	});
}

function get_cbm_factor() {
	return frappe.db.get_single_value("Pufm Manufacturing Settings", "cbm_factor").then((factor) => {
		const parsed = flt(factor);
		return parsed > 0 ? parsed : 61023.7;
	});
}

function recalculate_input_row(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	const total = flt(row.qty) * flt(row.unit_cbm);
	frappe.model.set_value(cdt, cdn, "total_cbm", total);
	recalculate_summary(frm);
}

function recalculate_output_row(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	get_cbm_factor().then((cbmFactor) => {
		const width = flt(row.width);
		const height = flt(row.height);
		const length = flt(row.length);
		const unit = (width > 0 && height > 0 && length > 0) ? ((width * height * length) / cbmFactor) : 0;
		const total = flt(row.qty) * unit;
		frappe.model.set_value(cdt, cdn, "unit_cbm", unit);
		frappe.model.set_value(cdt, cdn, "total_cbm", total);
		recalculate_summary(frm);
	});
}

function recalculate_summary(frm) {
	const totalInput = (frm.doc.inputs || []).reduce((acc, row) => acc + flt(row.total_cbm), 0);
	const totalOutput = (frm.doc.outputs || []).reduce((acc, row) => acc + flt(row.total_cbm), 0);
	const variance = totalOutput - totalInput;
	const conversionCost = totalInput * flt(frm.doc.conversion_rate);

	frm.set_value("total_input_cbm", totalInput);
	frm.set_value("total_output_cbm", totalOutput);
	frm.set_value("cbm_variance", variance);
	frm.set_value("conversion_cost", conversionCost);
}

frappe.ui.form.on('Foam Block Conversion', {
    onload: function(frm) {
        if (frm.is_new()) {
            frm.set_value('processed_by', frappe.session.user);
        }
    }
});
