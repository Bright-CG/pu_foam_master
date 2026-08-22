// Copyright (c) 2026, PU Foam Master and contributors
// For license information, please see license.txt

frappe.ui.form.on("Pufm Job Order", {
	setup(frm) {
		frm.set_query("item_code", "mattress_instructions", () => ({
			filters: { disabled: 0, is_stock_item: 1, name: ["like", "%-%"] },
			query:
				"pu_foam_master.pufm_manufacturing.doctype.pufm_job_order.pufm_job_order.mattress_item_query",
		}));
		frm.set_query("source_block", "sheeting_instructions", () => ({
			filters: { disabled: 0, is_stock_item: 1, name: ["like", "% Block"] },
		}));
		frm.set_query("source_block", "quilting_instructions", () => ({
			filters: { disabled: 0, is_stock_item: 1, name: ["like", "% Block"] },
		}));
	},
	onload(frm) {
		ensure_draft_pending_slicing(frm);
		limit_quilting_rows(frm);
	},
	onload_post_render(frm) {
		ensure_draft_pending_slicing(frm);
	},
	refresh(frm) {
		ensure_draft_pending_slicing(frm);
		limit_quilting_rows(frm);
		frm.clear_custom_buttons();
		if (frm.is_new() || frm.doc.docstatus !== 1) {
			return;
		}

		if (frm.doc.workflow_status === "Pending Slicing") {
			if (frm.doc.order_type === "Sheetings") {
				frm.add_custom_button(__("Start Sheeting Conversion"), () => {
					frappe.new_doc("Pufm Sheeting Conversion", { job_order: frm.doc.name });
				}).addClass("btn-primary");
			} else if (frm.doc.order_type === "Mattress" || frm.doc.order_type === "Quilting") {
				frm.add_custom_button(__("Start Core Slicing"), () => {
					if (frm.doc.order_type === "Quilting") {
						frappe.call({
							method:
								"pu_foam_master.pufm_manufacturing.doctype.pufm_job_order.pufm_job_order.get_core_conversion_prefill",
							args: { job_order: frm.doc.name },
							callback(r) {
								const prefill = r.message || {};
								frappe.model.with_doctype("Mattress Core Conversion", () => {
									const doc = frappe.model.get_new_doc("Mattress Core Conversion");
									doc.job_order = prefill.job_order;
									(prefill.inputs || []).forEach((row) => {
										const d = frappe.model.add_child(doc, "inputs");
										d.item_code = row.item_code;
										d.qty = row.qty;
									});
									(prefill.outputs || []).forEach((row) => {
										const d = frappe.model.add_child(doc, "outputs");
										d.item_code = row.item_code;
										d.qty = row.qty;
									});
									frappe.set_route("Form", "Mattress Core Conversion", doc.name);
									// CBM hydrate runs on form refresh (child events do not fire for add_child).
								});
							},
						});
					} else {
						frappe.new_doc("Mattress Core Conversion", { job_order: frm.doc.name });
					}
				}).addClass("btn-primary");
			}
		}

		if (frm.doc.order_type === "Quilting" && frm.doc.workflow_status === "Pending Quilting") {
			frm.add_custom_button(__("Start Quilting"), () => {
				frappe.call({
					method:
						"pu_foam_master.pufm_manufacturing.doctype.pufm_job_order.pufm_job_order.get_quilting_record_prefill",
					args: { job_order: frm.doc.name },
					callback(r) {
						const prefill = r.message || {};
						frappe.new_doc("Quilting Record", {
							job_order: prefill.job_order,
							core_conversion: prefill.core_conversion,
							sales_order: prefill.sales_order || undefined,
							fabric_item: prefill.fabric_item,
							sheeting_roll_item: prefill.sheeting_roll_item,
							finished_item: prefill.finished_item,
							planned_qty_meters: prefill.planned_qty_meters || undefined,
						});
					},
				});
			});
			frm.add_custom_button(__("Start Assembly"), () => {
				frappe.call({
					method:
						"pu_foam_master.pufm_manufacturing.doctype.pufm_job_order.pufm_job_order.get_mattress_production_prefill",
					args: { job_order: frm.doc.name },
					callback(r) {
						const prefill = r.message || {};
						frappe.new_doc("Mattress Production Entry", {
							job_order: prefill.job_order,
							core_conversion: prefill.core_conversion,
							sales_order: prefill.sales_order || undefined,
						});
					},
				});
			}).addClass("btn-primary");
		}

		if (frm.doc.workflow_status === "Pending Assembly" && frm.doc.order_type === "Mattress") {
			frm.add_custom_button(__("Start Assembly"), () => {
				frappe.new_doc("Mattress Production Entry", { job_order: frm.doc.name });
			}).addClass("btn-primary");
		}
	},
	order_type(frm) {
		if (frm.doc.docstatus === 0) {
			ensure_draft_pending_slicing(frm);
		}
		limit_quilting_rows(frm);
		frm.refresh_fields();
	},
});

frappe.ui.form.on("Pufm Sheeting Instruction", {
	length_inches(frm, cdt, cdn) {
		recalc_sheeting_cbm(frm, cdt, cdn);
	},
	width_inches(frm, cdt, cdn) {
		recalc_sheeting_cbm(frm, cdt, cdn);
	},
	thickness_inches(frm, cdt, cdn) {
		recalc_sheeting_cbm(frm, cdt, cdn);
	},
	quantity(frm, cdt, cdn) {
		recalc_sheeting_cbm(frm, cdt, cdn);
	},
});

frappe.ui.form.on("Pufm Quilting Instruction", {
	quilting_instructions_add(frm) {
		limit_quilting_rows(frm);
	},
});

function limit_quilting_rows(frm) {
	if (frm.doc.order_type !== "Quilting") {
		return;
	}
	const grid = frm.fields_dict.quilting_instructions && frm.fields_dict.quilting_instructions.grid;
	if (!grid) {
		return;
	}
	const allow = (frm.doc.quilting_instructions || []).length < 1;
	grid.wrapper.find(".grid-add-row").toggle(allow);
}

function ensure_draft_pending_slicing(frm) {
	if (frm.doc.docstatus !== 0) {
		return;
	}
	if (frm.doc.workflow_status !== "Pending Slicing") {
		frm.set_value("workflow_status", "Pending Slicing");
	}
	if (frm.doc.sliced_by) {
		frm.set_value("sliced_by", null);
	}
	if (frm.doc.assembled_by) {
		frm.set_value("assembled_by", null);
	}
}

function recalc_sheeting_cbm(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	frappe.db.get_single_value("Pufm Manufacturing Settings", "cbm_factor").then((factor) => {
		const cbmFactor = flt(factor) || 61023.74;
		const length = flt(row.length_inches);
		const width = flt(row.width_inches);
		const thickness = flt(row.thickness_inches);
		const qty = flt(row.quantity);
		if (length <= 0 || width <= 0 || thickness <= 0 || qty <= 0) {
			frappe.model.set_value(cdt, cdn, "calculated_cbm", 0);
			return;
		}
		const cbm = (length * width * thickness * qty) / cbmFactor;
		frappe.model.set_value(cdt, cdn, "calculated_cbm", flt(cbm, 5));
	});
}
