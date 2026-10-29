# Copyright (c) 2026, PU Foam Master and contributors

import frappe
from frappe.tests.utils import FrappeTestCase

from pu_foam_master.selling.bulk_invoice_lines import search_items_for_bulk_invoice


class TestBulkInvoiceLines(FrappeTestCase):
	def test_search_requires_item_group(self):
		with self.assertRaises(frappe.ValidationError):
			search_items_for_bulk_invoice("")

	def test_search_returns_list_for_products(self):
		group = frappe.db.get_value("Item", {"disabled": 0}, "item_group")
		if not group:
			self.skipTest("No items in database")
		rows = search_items_for_bulk_invoice(group, txt="", limit=5)
		self.assertIsInstance(rows, list)
		if rows:
			self.assertIn("item_code", rows[0])
			self.assertIn("details", rows[0])
