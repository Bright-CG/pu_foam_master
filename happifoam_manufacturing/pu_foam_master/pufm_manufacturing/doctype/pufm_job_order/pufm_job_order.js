// Copyright (c) 2026, PU Foam Master and contributors
// For license information, please see license.txt

frappe.ui.form.on("Pufm Job Order", {
	setup(frm) {
		frm.set_query("item_code", "mattress_instructions", () => {
			return {
				filters: {
					disabled: 0,
					is_stock_item: 1,
					name: ["like", "%-%"],
				},
				query: "pu_foam_master.pufm_manufacturing.doctype.pufm_job_order.pufm_job_order.mattress_item_query",
			};
		});
		frm.set_query("source_block", "sheeting_instructions", () => {
			return {
				filters: {
					disabled: 0,
					is_stock_item: 1,
					name: ["like", "% Block"],
				},
			};
		});
	},
	onload(frm) {
		ensure_draft_pending_slicing(frm);
	},
	onload_post_render(frm) {
		ensure_draft_pending_slicing(frm);
	},
	refresh(frm) {
		ensure_draft_pending_slicing(frm);
		frm.clear_custom_buttons();
		// Only route from submitted Job Orders — prevents draft-stage duplicate starts
		if (frm.is_new() || frm.doc.docstatus !== 1) {
			return;
		}

		if (frm.doc.workflow_status === "Pending Slicing") {
			if (frm.doc.order_type === "Sheetings") {
				frm.add_custom_button(__("Start Sheeting Conversion"), () => {
					frappe.new_doc("Pufm Sheeting Conversion", {
						job_order: frm.doc.name,
						company: frm.doc.company || undefined,
					});
				}).addClass("btn-primary");
			} else if (frm.doc.order_type === "Mattress") {
				frm.add_custom_button(__("Start Core Slicing"), () => {
					frappe.new_doc("Mattress Core Conversion", {
						job_order: frm.doc.name,
						company: frm.doc.company || undefined,
					});
				}).addClass("btn-primary");
			}
		}

		if (
			frm.doc.workflow_status === "Pending Assembly" &&
			frm.doc.order_type === "Mattress"
		) {
			frm.add_custom_button(__("Start Assembly"), () => {
				frappe.new_doc("Mattress Production Entry", {
					job_order: frm.doc.name,
					company: frm.doc.company || undefined,
				});
			}).addClass("btn-primary");
		}
	},
	order_type(frm) {
		if (frm.doc.docstatus === 0) {
			ensure_draft_pending_slicing(frm);
		}
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

function ensure_draft_pending_slicing(frm) {
	// Ignore list-filter / duplicate prefill of Pending Assembly or Completed on drafts.
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
