# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import flt


class PufmPriceEngine(Document):
	def autoname(self):
		self.name = make_autoname(self.naming_series or "PRICE-.YYYY.-.####")

	def validate(self):
		if not self.item_code:
			frappe.throw(_("Item Code is required."))
		if not self.price_list:
			frappe.throw(_("Price List is required."))
		self.current_cost = _get_item_current_cost(self.item_code)
		self._recalculate()

	def on_submit(self):
		self._recalculate()
		if flt(self.proposed_selling_price) <= 0:
			frappe.throw(_("Proposed Selling Price must be greater than zero before submit."))
		self._upsert_item_price()

	def _recalculate(self):
		total = (
			flt(self.freight_percent)
			+ flt(self.advert_percent)
			+ flt(self.vat_percent)
			+ flt(self.rebate_percent)
			+ flt(self.profit_margin_percent)
		)
		if total >= 100:
			frappe.throw(_("Margin cannot be 100% or greater"))

		self.total_deduction_percent = flt(total, 2)
		cost = flt(self.current_cost)
		if cost <= 0:
			self.proposed_selling_price = 0
			self.gross_profit_amount = 0
			return

		denominator = 1 - (total / 100.0)
		self.proposed_selling_price = flt(cost / denominator, 2)
		self.gross_profit_amount = flt(self.proposed_selling_price - cost, 2)

	def _upsert_item_price(self):
		"""Push proposed_selling_price onto standard ERPNext Item Price."""
		existing = frappe.db.get_value(
			"Item Price",
			{
				"item_code": self.item_code,
				"price_list": self.price_list,
				"selling": 1,
			},
			"name",
		)
		# Also match buying-only lists if selling flag differs
		if not existing:
			existing = frappe.db.get_value(
				"Item Price",
				{"item_code": self.item_code, "price_list": self.price_list},
				"name",
			)

		rate = flt(self.proposed_selling_price)
		if existing:
			frappe.db.set_value("Item Price", existing, "price_list_rate", rate)
			return existing

		price_list_doc = frappe.get_cached_doc("Price List", self.price_list)
		item_price = frappe.get_doc(
			{
				"doctype": "Item Price",
				"item_code": self.item_code,
				"price_list": self.price_list,
				"price_list_rate": rate,
				"selling": 1 if getattr(price_list_doc, "selling", 0) else 0,
				"buying": 1 if getattr(price_list_doc, "buying", 0) else 0,
			}
		)
		# Ensure at least selling if neither flag is set on the price list
		if not item_price.selling and not item_price.buying:
			item_price.selling = 1
		item_price.insert(ignore_permissions=True)
		return item_price.name


def _get_item_current_cost(item_code):
	valuation = flt(frappe.db.get_value("Item", item_code, "valuation_rate"))
	if valuation > 0:
		return valuation
	# Prefer latest bin valuation if Item.valuation_rate is blank
	bin_rate = frappe.db.sql(
		"""
		SELECT valuation_rate
		FROM `tabBin`
		WHERE item_code = %s AND valuation_rate > 0
		ORDER BY modified DESC
		LIMIT 1
		""",
		(item_code,),
	)
	if bin_rate and flt(bin_rate[0][0]) > 0:
		return flt(bin_rate[0][0])
	return flt(frappe.db.get_value("Item", item_code, "standard_rate"))


@frappe.whitelist()
def get_item_current_cost(item_code):
	if not item_code:
		return 0
	return _get_item_current_cost(item_code)
