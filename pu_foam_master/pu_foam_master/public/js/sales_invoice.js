frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		ensure_pufm_vat_rate(frm);
		toggle_additional_discount_read_only(frm);
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
	customer(frm) {
		calculate_instant_rebate(frm);
	},
	custom_apply_instant_rebate(frm) {
		if (frm.doc.custom_apply_instant_rebate && frm.doc.custom_exclude_from_rebate) {
			frm.set_value("custom_exclude_from_rebate", 0);
		}
		if (frm.doc.custom_apply_instant_rebate && has_manual_additional_discount(frm)) {
			frappe.msgprint({
				title: __("Instant Rebate"),
				indicator: "orange",
				message: __("Additional Discount was cleared. Use either Instant Rebate or Additional Discount."),
			});
			clear_manual_additional_discount(frm, () => calculate_instant_rebate(frm));
			return;
		}
		if (!frm.doc.custom_apply_instant_rebate) {
			clear_instant_discount_fields(frm, () => calculate_instant_rebate(frm));
			return;
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
	apply_discount_on(frm) {
		block_discount_if_instant_rebate(frm);
	},
	additional_discount_percentage(frm) {
		block_discount_if_instant_rebate(frm);
	},
	discount_amount(frm) {
		block_discount_if_instant_rebate(frm);
	},
	additional_discount_account(frm) {
		block_discount_if_instant_rebate(frm);
	},
});

["net_total", "discount_amount"].forEach((fieldname) => {
	frappe.ui.form.on("Sales Invoice", fieldname, (frm) => {
		if (frm._pufm_syncing_instant_rebate) {
			return;
		}
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
	if (frm._pufm_vat_rate != null && frm._pufm_rebate_expense_account) {
		return;
	}
	const tasks = [];
	if (frm._pufm_vat_rate == null) {
		tasks.push(
			frappe.call({
				method: "pu_foam_master.pufm_manufacturing.utils.settings.get_default_vat_rate",
			})
		);
	}
	if (!frm._pufm_rebate_expense_account) {
		tasks.push(
			frappe.call({
				method: "pu_foam_master.rebate.sales_invoice.get_instant_rebate_discount_defaults",
			})
		);
	}
	if (!tasks.length) {
		return;
	}
	Promise.all(tasks).then((results) => {
		results.forEach((r) => {
			if (!r || r.message == null) {
				return;
			}
			const msg = r.message;
			if (typeof msg === "number") {
				frm._pufm_vat_rate = flt(msg) || 7.5;
			} else if (msg.additional_discount_account) {
				frm._pufm_rebate_expense_account = msg.additional_discount_account;
			}
		});
		if (frm._pufm_vat_rate == null) {
			frm._pufm_vat_rate = 7.5;
		}
		calculate_instant_rebate(frm);
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
	const gross = frm.doc.custom_apply_instant_rebate
		? flt(frm.doc.net_total)
		: flt(frm.doc.net_total) - flt(frm.doc.discount_amount);
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
	return gross - (gross * rate) / 100;
}

function has_manual_additional_discount(frm) {
	if (frm.doc.custom_apply_instant_rebate) {
		return false;
	}
	if (flt(frm.doc.additional_discount_percentage) > 0) {
		return true;
	}
	if (flt(frm.doc.discount_amount) <= 0) {
		return false;
	}
	const rebate_ac = frm._pufm_rebate_expense_account;
	if (rebate_ac && frm.doc.additional_discount_account === rebate_ac) {
		return false;
	}
	return true;
}

function clear_manual_additional_discount(frm, callback) {
	frm._pufm_syncing_instant_rebate = true;
	frm.set_value("additional_discount_percentage", 0);
	frm.set_value("discount_amount", 0);
	frm.set_value("additional_discount_account", null).then(() => {
		frm._pufm_syncing_instant_rebate = false;
		if (callback) {
			callback();
		}
	});
}

function clear_instant_discount_fields(frm, callback) {
	const rebate_ac = frm._pufm_rebate_expense_account;
	const clear_discount =
		rebate_ac && frm.doc.additional_discount_account === rebate_ac && flt(frm.doc.discount_amount) > 0;
	frm._pufm_syncing_instant_rebate = true;
	const chain = [frm.set_value("custom_instant_rebate_amount", 0)];
	if (clear_discount) {
		chain.push(frm.set_value("additional_discount_percentage", 0));
		chain.push(frm.set_value("discount_amount", 0));
		chain.push(frm.set_value("additional_discount_account", null));
	}
	Promise.all(chain).then(() => {
		frm._pufm_syncing_instant_rebate = false;
		toggle_additional_discount_read_only(frm);
		trigger_invoice_tax_recalc(frm);
		if (callback) {
			callback();
		}
	});
}

function block_discount_if_instant_rebate(frm) {
	if (!frm.doc.custom_apply_instant_rebate || frm._pufm_syncing_instant_rebate) {
		return;
	}
	frappe.msgprint({
		title: __("Instant Rebate active"),
		indicator: "blue",
		message: __(
			"Additional Discount is controlled by Instant Rebate. Turn off Instant Rebate to use a manual discount."
		),
	});
	calculate_instant_rebate(frm);
}

function toggle_additional_discount_read_only(frm) {
	const hide = !!frm.doc.custom_apply_instant_rebate;
	const fields = [
		"apply_discount_on",
		"additional_discount_percentage",
		"discount_amount",
		"additional_discount_account",
	];
	fields.forEach((fieldname) => {
		frm.set_df_property(fieldname, "read_only", hide ? 1 : 0);
	});
	if (hide && frm.doc.apply_discount_on !== "Grand Total") {
		frm.set_value("apply_discount_on", "Grand Total");
	}
}

function sync_instant_as_additional_discount(frm, amount) {
	frm._pufm_syncing_instant_rebate = true;
	const account = frm._pufm_rebate_expense_account;
	return frm
		.set_value("apply_discount_on", "Grand Total")
		.then(() => frm.set_value("additional_discount_percentage", 0))
		.then(() => frm.set_value("additional_discount_account", account))
		.then(() => frm.set_value("discount_amount", flt(amount)))
		.then(() => {
			frm._pufm_syncing_instant_rebate = false;
		});
}

function trigger_invoice_tax_recalc(frm) {
	if (frm.script_manager && frm.script_manager.trigger) {
		frm.script_manager.trigger("calculate_taxes_and_totals");
		return;
	}
	if (frm.cscript && frm.cscript.calculate_taxes_and_totals) {
		frm.cscript.calculate_taxes_and_totals();
	}
}

function calculate_instant_rebate(frm) {
	if (frm.doc.docstatus !== 0) {
		toggle_additional_discount_read_only(frm);
		return;
	}
	toggle_additional_discount_read_only(frm);

	if (!frm.doc.custom_apply_instant_rebate || frm.doc.custom_exclude_from_rebate) {
		clear_instant_discount_fields(frm);
		return;
	}
	if (frm._pufm_vat_rate == null || !frm._pufm_rebate_expense_account) {
		ensure_pufm_vat_rate(frm);
		return;
	}
	const base = get_sales_invoice_rebatable_base(frm);
	const amount = flt((base * flt(frm.doc.custom_instant_rebate_percentage)) / 100, 2);
	frm.set_value("custom_instant_rebate_amount", amount).then(() => {
		if (amount <= 0) {
			clear_instant_discount_fields(frm);
			return;
		}
		sync_instant_as_additional_discount(frm, amount).then(() => {
			trigger_invoice_tax_recalc(frm);
		});
	});
}