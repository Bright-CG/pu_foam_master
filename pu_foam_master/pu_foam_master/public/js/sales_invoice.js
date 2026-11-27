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
		ensure_manual_additional_discount_account(frm);
	},
	discount_amount(frm) {
		block_discount_if_instant_rebate(frm);
		ensure_manual_additional_discount_account(frm);
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
		if (fieldname === "discount_amount" && frm.doc.custom_apply_instant_rebate) {
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
	const ready =
		frm._pufm_vat_rate != null &&
		frm._pufm_rebate_expense_account !== undefined &&
		frm._pufm_sales_discount_account !== undefined;
	if (ready) {
		toggle_additional_discount_read_only(frm);
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
	if (frm._pufm_rebate_expense_account === undefined || frm._pufm_sales_discount_account === undefined) {
		tasks.push(
			frappe.call({
				method: "pu_foam_master.rebate.sales_invoice.get_pufm_sales_invoice_discount_accounts",
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
			} else if (typeof msg === "object") {
				if (frm._pufm_rebate_expense_account === undefined) {
					frm._pufm_rebate_expense_account = msg.rebate_expense_account || null;
				}
				if (frm._pufm_sales_discount_account === undefined) {
					frm._pufm_sales_discount_account = msg.sales_additional_discount_account || null;
				}
			}
		});
		if (frm._pufm_vat_rate == null) {
			frm._pufm_vat_rate = 7.5;
		}
		toggle_additional_discount_read_only(frm);
		ensure_manual_additional_discount_account(frm);
		calculate_instant_rebate(frm);
	});
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
	const instant = !!frm.doc.custom_apply_instant_rebate;
	const lock_discount_account =
		!instant && !!frm._pufm_sales_discount_account;
	frm.set_df_property("apply_discount_on", "read_only", instant ? 1 : 0);
	frm.set_df_property("additional_discount_percentage", "read_only", instant ? 1 : 0);
	frm.set_df_property("discount_amount", "read_only", instant ? 1 : 0);
	frm.set_df_property("additional_discount_account", "read_only", instant || lock_discount_account ? 1 : 0);
	if (instant && frm.doc.apply_discount_on !== "Grand Total") {
		frm.set_value("apply_discount_on", "Grand Total");
	}
}

function ensure_manual_additional_discount_account(frm) {
	if (frm.doc.docstatus !== 0 || frm.doc.custom_apply_instant_rebate) {
		return;
	}
	if (frm._pufm_sales_discount_account === undefined) {
		ensure_pufm_vat_rate(frm);
		return;
	}
	if (!frm._pufm_sales_discount_account) {
		return;
	}
	const hasDiscount =
		flt(frm.doc.additional_discount_percentage) > 0 || flt(frm.doc.discount_amount) > 0;
	if (!hasDiscount) {
		return;
	}
	const jobs = [];
	if (!frm.doc.apply_discount_on) {
		jobs.push(frm.set_value("apply_discount_on", "Grand Total"));
	}
	if (frm.doc.additional_discount_account !== frm._pufm_sales_discount_account) {
		jobs.push(frm.set_value("additional_discount_account", frm._pufm_sales_discount_account));
	}
	if (jobs.length) {
		Promise.all(jobs).then(() => trigger_invoice_tax_recalc(frm));
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
	if (flt(frm.doc.custom_instant_rebate_percentage) <= 0) {
		frm.set_value("custom_instant_rebate_amount", 0);
		clear_instant_discount_fields(frm);
		return;
	}
	frm._pufm_rebate_calc_seq = (frm._pufm_rebate_calc_seq || 0) + 1;
	const seq = frm._pufm_rebate_calc_seq;
	const rebate_pct = flt(frm.doc.custom_instant_rebate_percentage);
	frappe.call({
		method: "pu_foam_master.rebate.sales_invoice.compute_instant_rebate_amount",
		args: {
			net_total: flt(frm.doc.net_total),
			total: flt(frm.doc.total),
			discount_amount: flt(frm.doc.discount_amount),
			custom_apply_instant_rebate: frm.doc.custom_apply_instant_rebate ? 1 : 0,
			custom_exclude_from_rebate: frm.doc.custom_exclude_from_rebate ? 1 : 0,
			custom_instant_rebate_percentage: rebate_pct,
			taxes: frm.doc.taxes,
		},
		callback(r) {
			if (seq !== frm._pufm_rebate_calc_seq || frm._pufm_syncing_instant_rebate) {
				return;
			}
			const amount = flt(r.message && r.message.amount);
			frm.set_value("custom_instant_rebate_amount", amount).then(() => {
				if (amount <= 0) {
					clear_instant_discount_fields(frm);
					return;
				}
				sync_instant_as_additional_discount(frm, amount).then(() => {
					trigger_invoice_tax_recalc(frm);
				});
			});
		},
	});
}