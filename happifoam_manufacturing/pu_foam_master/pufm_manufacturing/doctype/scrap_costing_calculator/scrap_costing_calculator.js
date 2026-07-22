frappe.ui.form.on("Scrap Costing Calculator", {
	shipping_cost_ngn(frm) {
		recalculate(frm);
	},
	local_logistics_ngn(frm) {
		recalculate(frm);
	},
	process_loss_contingency_ngn(frm) {
		recalculate(frm);
	},
});

function recalculate(frm) {
	const capacity = flt(frm.doc.container_capacity_kg) || 20000;
	const total =
		flt(frm.doc.shipping_cost_ngn) +
		flt(frm.doc.local_logistics_ngn) +
		flt(frm.doc.process_loss_contingency_ngn);
	frm.set_value("calculated_cost_per_kg", capacity ? total / capacity : 0);
}
