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

	def test_vat_tax_row_uses_qty_times_rate(self):
		"""A real VAT row means qty × rate is already ex-VAT. Discounted net is ignored."""
		doc = frappe._dict(
			net_total=534803.37,
			total=578408.11,
			discount_amount=53502.57,
			taxes=[frappe._dict(description="VAT", add_deduct_tax="Add", tax_amount=40000, rate=7.5)],
			custom_apply_instant_rebate=1,
			items=[frappe._dict(qty=1, rate=578408.11, amount=578408.11, net_amount=534803.37)],
		)
		base = get_sales_invoice_rebatable_base(doc)
		self.assertEqual(flt(base, 2), flt(578408.11, 2))

	def test_discounted_net_does_not_change_rebate(self):
		"""The saved screenshot case: 10% of ex-VAT qty × rate stays 53,502.75 after net shrinks."""
		rate = 578408.11
		doc = frappe._dict(
			net_total=524905.36,
			total=rate,
			discount_amount=53502.75,
			taxes=[],
			custom_apply_instant_rebate=1,
			custom_instant_rebate_percentage=10,
			items=[frappe._dict(qty=1, rate=rate, amount=rate, net_amount=524905.36)],
		)
		base = get_sales_invoice_rebatable_base(doc)
		self.assertEqual(flt(base, 2), flt(rate - rate * 7.5 / 100, 2))
		from pu_foam_master.rebate.sales_invoice import _expected_instant_rebate_amount

		self.assertEqual(_expected_instant_rebate_amount(doc), 53502.75)

	def test_total_greater_than_net_still_strips_vat_without_tax_rows(self):
		"""Total > Net after the rebate discount is not proof that net is already ex-VAT."""
		rate = 578408.11
		doc = frappe._dict(
			net_total=524905.36,
			total=rate,
			discount_amount=53502.75,
			taxes=[],
			custom_apply_instant_rebate=1,
			items=[frappe._dict(qty=1, rate=rate, amount=rate, net_amount=524905.36)],
		)
		base = get_sales_invoice_rebatable_base(doc)
		self.assertEqual(flt(base, 2), flt(rate - rate * 7.5 / 100, 2))

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