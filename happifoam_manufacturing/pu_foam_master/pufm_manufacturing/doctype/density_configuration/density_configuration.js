frappe.ui.form.on("Density Configuration", {
    setup: function(frm) {
        frm.set_query("company", function() {
            return { filters: { disabled: 0 } };
        });
    },
    onload: function(frm) {
        if (frm.is_new() && !frm.doc.company) {
            frappe.db.exists("Company", "Solarfoam").then((exists) => {
                if (exists) {
                    frm.set_value("company", "Solarfoam");
                } else {
                    frm.set_value("company", frappe.defaults.get_user_default("Company"));
                }
            });
        }
    },
    refresh: function(frm) {
        calculate_parent(frm);
        recalculate_operations(frm);
    },
    width_inches: function(frm) {
        calculate_parent(frm);
    },
    height_inches: function(frm) {
        calculate_parent(frm);
    },
    conveyor_speed: function(frm) {
        calculate_parent(frm);
    },
    calibration_factor: function(frm) {
        calculate_parent(frm);
    },
    production_inputs_add: function(frm) {
        calculate_parent(frm);
    },
    bom_operations_add: function(frm, cdt, cdn) {
        apply_operation_time(frm, cdt, cdn);
        calculate_operation_row(frm, cdt, cdn);
        frm.refresh_field("bom_operations");
    },
    generate_block_variants: function(frm) {
        if (!frm.doc.name || frm.is_new()) {
            frappe.msgprint(__("Please save the Density Configuration first."));
            return;
        }
        if (!frm.doc.target_block_lengths) {
            frappe.msgprint(__("Please enter lengths first."));
            return;
        }

        frm.call({
            method: "pu_foam_master.pufm_manufacturing.doctype.density_configuration.density_configuration.generate_block_items",
            args: {
                docname: frm.doc.name,
                lengths_string: frm.doc.target_block_lengths,
            },
            freeze: true,
            freeze_message: __("Generating block items..."),
            callback: function(r) {
                if (r.message) {
                    frappe.msgprint({
                        title: __("Block Items"),
                        indicator: "green",
                        message: r.message.message || __("Done"),
                    });
                }
            },
            error: function() {
                frappe.msgprint({
                    title: __("Error"),
                    indicator: "red",
                    message: __("Failed to generate block items."),
                });
            },
        });
    },
});

frappe.ui.form.on("Production Inputs", {
    flow_factor: function(frm, cdt, cdn) {
        calculate_production_row(frm, cdt, cdn);
    },
    set_at: function(frm, cdt, cdn) {
        calculate_production_row(frm, cdt, cdn);
    },
});

frappe.ui.form.on("BOM Operation", {
    workstation: function(frm, cdt, cdn) {
        apply_operation_time(frm, cdt, cdn);
        calculate_operation_row(frm, cdt, cdn);
    },
    time: function(frm, cdt, cdn) {
        calculate_operation_row(frm, cdt, cdn);
    },
    hour_rate: function(frm, cdt, cdn) {
        calculate_operation_row(frm, cdt, cdn);
    },
});

function round5(value) {
    return Number(flt(value || 0, 5));
}

function apply_operation_time(frm, cdt, cdn) {
    let rate = flt(frm.doc.output_rate_m3_per_min);
    let time_mins = rate ? round5(1 / rate) : 0;
    frappe.model.set_value(cdt, cdn, "time", time_mins);
}

function calculate_parent(frm) {
    let wm = round5((frm.doc.width_inches || 0) * 0.0254);
    let hm = round5((frm.doc.height_inches || 0) * 0.0254);
    let factor = frm.doc.calibration_factor || 1.0;
    let rate = round5((frm.doc.conveyor_speed || 0) * factor * wm * hm);

    frm.set_value("width_meters", wm);
    frm.set_value("height_meters", hm);
    frm.set_value("output_rate_m3_per_min", rate);

    if (frm.doc.production_inputs) {
        frm.doc.production_inputs.forEach((row) => {
            calculate_production_row(frm, row.doctype, row.name);
        });
    }
    recalculate_operations(frm);
}

function calculate_production_row(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    let flow = round5((row.flow_factor || 0) * (row.set_at || 0));
    let qty = 0;
    if (frm.doc.output_rate_m3_per_min) {
        qty = round5(flow / frm.doc.output_rate_m3_per_min);
    }
    frappe.model.set_value(cdt, cdn, "flow_min", flow);
    frappe.model.set_value(cdt, cdn, "qty_per_m3", qty);
}

function calculate_operation_row(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    let cost = round5(((row.time || 0) / 60.0) * (row.hour_rate || 0));
    frappe.model.set_value(cdt, cdn, "operating_cost", cost);
}

function recalculate_operations(frm) {
    if (!frm.doc.bom_operations) {
        return;
    }
    frm.doc.bom_operations.forEach((row) => {
        apply_operation_time(frm, row.doctype, row.name);
        calculate_operation_row(frm, row.doctype, row.name);
        frm.refresh_field("bom_operations");
    });
}
