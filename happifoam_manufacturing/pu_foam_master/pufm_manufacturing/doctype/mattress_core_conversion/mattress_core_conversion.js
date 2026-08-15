frappe.ui.form.on("Mattress Core Conversion", {
	setup(frm) {
		frm.set_query("source_warehouse", "inputs", () => {
			return {
				filters: {
					company: frm.doc.company,
					disabled: 0,
				},
			};
		});
		frm.set_query("batch_no", "inputs", (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			return {
				filters: {
					item: row.item_code || "",
					disabled: 0,
				},
			};
		});
		frm.set_query("target_warehouse", () => {
			return {
				filters: {
					company: frm.doc.company,
					disabled: 0,
				},
			};
		});
		frm.set_query("material_request", () => ({
			filters: { material_request_type: "Manufacture" },
		}));
	},
	refresh(frm) {
		// Sync read-only totals without dirtying (keeps Submit visible)
		sync_summary_fields(frm, { silent: true });
		if (frm.doc.job_order) {
			pufm_fetch_job_instructions(frm);
		}
	},
	job_order(frm) {
		pufm_fetch_job_instructions(frm);
	},
	fetch_job_instructions(frm) {
		pufm_fetch_job_instructions(frm);
	},
	onload(frm) {
		if (frm.is_new() && !frm.doc.company) {
			const user_company = frappe.defaults.get_user_default("Company");
			if (user_company) {
				frm.set_value("company", user_company);
			}
		}
		if (frm.is_new() && !frm.doc.processed_by) {
			frm.set_value("processed_by", frappe.session.user);
		}
		set_conversion_rate(frm);
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
				}
			});
		});
	},
	inputs_add(frm) {
		sync_summary_fields(frm);
	},
	inputs_remove(frm) {
		sync_summary_fields(frm);
	},
	outputs_add(frm) {
		sync_summary_fields(frm);
	},
	outputs_remove(frm) {
		sync_summary_fields(frm);
	},
	validate(frm) {
		sync_summary_fields(frm, { silent: true });
	},
});

frappe.ui.form.on("Block Conversion Input", {
	item_code(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.item_code) {
			return;
		}
		frappe.db.get_value("Item", row.item_code, "custom_cbm_value").then((r) => {
			const unitCbm = flt((r.message || {}).custom_cbm_value);
			frappe.model.set_value(cdt, cdn, "unit_cbm", unitCbm).then(() => {
				recalculate_input_row(frm, cdt, cdn);
			});
		});
	},
	qty(frm, cdt, cdn) {
		recalculate_input_row(frm, cdt, cdn);
	},
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
				name: row.item_code,
			},
			callback: function (res) {
				const item = res.message || {};
				frappe.model.set_value(cdt, cdn, "uom", item.stock_uom || null);
				frappe.model.set_value(cdt, cdn, "width", flt(item.custom_width));
				frappe.model.set_value(cdt, cdn, "height", flt(item.custom_height));
				frappe.model.set_value(cdt, cdn, "length", flt(item.custom_length)).then(() => {
					recalculate_output_row(frm, cdt, cdn);
				});
			},
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
	},
});

function set_conversion_rate(frm) {
	if (flt(frm.doc.conversion_rate)) {
		return;
	}
	frappe.db.get_single_value("Pufm Manufacturing Settings", "conversion_rate_per_cbm").then((rate) => {
		const value = flt(rate);
		if (!nearly_equal(frm.doc.conversion_rate, value)) {
			if (frm.is_new()) {
				frm.set_value("conversion_rate", value);
			} else {
				frm.doc.conversion_rate = value;
				frm.refresh_field("conversion_rate");
			}
		}
		sync_summary_fields(frm, { silent: !frm.is_new() });
	});
}

function get_cbm_factor() {
	return frappe.db.get_single_value("Pufm Manufacturing Settings", "cbm_factor").then((factor) => {
		const parsed = flt(factor);
		return parsed > 0 ? parsed : 61023.74;
	});
}

function recalculate_input_row(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	const total = flt(row.qty) * flt(row.unit_cbm);
	frappe.model.set_value(cdt, cdn, "total_cbm", total).then(() => {
		sync_summary_fields(frm);
	});
}

function recalculate_output_row(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	get_cbm_factor().then((cbmFactor) => {
		const width = flt(row.width);
		const height = flt(row.height);
		const length = flt(row.length);
		const unit = width > 0 && height > 0 && length > 0 ? (width * height * length) / cbmFactor : 0;
		const total = flt(row.qty) * unit;
		frappe.model.set_value(cdt, cdn, "unit_cbm", unit);
		frappe.model.set_value(cdt, cdn, "total_cbm", total).then(() => {
			sync_summary_fields(frm);
		});
	});
}

function compute_summary(frm) {
	const totalInput = (frm.doc.inputs || []).reduce((acc, row) => acc + flt(row.total_cbm), 0);
	const totalOutput = (frm.doc.outputs || []).reduce((acc, row) => acc + flt(row.total_cbm), 0);
	return {
		total_input_cbm: totalInput,
		total_output_cbm: totalOutput,
		cbm_variance: totalOutput - totalInput,
		conversion_cost: flt(totalInput * flt(frm.doc.conversion_rate), 2),
	};
}

function sync_summary_fields(frm, opts) {
	const silent = opts && opts.silent;
	const values = compute_summary(frm);

	Object.keys(values).forEach((fieldname) => {
		const next = values[fieldname];
		if (nearly_equal(frm.doc[fieldname], next)) {
			return;
		}
		if (silent) {
			frm.doc[fieldname] = next;
			frm.refresh_field(fieldname);
		} else {
			frm.set_value(fieldname, next);
		}
	});
}

function nearly_equal(a, b, eps) {
	return Math.abs(flt(a) - flt(b)) < (eps || 0.0000001);
}

function pufm_fetch_job_instructions(frm) {
	if (!frm.doc.job_order) {
		if (frm.fields_dict.job_instructions_html) {
			frm.fields_dict.job_instructions_html.$wrapper.html(
				"<p class='text-muted'>Select a Job Order to load traveler instructions.</p>"
			);
		}
		return;
	}
	frappe.call({
		method:
			"pu_foam_master.pufm_manufacturing.doctype.pufm_job_order.pufm_job_order.get_job_order_instructions_html",
		args: { job_order: frm.doc.job_order },
		callback(r) {
			if (frm.fields_dict.job_instructions_html) {
				frm.fields_dict.job_instructions_html.$wrapper.html(r.message || "");
			}
		},
	});
}
