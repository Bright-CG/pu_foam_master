# Copyright (c) 2026, Bright and Contributors
# See license.txt

from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

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