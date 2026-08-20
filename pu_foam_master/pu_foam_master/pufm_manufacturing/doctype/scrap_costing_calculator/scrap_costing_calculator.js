frappe.ui.form.on("Scrap Costing Calculator", {
	onload(frm) {
		if (frm.is_new()) {
			ensure_scrap_defaults(frm);
		}
	},
	shipping_cost_ngn(frm) {
		recalculate(frm);
	},
	local_logistics_ngn(frm) {
		recalculate(frm);
	},
	process_loss_contingency_ngn(frm) {
		recalculate(frm);
	},
	container_capacity_kg(frm) {
		recalculate(frm);
	},
});

function ensure_scrap_defaults(frm) {
	frappe.db
		.get_value("Pufm Manufacturing Settings", "Pufm Manufacturing Settings", [
			"scrap_default_container_capacity_kg",
			"scrap_default_process_loss_ngn",
		])
		.then((r) => {
			const msg = (r && r.message) || {};
			const capacity = flt(msg.scrap_default_container_capacity_kg) || 20000;
			const processLoss = flt(msg.scrap_default_process_loss_ngn);
			if (!flt(frm.doc.container_capacity_kg)) {
				frm.set_value("container_capacity_kg", capacity);
			}
			if (frm.doc.process_loss_contingency_ngn == null || frm.doc.process_loss_contingency_ngn === "") {
				frm.set_value("process_loss_contingency_ngn", processLoss || 3000000);
			}
			recalculate(frm);
		});
}

function recalculate(frm) {
	frappe.db
		.get_single_value("Pufm Manufacturing Settings", "scrap_default_container_capacity_kg")
		.then((defaultCapacity) => {
			const capacity = flt(frm.doc.container_capacity_kg) || flt(defaultCapacity) || 20000;
			const total =
				flt(frm.doc.shipping_cost_ngn) +
				flt(frm.doc.local_logistics_ngn) +
				flt(frm.doc.process_loss_contingency_ngn);
			frm.set_value("calculated_cost_per_kg", capacity ? total / capacity : 0);
		});
}
