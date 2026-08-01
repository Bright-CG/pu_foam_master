frappe.ui.form.on("Density Configuration", {
    setup: function(frm) {
        // Company has no `disabled` column in ERPNext — do not filter on it.
        frm.set_query("company", function() {
            return {};
        });
    },
    onload: function(frm) {
        if (frm.is_new() && !frm.doc.company) {
            let company = frappe.defaults.get_user_default("Company");
            if (company) {
                frm.set_value("company", company);
            } else {
                frappe.db.get_single_value("Global Defaults", "default_company").then((fallback) => {
                    if (fallback) {
                        frm.set_value("company", fallback);
                    }
                });
            }
        }
    },
    refresh: function(frm) {
        calculate_parent(frm);
        recalculate_operations(frm);
        frm.clear_custom_buttons();
        if (!frm.is_new() && frm.doc.docstatus !== 2) {
            frm.add_custom_button(__("Clone Recipe"), () => {
                clone_density_recipe(frm);
            });
        }
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
    get_inches_to_meters_factor().then((inchToM) => {
        let wm = round5((frm.doc.width_inches || 0) * inchToM);
        let hm = round5((frm.doc.height_inches || 0) * inchToM);
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
    });
}

function get_inches_to_meters_factor() {
    return frappe.db
        .get_single_value("Pufm Manufacturing Settings", "inches_to_meters_factor")
        .then((factor) => {
            const parsed = flt(factor);
            return parsed > 0 ? parsed : 0.0254;
        });
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

function clone_density_recipe(frm) {
    frappe.prompt(
        [
            {
                fieldname: "density_name",
                fieldtype: "Data",
                label: __("New Density Name"),
                reqd: 1,
                description: __(
                    "Recipe fields are copied. Virtual Item and Active BOM are left blank so a new BOM is created on submit."
                ),
            },
        ],
        (values) => {
            const new_name = (values.density_name || "").trim();
            if (!new_name) {
                frappe.msgprint(__("New Density Name is required."));
                return;
            }
            frappe.call({
                method:
                    "pu_foam_master.pufm_manufacturing.doctype.density_configuration.density_configuration.get_clone_recipe",
                args: {
                    source_name: frm.doc.name,
                    new_density_name: new_name,
                },
                freeze: true,
                freeze_message: __("Preparing clone..."),
                callback(r) {
                    const data = r.message;
                    if (!data) {
                        return;
                    }
                    frappe.model.with_doctype("Density Configuration", () => {
                        const doc = frappe.model.get_new_doc("Density Configuration");
                        const skip = new Set([
                            "name",
                            "creation",
                            "modified",
                            "modified_by",
                            "owner",
                            "docstatus",
                            "idx",
                            "production_inputs",
                            "bom_operations",
                            "virtual_item",
                            "active_bom",
                            "amended_from",
                        ]);
                        Object.keys(data).forEach((key) => {
                            if (skip.has(key)) {
                                return;
                            }
                            if (data[key] !== undefined && data[key] !== null) {
                                doc[key] = data[key];
                            }
                        });
                        doc.density_name = new_name;
                        doc.virtual_item = null;
                        doc.active_bom = null;

                        (data.production_inputs || []).forEach((row) => {
                            const child = frappe.model.add_child(
                                doc,
                                "Production Inputs",
                                "production_inputs"
                            );
                            Object.keys(row).forEach((key) => {
                                if (
                                    [
                                        "name",
                                        "owner",
                                        "creation",
                                        "modified",
                                        "modified_by",
                                        "parent",
                                        "parentfield",
                                        "parenttype",
                                        "docstatus",
                                    ].includes(key)
                                ) {
                                    return;
                                }
                                child[key] = row[key];
                            });
                        });

                        (data.bom_operations || []).forEach((row) => {
                            const child = frappe.model.add_child(
                                doc,
                                "BOM Operation",
                                "bom_operations"
                            );
                            Object.keys(row).forEach((key) => {
                                if (
                                    [
                                        "name",
                                        "owner",
                                        "creation",
                                        "modified",
                                        "modified_by",
                                        "parent",
                                        "parentfield",
                                        "parenttype",
                                        "docstatus",
                                    ].includes(key)
                                ) {
                                    return;
                                }
                                child[key] = row[key];
                            });
                        });

                        frappe.set_route("Form", doc.doctype, doc.name);
                    });
                },
            });
        },
        __("Clone Recipe"),
        __("Create Draft")
    );
}
