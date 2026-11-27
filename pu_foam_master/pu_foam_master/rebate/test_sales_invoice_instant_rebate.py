# Copyright (c) 2026, Bright and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from pu_foam_master.rebate.sales_invoice import compute_instant_rebate_amount
from pu_foam_master.rebate.turnover import get_sales_invoice_rebatable_base


class TestSalesInvoiceInstantRebate(FrappeTestCase):
	def test_rebatable_base_ex_vat_without_tax_rows(self):
		doc = frappe._dict(
			net_total=98100,
			discount_amount=0,
			taxes=[],
			custom_apply_instant_rebate=1,
			custom_instant_rebate_percentage=10,
		)
		base = get_sales_invoice_rebatable_base(doc)
		self.assertEqual(flt(base, 2), flt(98100 - 98100 * 7.5 / 100, 2))

	def test_instant_rebate_ignores_additional_discount_on_base(self):
		"""Instant rebate additional discount must not reduce the rebatable base."""
		net_total = 534803.37
		instant_discount = 53502.57
		doc = frappe._dict(
			net_total=net_total,
			total=578408.11,
			discount_amount=instant_discount,
			taxes=[frappe._dict(description="VAT", add_deduct_tax="Add", tax_amount=40000)],
			custom_apply_instant_rebate=1,
			items=[frappe._dict(net_amount=net_total, amount=578408.11)],
		)
		base = get_sales_invoice_rebatable_base(doc)
		self.assertEqual(flt(base, 2), flt(net_total, 2))

	def test_items_net_stable_when_header_net_shrunk(self):
		"""After save, header net_total may shrink; item net is still the rebate base."""
		items_net = 534803.37
		doc = frappe._dict(
			net_total=525816.35,
			total=578408.11,
			discount_amount=52591.76,
			taxes=[],
			custom_apply_instant_rebate=1,
			items=[frappe._dict(net_amount=items_net, amount=578408.11)],
		)
		base = get_sales_invoice_rebatable_base(doc)
		self.assertEqual(flt(base, 2), flt(items_net, 2))
		self.assertEqual(flt(base * 0.1, 2), flt(53480.34, 2))

	def test_total_greater_than_net_skips_extra_vat_strip(self):
		"""Item rates VAT-inclusive: net is ex-VAT; do not strip default VAT % again."""
		doc = frappe._dict(
			net_total=534803.37,
			total=578408.11,
			discount_amount=0,
			taxes=[],
			custom_apply_instant_rebate=1,
		)
		base = get_sales_invoice_rebatable_base(doc)
		self.assertEqual(flt(base, 2), flt(534803.37, 2))

	def test_compute_instant_rebate_without_percentage(self):
		out = compute_instant_rebate_amount(
			578408.11,
			custom_apply_instant_rebate=1,
		)
		self.assertEqual(out["amount"], 0)

	def test_manual_additional_discount_reduces_base(self):
		doc = frappe._dict(
			net_total=100000,
			discount_amount=10000,
			taxes=[],
			custom_apply_instant_rebate=0,
		)
		base = get_sales_invoice_rebatable_base(doc)
		expected_gross = 90000 - 90000 * 7.5 / 100
		self.assertEqual(flt(base, 2), flt(expected_gross, 2))