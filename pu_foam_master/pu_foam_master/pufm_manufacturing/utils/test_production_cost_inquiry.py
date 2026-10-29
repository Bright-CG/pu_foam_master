# Copyright (c) 2026, PU Foam Master and contributors

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from pu_foam_master.pufm_manufacturing.utils.production_cost_inquiry import (
	_line_amount,
	build_inquiry_rows,
)


class TestProductionCostInquiry(FrappeTestCase):
	def test_build_rows_prorates_shared_inputs(self):
		entry = frappe._dict(
			{
				"name": "SE-TEST-1",
				"posting_date": "2026-01-15",
				"purpose": "Repack",
				"items": [
					frappe._dict(
						item_code="BLOCK",
						qty=1,
						s_warehouse="WIP",
						basic_rate=1000,
						amount=1000,
					),
					frappe._dict(
						item_code="CORE-A",
						qty=1,
						t_warehouse="FG",
						basic_rate=600,
						amount=600,
					),
					frappe._dict(
						item_code="CORE-B",
						qty=1,
						t_warehouse="FG",
						basic_rate=400,
						amount=400,
					),
				],
				"additional_costs": [
					frappe._dict(description="Slicing", amount=100),
				],
			}
		)
		rows = build_inquiry_rows(entry, scrap_item="__scrap__")
		parents = [r for r in rows if r["indent"] == 0]
		self.assertEqual(len(parents), 2)
		self.assertEqual(flt(parents[0]["line_cost"]), 600)
		self.assertEqual(flt(parents[1]["line_cost"]), 400)
		for parent in parents:
			self.assertEqual(parent["integrity_flag"], "OK")

	def test_line_amount_prefers_amount_field(self):
		row = frappe._dict(qty=2, basic_rate=10, amount=25)
		self.assertEqual(_line_amount(row), 25)

	def test_multi_fg_integrity_ok_after_remainder(self):
		"""Large pour split across two blocks (share must not round to 5 dp)."""
		entry = frappe._dict(
			{
				"name": "SE-POUR-1",
				"posting_date": "2026-10-11",
				"purpose": "Repack",
				"items": [
					frappe._dict(
						item_code="CHEM",
						qty=1,
						s_warehouse="WIP",
						basic_rate=18657695.66,
						amount=18657695.66,
					),
					frappe._dict(
						item_code="D18-BLOCK",
						qty=18,
						t_warehouse="FG",
						basic_rate=423408.752,
						amount=7621357.53621,
					),
					frappe._dict(
						item_code="D40-BLOCK",
						qty=11,
						t_warehouse="FG",
						basic_rate=1003394.374,
						amount=11037338.12337,
					),
				],
				"additional_costs": [
					frappe._dict(description="Operating Costs for D18", amount=416.67),
					frappe._dict(description="Operating Costs for D40", amount=583.33),
				],
			}
		)
		rows = build_inquiry_rows(entry, scrap_item="__scrap__")
		for parent in [r for r in rows if r["indent"] == 0]:
			self.assertEqual(parent["integrity_flag"], "OK")
