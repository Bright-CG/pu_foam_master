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
		// Prefill from Quilting JO sets item_code/qty without firing child events —
		// hydrate CBM so Unit/Total CBM still populate.
		if (frm.doc.docstatus === 0) {
			hydrate_all_row_cbm(frm).then(() => {
				sync_summary_fields(frm, { silent: true });
			});
		} else {
			sync_summary_fields(frm, { silent: true });
		}
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
		hydrate_all_row_cbm(frm);
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
		hydrate_input_row_cbm(frm, cdt, cdn);
	},
	qty(frm, cdt, cdn) {
		recalculate_input_row(frm, cdt, cdn);
	},
});

frappe.ui.form.on("Block Conversion Output", {
	item_code(frm, cdt, cdn) {
		hydrate_output_row_cbm(frm, cdt, cdn);
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

function hydrate_all_row_cbm(frm) {
	const tasks = [];
	(frm.doc.inputs || []).forEach((row) => {
		if (row.item_code) {
			tasks.push(hydrate_input_row_cbm(frm, row.doctype, row.name, { silent: true }));
		}
	});
	(frm.doc.outputs || []).forEach((row) => {
		if (row.item_code) {
			tasks.push(hydrate_output_row_cbm(frm, row.doctype, row.name, { silent: true }));
		}
	});
	return Promise.all(tasks).then(() => {
		sync_summary_fields(frm, { silent: true });
	});
}

function hydrate_input_row_cbm(frm, cdt, cdn, opts) {
	const silent = opts && opts.silent;
	const row = locals[cdt][cdn];
	if (!row || !row.item_code) {
		return Promise.resolve();
	}
	return frappe.db.get_value("Item", row.item_code, "custom_cbm_value").then((r) => {
		const unitCbm = flt((r && r.message && r.message.custom_cbm_value) || 0);
		const apply = silent
			? Promise.resolve().then(() => {
					row.unit_cbm = unitCbm;
					row.total_cbm = flt(row.qty) * unitCbm;
					frm.refresh_field("inputs");
			  })
			: frappe.model.set_value(cdt, cdn, "unit_cbm", unitCbm).then(() => {
					return recalculate_input_row(frm, cdt, cdn);
			  });
		return apply;
	});
}

function hydrate_output_row_cbm(frm, cdt, cdn, opts) {
	const silent = opts && opts.silent;
	const row = locals[cdt][cdn];
	if (!row || !row.item_code) {
		return Promise.resolve();
	}
	return frappe.db
		.get_value("Item", row.item_code, [
			"stock_uom",
			"custom_width",
			"custom_height",
			"custom_length",
			"custom_cbm_value",
		])
		.then((r) => {
			const item = (r && r.message) || {};
			const width = flt(item.custom_width);
			const height = flt(item.custom_height);
			const length = flt(item.custom_length);
			if (silent) {
				row.uom = item.stock_uom || row.uom;
				row.width = width;
				row.height = height;
				row.length = length;
				return get_cbm_factor().then((cbmFactor) => {
					let unit =
						width > 0 && height > 0 && length > 0
							? (width * height * length) / cbmFactor
							: flt(item.custom_cbm_value);
					row.unit_cbm = unit;
					row.total_cbm = flt(row.qty) * unit;
					frm.refresh_field("outputs");
				});
			}
			return frappe.model
				.set_value(cdt, cdn, {
					uom: item.stock_uom || null,
					width: width,
					height: height,
					length: length,
				})
				.then(() => recalculate_output_row(frm, cdt, cdn));
		});
}

function recalculate_input_row(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	const total = flt(row.qty) * flt(row.unit_cbm);
	return frappe.model.set_value(cdt, cdn, "total_cbm", total).then(() => {
		sync_summary_fields(frm);
	});
}

function recalculate_output_row(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	return get_cbm_factor().then((cbmFactor) => {
		const width = flt(row.width);
		const height = flt(row.height);
		const length = flt(row.length);
		let unit =
			width > 0 && height > 0 && length > 0 ? (width * height * length) / cbmFactor : 0;
		// Fall back to Item CBM when dimensions are missing (e.g. sheeting roll SKUs).
		const finish = () => {
			const total = flt(row.qty) * unit;
			return frappe.model.set_value(cdt, cdn, "unit_cbm", unit).then(() => {
				return frappe.model.set_value(cdt, cdn, "total_cbm", total).then(() => {
					sync_summary_fields(frm);
				});
			});
		};
		if (unit > 0 || !row.item_code) {
			return finish();
		}
		return frappe.db.get_value("Item", row.item_code, "custom_cbm_value").then((r) => {
			unit = flt((r && r.message && r.message.custom_cbm_value) || 0);
			return finish();
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
