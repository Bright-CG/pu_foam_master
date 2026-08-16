// Copyright (c) 2026, PU Foam Master and contributors
// For license information, please see license.txt

frappe.ui.form.on("Mattress Production Entry", {
	setup(frm) {
		frm.add_fetch("mattress_item", "custom_finish_type", "finish_type");
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
		frm.set_query("fabric_item", "production_items", (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			return {
				query:
					"pu_foam_master.pufm_manufacturing.doctype.mattress_production_entry.mattress_production_entry.mattress_fabric_item_query",
				filters: {
					mattress_item: row.mattress_item || "",
					preferred_item_group: preferred_face_group(row.finish_type),
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
		frm.set_query("side_fabric_item", "production_items", (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			return {
				query:
					"pu_foam_master.pufm_manufacturing.doctype.mattress_production_entry.mattress_production_entry.mattress_fabric_item_query",
				filters: {
					mattress_item: row.mattress_item || "",
					preferred_item_group: "Quilted Fabric",
				},
			};
		});
		frm.set_query("side_fabric_batch", "production_items", (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			if (!row.side_fabric_item || !doc.source_warehouse) {
				return { filters: { name: ["in", [""]] } };
			}
			return {
				query: "erpnext.controllers.queries.get_batch_no",
				filters: {
					item_code: row.side_fabric_item,
					warehouse: doc.source_warehouse,
				},
			};
		});
		frm.set_query("label_item", "production_items", () => ({
			filters: {
				item_group: "Labels",
				disabled: 0,
				has_batch_no: 0,
				has_serial_no: 0,
				is_stock_item: 1,
			},
		}));
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
		apply_side_fabric_grid_state(frm);
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
		const errors = [];
		(frm.doc.production_items || []).forEach((row) => {
			const prefix = __("Row {0}", [row.idx]);
			if (flt(row.qty) <= 0) {
				errors.push(__("{0}: Quantity must be greater than zero.", [prefix]));
			}
			if (!row.core_batch) {
				errors.push(__("{0}: Core Batch is required.", [prefix]));
			}
			if (!row.fabric_item) {
				errors.push(__("{0}: Fabric Item is required.", [prefix]));
			}
			if (!row.fabric_batch) {
				errors.push(__("{0}: Fabric Batch is required.", [prefix]));
			}
			if (!row.label_item) {
				errors.push(__("{0}: Label Item is required.", [prefix]));
			}
			if ((row.finish_type || "") === "Side Quilted") {
				if (!row.side_fabric_item || !row.side_fabric_batch) {
					errors.push(
						__(
							"{0}: The mattress '{1}' is Side Quilted. You must select a Side Fabric and Batch.",
							[prefix, row.mattress_item || ""]
						)
					);
				} else if (row.side_fabric_item === row.fabric_item) {
					errors.push(
						__("{0}: Side Fabric Item must be different from the face Fabric Item.", [prefix])
					);
				}
			}
		});
		if (errors.length) {
			frappe.throw(errors.join("<br>"));
		}
	},
});

frappe.ui.form.on("Mattress Production Item", {
	production_items_add(frm, cdt, cdn) {
		prefill_label_item(cdt, cdn);
	},
	mattress_item(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.mattress_item) {
			frappe.model.set_value(cdt, cdn, "finish_type", "");
			apply_side_fabric_grid_state(frm);
			return;
		}
		frappe.model.set_value(cdt, cdn, "core_batch", "");
		frappe.model.set_value(cdt, cdn, "fabric_item", "");
		frappe.model.set_value(cdt, cdn, "fabric_batch", "");
		frappe.model.set_value(cdt, cdn, "side_fabric_item", "");
		frappe.model.set_value(cdt, cdn, "side_fabric_batch", "");
		if (!row.label_item) {
			prefill_label_item(cdt, cdn);
		}
		frappe.db.get_value("Item", row.mattress_item, "custom_finish_type").then((r) => {
			const finish = (r && r.message && r.message.custom_finish_type) || "";
			frappe.model.set_value(cdt, cdn, "finish_type", finish);
			apply_side_fabric_grid_state(frm);
		});
	},
	fabric_item(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "fabric_batch", "");
	},
	side_fabric_item(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "side_fabric_batch", "");
	},
});

function prefill_label_item(cdt, cdn) {
	frappe.db.get_single_value("Pufm Manufacturing Settings", "default_label_item").then((label) => {
		if (label) {
			frappe.model.set_value(cdt, cdn, "label_item", label);
		}
	});
}

function apply_side_fabric_grid_state(frm) {
	const grid = frm.fields_dict.production_items && frm.fields_dict.production_items.grid;
	if (!grid || !grid.grid_rows) {
		return;
	}
	grid.grid_rows.forEach((grid_row) => {
		const sq = (grid_row.doc.finish_type || "") === "Side Quilted";
		if (grid_row.toggle_editable) {
			grid_row.toggle_editable("side_fabric_item", sq);
			grid_row.toggle_editable("side_fabric_batch", sq);
		}
	});
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

function preferred_face_group(finish_type) {
	if (finish_type === "Fully Quilted") {
		return "Quilted Fabric";
	}
	if (finish_type === "Plain" || finish_type === "Side Quilted") {
		return "Plain Fabric";
	}
	return "";
}

function guess_core_item(mattress_item) {
	// Core SKU still follows the generator naming pattern.
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
