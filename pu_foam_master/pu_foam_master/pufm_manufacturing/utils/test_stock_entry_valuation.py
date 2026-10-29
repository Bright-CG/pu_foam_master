# Copyright (c) 2026, PU Foam Master and contributors

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from pu_foam_master.pufm_manufacturing.utils.stock_entry_valuation import (
	apply_manual_rate,
	finalize_pufm_stock_entry_balance,
	stock_entry_additional_amount,
	stock_entry_source_amount,
	stock_entry_target_amount,
	stock_entry_target_material_basic,
)


class TestStockEntryValuation(FrappeTestCase):
	def test_repack_overhead_stays_in_additional_costs_at_build(self):
		"""Material pool balanced at build; overhead not folded into FG basic."""
		entry = _blank_repack_entry()
		src = {"item_code": "BLOCK-1", "qty": 1, "s_warehouse": "Stores - T"}
		entry.append("items", src)
		apply_manual_rate(entry.items[0], 1_000_000)
		scrap = {"item_code": "SCRAP", "qty": 10, "t_warehouse": "WIP - T"}
		entry.append("items", scrap)
		apply_manual_rate(entry.items[1], 5_000)
		core = {"item_code": "CORE-1", "qty": 1, "t_warehouse": "WIP - T", "is_finished_item": 1}
		entry.append("items", core)
		apply_manual_rate(entry.items[2], 950_000)

		entry.append(
			"additional_costs",
			{
				"expense_account": "Conversion Overhead - T",
				"description": "Slicing",
				"amount": 50_000,
			},
		)

		finalize_pufm_stock_entry_balance(entry, scrap_item="SCRAP", context="test")
		sources = flt(stock_entry_source_amount(entry))
		target_basic = flt(stock_entry_target_material_basic(entry))
		self.assertAlmostEqual(sources, target_basic, places=2)
		self.assertAlmostEqual(sources, 1_000_000, places=2)
		# Overhead still only in the table until ERPNext submit distributes it.
		self.assertAlmostEqual(stock_entry_additional_amount(entry), 50_000, places=2)
		self.assertLess(
			stock_entry_target_amount(entry),
			sources + stock_entry_additional_amount(entry),
		)

	def test_sync_restores_outgoing_after_erpnext_zeros_source(self):
		"""Simulate validate wiping outgoing rate; sync must restore before balance check."""
		from pu_foam_master.pufm_manufacturing.utils.stock_entry_valuation import (
			reapply_pufm_outgoing_rates,
		)

		company = frappe.db.get_value("Company", {}, "name")
		if not company:
			self.skipTest("No company")
		entry = frappe.new_doc("Stock Entry")
		entry.company = company
		entry.stock_entry_type = "Repack"
		entry.purpose = "Repack"
		entry.posting_date = frappe.utils.today()
		entry.append(
			"items",
			{
				"item_code": frappe.db.get_value("Item", {"disabled": 0}, "name"),
				"qty": 1,
				"s_warehouse": frappe.db.get_value("Warehouse", {"company": company}, "name"),
				"set_basic_rate_manually": 1,
				"basic_rate": 100,
				"basic_amount": 100,
				"amount": 100,
			},
		)
		fg_item = frappe.db.get_value("Item", {"disabled": 0, "name": ["!=", entry.items[0].item_code]}, "name")
		if not fg_item:
			self.skipTest("Need two items")
		entry.append(
			"items",
			{
				"item_code": fg_item,
				"qty": 1,
				"t_warehouse": frappe.db.get_value("Warehouse", {"company": company}, "name"),
				"is_finished_item": 1,
				"set_basic_rate_manually": 1,
				"basic_rate": 100,
				"basic_amount": 100,
				"amount": 100,
			},
		)
		# ERPNext validate effect on outgoing
		entry.items[0].basic_rate = 0
		entry.items[0].basic_amount = 0
		entry.items[0].amount = 0
		reapply_pufm_outgoing_rates(entry)
		self.assertGreater(flt(entry.items[0].basic_rate), 0)


def _blank_repack_entry():
	entry = frappe.new_doc("Stock Entry")
	entry.stock_entry_type = "Repack"
	entry.purpose = "Repack"
	entry.company = "_Test Company"
	return entry

