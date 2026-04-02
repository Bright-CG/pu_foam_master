// Copyright (c) 2026, Happifoam and contributors
// For license information, please see license.txt

frappe.ui.form.on("Density Configuration", {
    refresh: function(frm) {
        // Refresh calculations
        calculate_parent_values(frm);
    },
    width_inches: function(frm) {
        calculate_parent_values(frm);
    },
    height_inches: function(frm) {
        calculate_parent_values(frm);
    },
    conveyor_speed: function(frm) {
        calculate_parent_values(frm);
    }
});

frappe.ui.form.on("Production Inputs", {
    flow_factor: function(frm, cdt, cdn) {
        calculate_child_row(frm, cdt, cdn);
    },
    set_at: function(frm, cdt, cdn) {
        calculate_child_row(frm, cdt, cdn);
    }
});

frappe.ui.form.on("Output Item Variant", {
    width: function(frm, cdt, cdn) {
        calculate_variant_row(frm, cdt, cdn);
    },
    height: function(frm, cdt, cdn) {
        calculate_variant_row(frm, cdt, cdn);
    },
    length: function(frm, cdt, cdn) {
        calculate_variant_row(frm, cdt, cdn);
    }
});

function calculate_parent_values(frm) {
    let width_m = (frm.doc.width_inches || 0) * 0.0254;
    let height_m = (frm.doc.height_inches || 0) * 0.0254;
    let output_rate = width_m * height_m * (frm.doc.conveyor_speed || 0);

    frm.set_value("width_meters", width_m);
    frm.set_value("height_meters", height_m);
    frm.set_value("output_rate_m3_per_min", output_rate);

    // Update all child rows since output_rate changed
    if (frm.doc.production_inputs) {
        frm.doc.production_inputs.forEach(row => {
            calculate_child_row(frm, row.doctype, row.name);
        });
    }
}

function calculate_child_row(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    let flow_min = (row.flow_factor || 0) * (row.set_at || 0);
    let qty_per_m3 = 0;

    if (frm.doc.output_rate_m3_per_min) {
        qty_per_m3 = flow_min / frm.doc.output_rate_m3_per_min;
    }

    frappe.model.set_value(cdt, cdn, "flow_min", flow_min);
    frappe.model.set_value(cdt, cdn, "qty_per_m3", qty_per_m3);
}

function calculate_variant_row(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    let unit_cbm = (row.width * row.height * row.length) / 61023.74;
    frappe.model.set_value(cdt, cdn, "unit_cbm", unit_cbm);
}
