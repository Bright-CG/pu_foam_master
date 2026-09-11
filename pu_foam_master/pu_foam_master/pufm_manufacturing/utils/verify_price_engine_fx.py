# Copyright (c) 2026, PU Foam Master and contributors
"""Verify Price Engine dollar adjustment + selling price seeding."""

import frappe
from frappe.utils import flt

from pu_foam_master.pufm_manufacturing.doctype.pufm_price_engine.pufm_price_engine import (
	_dollar_adjustment_percents,
)


def run():
	# Example from product discussion: base 1500, current 1600, exposure 50%
	rate_adj, effective = _dollar_adjustment_percents(1500, 1600, 50)
	assert abs(rate_adj - ((1600 / 1500) - 1) * 100) < 1e-6
	assert abs(effective - rate_adj * 0.5) < 1e-6

	proposed = 120000.0
	adjusted = flt(proposed * (1 + effective / 100.0), 2)
	expected = flt(120000 * (1 + (((1600 / 1500) - 1) * 0.5)), 2)
	assert abs(adjusted - expected) < 0.02

	# No rates → no adjustment
	assert _dollar_adjustment_percents(0, 1600, 50) == (0.0, 0.0)
	assert _dollar_adjustment_percents(1500, 0, 50) == (0.0, 0.0)

	meta_parent = frappe.get_meta("Pufm Price Engine")
	meta_child = frappe.get_meta("Pufm Price Engine Item")
	for field in (
		"base_dollar_rate",
		"current_dollar_rate",
		"dollar_exposure_percent",
		"dollar_rate_adjustment_percent",
		"effective_price_adjustment_percent",
	):
		assert meta_parent.has_field(field), field
	for field in ("dollar_adjusted_price", "selling_price"):
		assert meta_child.has_field(field), field
	assert not meta_child.get_field("selling_price").read_only

	result = {
		"rate_adj_pct": flt(rate_adj, 4),
		"effective_pct": flt(effective, 4),
		"adjusted_price": adjusted,
		"expected_adjusted": expected,
		"ok": True,
	}
	print(result)
	return result
