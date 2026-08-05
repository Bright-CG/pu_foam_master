// Copyright (c) 2026, PU Foam Master and contributors
// For license information, please see license.txt

frappe.ui.form.on("Mattress Production Entry", {
	setup(frm) {
		frm.set_query("source_warehouse", () => ({
			filters: { company: frm.doc.company, disabled: 0 },
		}));
		frm.set_query("target_warehouse", () => ({
			filters: { company: frm.doc.company, disabled: 0 },
		}));
		frm.set_query("core_batch", "production_items", (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			const core_item = guess_core_item(row.mattress_item);
			if (!core_item || !doc.source_warehouse) {
				return { filters: { name: ["in", [""]] } };
			}
			return {
				query: "erpnext.controllers.queries.get_batch_no",
				filters: {
					item_code: core_item,
					warehouse: doc.source_warehouse,
				},
			};
		});
		frm.set_query("fabric_batch", "production_items", (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			if (!row.fabric_item || !doc.source_warehouse) {
				frappe.msgprint(
					__("Please select Fabric Item and Source/WIP Warehouse first to see available batches.")
				);
				return { filters: { name: ["in", [""]] } };
			}
			return {
				query: "erpnext.controllers.queries.get_batch_no",
				filters: {
					item_code: row.fabric_item,
					warehouse: doc.source_warehouse,
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
		if (frm.is_new() && !frm.doc.processed_by) {
			frm.set_value("processed_by", frappe.session.user);
		}
		if (frm.doc.job_order) {
			pufm_fetch_job_instructions(frm);
		}
	},
	refresh(frm) {
		frm.set_query("mattress_item", "production_items", () => ({
			filters: { item_group: "Finished Mattresses" },
		}));
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
	company(frm) {
		clear_warehouse_if_wrong_company(frm, "source_warehouse");
		clear_warehouse_if_wrong_company(frm, "target_warehouse");
	},
	validate(frm) {
		(frm.doc.production_items || []).forEach((row) => {
			if (flt(row.qty) <= 0) {
				frappe.throw(__("Quantity must be greater than zero in all production rows."));
			}
		});
	},
});

frappe.ui.form.on("Mattress Production Item", {
	mattress_item(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.mattress_item) {
			return;
		}
		set_fabric_filter(frm, row.mattress_item);
		frappe.model.set_value(cdt, cdn, "core_batch", "");
		frappe.model.set_value(cdt, cdn, "fabric_batch", "");
	},
	fabric_item(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "fabric_batch", "");
	},
});

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

function guess_core_item(mattress_item) {
	// New: 75x42x8-PLAIN / -SQ / -FQ -> 75x42x8-CORE
	// Legacy: MAT-{BRAND}-{size} -> CORE-{BRAND}-{size}
	if (!mattress_item) {
		return null;
	}
	const code = String(mattress_item);
	const upper = code.toUpperCase();
	for (const suffix of ["-PLAIN", "-SQ", "-FQ"]) {
		if (upper.endsWith(suffix)) {
			return code.slice(0, code.length - suffix.length) + "-CORE";
		}
	}
	if (upper.startsWith("MAT-")) {
		return "CORE-" + code.slice(4);
	}
	return null;
}

function set_fabric_filter(frm, mattressItem) {
	frappe.call({
		method:
			"pu_foam_master.pufm_manufacturing.doctype.mattress_production_entry.mattress_production_entry.get_allowed_fabric_items_for_mattress",
		args: { mattress_item: mattressItem },
		callback: (r) => {
			const allowedItems = r.message || [];
			frm.set_query("fabric_item", "production_items", () => ({
				filters: {
					name: ["in", allowedItems.length ? allowedItems : [""]],
				},
			}));
		},
	});
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
