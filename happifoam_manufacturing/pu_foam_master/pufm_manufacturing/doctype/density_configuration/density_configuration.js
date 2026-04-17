frappe.ui.form.on("Density Configuration", {
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
    bom_operations_add: function(frm) {
        recalculate_operations(frm);
    },
    generate_variants_btn: function(frm) {
        if (!frm.doc.density_name || !frm.doc.standard_lengths) {
            frappe.msgprint("Please fill in Density Name and Target Lengths first.");
            return;
        }

        frappe.confirm('This will create or update Item Variants. Continue?', () => {
            frm.call({
                method: "generate_variants",
                doc: frm.doc,
                callback: function(r) {
                    if (r.message) {
                        frappe.msgprint({
                            title: __('Success'),
                            indicator: 'green',
                            message: __("Generated {0} Block Variants for Density {1}.", [r.message, frm.doc.density_name])
                        });
                    }
                }
            });
        });
    }
});

frappe.ui.form.on("Production Inputs", {
    flow_factor: function(frm, cdt, cdn) {
        calculate_production_row(frm, cdt, cdn);
    },
    set_at: function(frm, cdt, cdn) {
        calculate_production_row(frm, cdt, cdn);
    }
});

frappe.ui.form.on("BOM Operation", {
    time: function(frm, cdt, cdn) {
        calculate_operation_row(frm, cdt, cdn);
    },
    hour_rate: function(frm, cdt, cdn) {
        calculate_operation_row(frm, cdt, cdn);
    }
});

function calculate_parent(frm) {
    let wm = (frm.doc.width_inches || 0) * 0.0254;
    let hm = (frm.doc.height_inches || 0) * 0.0254;
    let factor = (frm.doc.calibration_factor || 1.0);
    let rate = (frm.doc.conveyor_speed || 0) * factor * wm * hm;

    frm.set_value("width_meters", wm);
    frm.set_value("height_meters", hm);
    frm.set_value("output_rate_m3_per_min", rate);

    // Update all production rows because rate changed
    if (frm.doc.production_inputs) {
        frm.doc.production_inputs.forEach(row => {
            calculate_production_row(frm, row.doctype, row.name);
        });
    }
}

function calculate_production_row(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    let flow = (row.flow_factor || 0) * (row.set_at || 0);
    let qty = 0;
    if (frm.doc.output_rate_m3_per_min) {
        qty = flow / frm.doc.output_rate_m3_per_min;
    }
    frappe.model.set_value(cdt, cdn, "flow_min", flow);
    frappe.model.set_value(cdt, cdn, "qty_per_m3", qty);
}

function calculate_operation_row(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    // operating_cost = (time / 60) * hour_rate
    let cost = ((row.time || 0) / 60.0) * (row.hour_rate || 0);
    frappe.model.set_value(cdt, cdn, "operating_cost", cost);
}

function recalculate_operations(frm) {
    if (frm.doc.bom_operations) {
        frm.doc.bom_operations.forEach(row => {
            calculate_operation_row(frm, row.doctype, row.name);
        });
    }
}
