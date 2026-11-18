// Copyright (c) 2026, PU Foam Master and contributors

frappe.ui.form.on("PUFM Create Customer", {
	refresh(frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Trade Customer Only"), () => {
				frm.set_value("registration_type", "Trade Customer Only");
			});
			frm.add_custom_button(__("Main + Rebate Wallet"), () => {
				frm.set_value("registration_type", "Main and Rebate Wallet");
			});
			frm.add_custom_button(__("Suggest Next Main ID"), () => {
				frappe.call({
					method:
						"pu_foam_master.pufm_manufacturing.utils.customer_creation.suggest_next_main_customer_id",
					callback(r) {
						if (r.message) {
							frm.set_value("main_customer_id", String(r.message));
							sync_rebate_id(frm);
						}
					},
				});
			});
		}

		if (frm.doc.created_main_customer && frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Open Main Customer"), () => {
				frappe.set_route("Form", "Customer", frm.doc.created_main_customer);
			});
		}
		if (frm.doc.created_rebate_customer && frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Open Rebate Customer"), () => {
				frappe.set_route("Form", "Customer", frm.doc.created_rebate_customer);
			});
		}
	},

	registration_type(frm) {
		if (frm.doc.registration_type === "Main and Rebate Wallet") {
			frm.set_value("is_distributor", 1);
		}
		if (frm.doc.registration_type === "Rebate Wallet for Existing Main") {
			frm.set_value("customer_name", "");
		}
		sync_rebate_id(frm);
		sync_rebate_display_name(frm);
	},

	company(frm) {
		frm.trigger("refresh_preview_accounts");
	},

	main_customer_id(frm) {
		sync_rebate_id(frm);
	},

	existing_main_customer(frm) {
		if (!frm.doc.existing_main_customer) {
			return;
		}
		const main_name = frm.doc.existing_main_customer;
		if (/^[1-9]\d*$/.test(main_name)) {
			frm.set_value("main_customer_id", main_name);
			sync_rebate_id(frm);
			frappe.db.get_value(
				"Customer",
				frm.doc.existing_main_customer,
				"customer_name",
				(r) => {
					if (r.message && !frm.doc.__rebate_name_edited_manually) {
						frm.set_value("rebate_customer_name", `${String(r.message).trim()} - Rebate`);
					}
				}
			);
		} else {
			frappe.msgprint({
				title: __("Non-numeric main customer ID"),
				indicator: "orange",
				message: __(
					"Customer {0} does not use a numeric ID. PUFM Create Customer can only add rebate wallets when the main Customer name is a positive integer (e.g. 330).",
					[main_name]
				),
			});
		}
	},

	customer_name(frm) {
		sync_rebate_display_name(frm);
	},

	rebate_customer_name(frm) {
		const autoSuffix = " - Rebate";
		const expected =
			frm.doc.registration_type === "Main and Rebate Wallet" && frm.doc.customer_name
				? `${frm.doc.customer_name.trim()}${autoSuffix}`
				: "";
		const current = (frm.doc.rebate_customer_name || "").trim();
		frm.doc.__rebate_name_edited_manually =
			Boolean(current) && expected && current !== expected;
	},
});

function sync_rebate_display_name(frm) {
	const t = frm.doc.registration_type;
	if (t !== "Main and Rebate Wallet") {
		return;
	}
	if (frm.doc.__rebate_name_edited_manually) {
		return;
	}
	if (frm.doc.customer_name) {
		frm.set_value("rebate_customer_name", `${frm.doc.customer_name.trim()} - Rebate`);
	}
}

function sync_rebate_id(frm) {
	const t = frm.doc.registration_type;
	if (!["Main and Rebate Wallet", "Rebate Wallet for Existing Main"].includes(t)) {
		frm.set_value("rebate_customer_id", "");
		return;
	}
	const main_id = (frm.doc.main_customer_id || "").trim();
	if (/^[1-9]\d*$/.test(main_id)) {
		frm.set_value("rebate_customer_id", `REBATE${main_id}`);
	}
}