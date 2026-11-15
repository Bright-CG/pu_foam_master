frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		ensure_pufm_vat_rate(frm);
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(
				__("Bulk add items"),
				() => pu_foam_master.bulk_invoice_lines.open_dialog(frm),
				__("PUFM")
			);
			return;
		}
		frm.add_custom_button(__("Create Job Order"), () => {
			frappe.new_doc("Pufm Job Order", {
				customer: frm.doc.customer,
				source_doctype: "Sales Invoice",
				source_document: frm.doc.name,
			});
		}, __("Create"));
	},
	onload(frm) {
		ensure_pufm_vat_rate(frm);
	},
	custom_apply_instant_rebate(frm) {
		if (frm.doc.custom_apply_instant_rebate && frm.doc.custom_exclude_from_rebate) {
			frm.set_value("custom_exclude_from_rebate", 0);
		}
		calculate_instant_rebate(frm);
	},
	custom_exclude_from_rebate(frm) {
		if (frm.doc.custom_exclude_from_rebate && frm.doc.custom_apply_instant_rebate) {
			frm.set_value("custom_apply_instant_rebate", 0);
		}
		calculate_instant_rebate(frm);
	},
	custom_instant_rebate_percentage(frm) {
		calculate_instant_rebate(frm);
	},
});

["net_total", "discount_amount"].forEach((fieldname) => {
	frappe.ui.form.on("Sales Invoice", fieldname, (frm) => {
		calculate_instant_rebate(frm);
	});
});

frappe.ui.form.on("Sales Taxes and Charges", {
	tax_amount(frm) {
		calculate_instant_rebate(frm);
	},
	add_deduct_tax(frm) {
		calculate_instant_rebate(frm);
	},
	taxes_remove(frm) {
		calculate_instant_rebate(frm);
	},
});

const INSTANT_REBATE_ROW_DESCRIPTION = "Instant Rebate";

function ensure_pufm_vat_rate(frm) {
	if (frm._pufm_vat_rate != null) {
		return;
	}
	frappe.call({
		method: "pu_foam_master.pufm_manufacturing.utils.settings.get_default_vat_rate",
		callback(r) {
			frm._pufm_vat_rate = flt(r.message) || 7.5;
			calculate_instant_rebate(frm);
		},
	});
}

function sales_invoice_has_erpnext_vat_taxes(frm) {
	return (frm.doc.taxes || []).some(
		(row) =>
			row.description !== INSTANT_REBATE_ROW_DESCRIPTION &&
			row.add_deduct_tax !== "Deduct" &&
			flt(row.tax_amount) > 0
	);
}

function get_sales_invoice_rebatable_base(frm) {
	const gross = flt(frm.doc.net_total) - flt(frm.doc.discount_amount);
	if (gross <= 0) {
		return 0;
	}
	if (sales_invoice_has_erpnext_vat_taxes(frm)) {
		return gross;
	}
	const rate = frm._pufm_vat_rate != null ? frm._pufm_vat_rate : 7.5;
	if (rate <= 0) {
		return gross;
	}
	return (gross * 100) / (100 + rate);
}

function calculate_instant_rebate(frm) {
	if (!frm.doc.custom_apply_instant_rebate || frm.doc.custom_exclude_from_rebate) {
		frm.set_value("custom_instant_rebate_amount", 0);
		return;
	}
	if (frm._pufm_vat_rate == null) {
		ensure_pufm_vat_rate(frm);
		return;
	}
	const base = get_sales_invoice_rebatable_base(frm);
	const amount = (base * flt(frm.doc.custom_instant_rebate_percentage)) / 100;
	frm.set_value("custom_instant_rebate_amount", amount);
}
