# Copyright (c) 2026, PU Foam Master and contributors
# One-shot formula / settings checks for mattress PVC+tape and pour CBM basis.

import frappe
from frappe.utils import flt

from pu_foam_master.pufm_manufacturing.doctype.mattress_production_entry.mattress_production_entry import (
	_pvc_kg,
	_tape_edge_meters,
)
from pu_foam_master.pufm_manufacturing.utils.settings import (
	get_chemical_consumption_basis,
	get_usage_allowance_percent,
)


def run():
	settings = frappe.get_single("Pufm Manufacturing Settings")
	gsm = flt(settings.pvc_gsm) or 200.0
	# In-memory only for formula check (does not save)
	settings.pvc_gsm = gsm
	if flt(settings.tape_edge_usage_allowance) <= 0:
		settings.tape_edge_usage_allowance = 25
	if flt(settings.pvc_usage_allowance) <= 0:
		settings.pvc_usage_allowance = 25

	length, width, height = 72.0, 54.0, 8.0
	inches_per_m = flt(settings.inches_per_meter) or 39.37
	multiplier = flt(settings.tape_edge_perimeter_multiplier) or 4.0
	tape_allow = get_usage_allowance_percent("tape_edge_usage_allowance", settings)
	pvc_allow = get_usage_allowance_percent("pvc_usage_allowance", settings)

	tape = _tape_edge_meters(length, width, 1, settings)
	tape_exp = (multiplier * (length + width) / inches_per_m) * (1 + tape_allow / 100.0)

	pvc = _pvc_kg(length, width, height, 1, settings)
	wrap_w_m = (2.0 * (width + height)) / inches_per_m
	wrap_l_m = (height + length) / inches_per_m
	pvc_exp = (wrap_w_m * wrap_l_m * gsm / 1000.0) * (1 + pvc_allow / 100.0)

	pvc_item = settings.default_pvc_nylon_item
	pvc_uom = frappe.db.get_value("Item", pvc_item, "stock_uom") if pvc_item else None

	result = {
		"tape_ok": abs(tape - tape_exp) < 1e-6,
		"tape_meters": flt(tape, 6),
		"tape_expected": flt(tape_exp, 6),
		"pvc_ok": abs(pvc - pvc_exp) < 1e-6,
		"pvc_kg": flt(pvc, 6),
		"pvc_expected": flt(pvc_exp, 6),
		"gsm_used": gsm,
		"tape_allowance_pct": tape_allow,
		"pvc_allowance_pct": pvc_allow,
		"chemical_consumption_basis": get_chemical_consumption_basis(settings),
		"pvc_item": pvc_item,
		"pvc_stock_uom": pvc_uom,
		"settings_fields_present": all(
			hasattr(settings, f)
			for f in (
				"tape_edge_usage_allowance",
				"pvc_usage_allowance",
				"pvc_gsm",
				"chemical_consumption_basis",
			)
		),
	}
	if not result["tape_ok"] or not result["pvc_ok"] or pvc_uom != "Kg":
		frappe.throw("Verification failed: {0}".format(result))

	# Chemical CBM basis switch (in-memory)
	settings.chemical_consumption_basis = "Actual CBM"
	assert get_chemical_consumption_basis(settings) == "Actual CBM"
	settings.chemical_consumption_basis = "Expected CBM"
	assert get_chemical_consumption_basis(settings) == "Expected CBM"
	settings.chemical_consumption_basis = ""
	assert get_chemical_consumption_basis(settings) == "Expected CBM"

	print(result)
	return result
