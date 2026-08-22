// Copyright (c) 2026, PU Foam Master and contributors
// For license information, please see license.txt

frappe.ui.form.on("Quilting Record", {
	setup(frm) {
		frm.set_query("target_warehouse", () => ({
			filters: { company: frm.doc.company, disabled: 0 },
		}));
		frm.set_query("fabric_warehouse", () => ({
			filters: { company: frm.doc.company, disabled: 0 },
		}));
		frm.set_query("sheeting_warehouse", () => ({
			filters: { company: frm.doc.company, disabled: 0 },
		}));
		frm.set_query("job_order", () => ({
			filters: { docstatus: 1, order_type: "Quilting" },
		}));
		frm.set_query("core_conversion", () => {
			if (!frm.doc.job_order) {
				return { filters: { name: ["in", [""]] } };
			}
			return {
				filters: {
					job_order: frm.doc.job_order,
					docstatus: 1,
				},
			};
		});
		frm.set_query("fabric_batch", () => {
			if (!frm.doc.fabric_item || !frm.doc.fabric_warehouse) {
				frappe.msgprint(
					__("Select Fabric Item and Fabric Warehouse first to see available batches.")
				);
				return { filters: { name: ["in", [""]] } };
			}
			return {
				query: "erpnext.controllers.queries.get_batch_no",
				filters: {
					item_code: frm.doc.fabric_item,
					warehouse: frm.doc.fabric_warehouse,
				},
			};
		});
		frm.set_query("sheeting_batch", () => {
			if (frm.doc.core_conversion && frm.doc.sheeting_roll_item) {
				return {
					query:
						"pu_foam_master.pufm_manufacturing.doctype.pufm_job_order.pufm_job_order.sheeting_batch_query_for_conversion",
					filters: {
						core_conversion: frm.doc.core_conversion,
						item_code: frm.doc.sheeting_roll_item,
					},
				};
			}
			if (!frm.doc.sheeting_roll_item || !frm.doc.sheeting_warehouse) {
				frappe.msgprint(
					__(
						"Select Sheeting Roll Item and Warehouse (or Core Conversion) first to see batches."
					)
				);
				return { filters: { name: ["in", [""]] } };
			}
			return {
				query: "erpnext.controllers.queries.get_batch_no",
				filters: {
					item_code: frm.doc.sheeting_roll_item,
					warehouse: frm.doc.sheeting_warehouse,
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
		if (frm.doc.job_order) {
			pufm_fetch_quilting_traveler(frm);
		}
	},
	refresh(frm) {
		calculate_variance(frm, true);
		if (frm.doc.job_order) {
			pufm_fetch_quilting_traveler(frm);
		}
	},
	job_order(frm) {
		if (frm.doc.core_conversion) {
			frm.set_value("core_conversion", null);
		}
		pufm_fetch_quilting_traveler(frm);
		if (!frm.doc.job_order) {
			return;
		}
		frappe.db
			.get_value("Pufm Job Order", frm.doc.job_order, ["source_doctype", "source_document"])
			.then((r) => {
				const jo = r && r.message;
				if (jo && jo.source_doctype === "Sales Order" && jo.source_document && !frm.doc.sales_order) {
					frm.set_value("sales_order", jo.source_document);
				}
			});
	},
	core_conversion(frm) {
		frm.set_value("sheeting_batch", null);
		pufm_fetch_quilting_traveler(frm);
	},
	fetch_job_instructions(frm) {
		pufm_fetch_quilting_traveler(frm);
	},
	fabric_item(frm) {
		frm.set_value("fabric_batch", null);
	},
	fabric_warehouse(frm) {
		frm.set_value("fabric_batch", null);
		clear_warehouse_if_wrong_company(frm, "fabric_warehouse");
	},
	fabric_qty_meters(frm) {
		calculate_variance(frm);
	},
	sheeting_roll_item(frm) {
		frm.set_value("sheeting_batch", null);
	},
	sheeting_warehouse(frm) {
		frm.set_value("sheeting_batch", null);
		clear_warehouse_if_wrong_company(frm, "sheeting_warehouse");
	},
	sheeting_qty_meters(frm) {
		calculate_variance(frm);
	},
	output_qty_meters(frm) {
		calculate_variance(frm);
	},
	company(frm) {
		["target_warehouse", "fabric_warehouse", "sheeting_warehouse"].forEach((field) => {
			clear_warehouse_if_wrong_company(frm, field);
		});
	},
});

function calculate_variance(frm, silent) {
	const total_input = Math.max(flt(frm.doc.fabric_qty_meters), flt(frm.doc.sheeting_qty_meters));
	const variance = frm.doc.output_qty_meters ? total_input - flt(frm.doc.output_qty_meters) : 0;

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

function clear_warehouse_if_wrong_company(frm, fieldname) {
	const wh = frm.doc[fieldname];
	if (!wh || !frm.doc.company) {
		return;
	}
	frappe.db.get_value("Warehouse", wh, "company").then((r) => {
		const wh_company = r && r.message && r.message.company;
		if (wh_company && wh_company !== frm.doc.company) {
			frm.set_value(fieldname, null);
		}
	});
}

function pufm_fetch_quilting_traveler(frm) {
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
