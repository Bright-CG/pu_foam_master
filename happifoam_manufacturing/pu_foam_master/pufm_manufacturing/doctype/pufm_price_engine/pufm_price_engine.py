# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

"""Pufm Price Engine — visual price matrix with BOM material breakdown.

MD reviews proposed prices and BOM summaries in the child table before submit.
On submit, upserts ERPNext Item Price records from the reviewed matrix rows.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import cint, flt, getdate


class PufmPriceEngine(Document):
	def autoname(self):
		self.name = make_autoname(self.naming_series or "PUFM-PRC-.YYYY.-.MM.-.DD.-.####")

	def validate(self):
		if not self.item_group:
			frappe.throw(_("Item Group is required."))
		if not self.price_list:
			frappe.throw(_("Price List is required."))
		if not self.valid_from:
			frappe.throw(_("Valid From is required."))
		if self.valid_upto and getdate(self.valid_upto) < getdate(self.valid_from):
			frappe.throw(_("Valid Upto cannot be before Valid From."))
		if not self.items:
			frappe.throw(_("Fetch items and review the price matrix before saving."))

		total = self._total_deduction_percent()
		self.total_deduction_percent = flt(total, 2)
		self._recalculate_item_prices(total)

	def on_submit(self):
		total = self._total_deduction_percent()
		self.db_set("total_deduction_percent", flt(total, 2), update_modified=False)
		self._recalculate_item_prices(total)

		updated = 0
		skipped = 0
		for row in self.items:
			rate = flt(row.proposed_selling_price)
			if rate <= 0 or not row.item_code:
				skipped += 1
				continue
			_upsert_item_price(
				item_code=row.item_code,
				price_list=self.price_list,
				rate=rate,
				valid_from=self.valid_from,
				valid_upto=self.valid_upto,
			)
			updated += 1

		frappe.msgprint(
			_("Successfully updated prices for {0} items.").format(updated),
			indicator="green",
			title=_("Price Engine"),
		)
		if skipped:
			frappe.msgprint(
				_("Skipped {0} rows with missing item or zero proposed price.").format(skipped),
				indicator="orange",
			)

	def _total_deduction_percent(self):
		total = (
			flt(self.freight_percent)
			+ flt(self.advert_percent)
			+ flt(self.vat_percent)
			+ flt(self.rebate_percent)
			+ flt(self.profit_margin_percent)
		)
		if total >= 100:
			frappe.throw(_("Margin cannot be 100% or greater"))
		return total

	def _recalculate_item_prices(self, total_deduction=None):
		total = flt(total_deduction if total_deduction is not None else self._total_deduction_percent())
		denominator = 1 - (total / 100.0)
		if denominator <= 0:
			frappe.throw(_("Margin cannot be 100% or greater"))

		for row in self.items:
			cost = flt(row.current_cost)
			if cost <= 0:
				row.proposed_selling_price = 0
				row.gross_profit_amount = 0
				continue
			row.proposed_selling_price = flt(cost / denominator, 2)
			row.gross_profit_amount = flt(row.proposed_selling_price - cost, 2)


def _get_item_group_bounds(item_group):
	if not item_group:
		frappe.throw(_("Item Group is required."))
	if not frappe.db.exists("Item Group", item_group):
		frappe.throw(_("Item Group {0} does not exist.").format(item_group))
	root = frappe.db.get_value("Item Group", item_group, ["lft", "rgt"], as_dict=True)
	if not root:
		frappe.throw(_("Could not resolve Item Group tree for {0}.").format(item_group))
	return cint(root.lft), cint(root.rgt)


def _fetch_group_sales_items(item_group):
	lft, rgt = _get_item_group_bounds(item_group)
	return frappe.db.sql(
		"""
		SELECT
			item.name AS item_code,
			item.item_name,
			item.default_bom,
			item.valuation_rate,
			item.standard_rate
		FROM `tabItem` item
		INNER JOIN `tabItem Group` ig ON ig.name = item.item_group
		WHERE item.disabled = 0
			AND item.is_sales_item = 1
			AND ig.lft >= %(lft)s
			AND ig.rgt <= %(rgt)s
		ORDER BY item.name ASC
		""",
		{"lft": lft, "rgt": rgt},
		as_dict=True,
	)


def _resolve_bom(item_code, default_bom=None):
	if default_bom and frappe.db.exists("BOM", default_bom):
		is_active = cint(frappe.db.get_value("BOM", default_bom, "is_active"))
		if is_active:
			return default_bom

	return frappe.db.get_value(
		"BOM",
		{"item": item_code, "is_active": 1, "docstatus": 1},
		"name",
		order_by="modified desc",
	) or frappe.db.get_value(
		"BOM",
		{"item": item_code, "is_active": 1},
		"name",
		order_by="modified desc",
	)


def _build_material_breakdown(bom_name, limit=6):
	rows = frappe.db.sql(
		"""
		SELECT
			COALESCE(NULLIF(bi.item_name, ''), bi.item_code) AS material_name,
			bi.qty,
			bi.uom,
			bi.amount
		FROM `tabBOM Item` bi
		WHERE bi.parent = %s
		ORDER BY bi.amount DESC, bi.idx ASC
		""",
		(bom_name,),
		as_dict=True,
	)
	if not rows:
		return "No materials"

	parts = []
	for row in rows[:limit]:
		qty = flt(row.qty)
		qty_str = f"{qty:g}" if qty == int(qty) else f"{flt(qty, 2)}"
		uom = (row.uom or "").strip()
		parts.append(f"{row.material_name}: {qty_str}{uom}")
	return ", ".join(parts)


def _get_item_current_cost(item_code, valuation_rate=None, standard_rate=None):
	valuation = flt(valuation_rate)
	if valuation <= 0:
		valuation = flt(frappe.db.get_value("Item", item_code, "valuation_rate"))
	if valuation > 0:
		return valuation

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

	standard = flt(standard_rate)
	if standard <= 0:
		standard = flt(frappe.db.get_value("Item", item_code, "standard_rate"))
	return standard


def _upsert_item_price(item_code, price_list, rate, valid_from, valid_upto):
	existing = frappe.db.get_value(
		"Item Price",
		{"item_code": item_code, "price_list": price_list},
		"name",
	)
	if existing:
		frappe.db.set_value(
			"Item Price",
			existing,
			{
				"price_list_rate": rate,
				"valid_from": valid_from,
				"valid_upto": valid_upto,
			},
			update_modified=True,
		)
		return existing

	price_list_doc = frappe.get_cached_doc("Price List", price_list)
	item_price = frappe.get_doc(
		{
			"doctype": "Item Price",
			"item_code": item_code,
			"price_list": price_list,
			"price_list_rate": rate,
			"valid_from": valid_from,
			"valid_upto": valid_upto,
			"selling": 1 if getattr(price_list_doc, "selling", 0) else 0,
			"buying": 1 if getattr(price_list_doc, "buying", 0) else 0,
		}
	)
	if not item_price.selling and not item_price.buying:
		item_price.selling = 1
	item_price.insert(ignore_permissions=True)
	return item_price.name


@frappe.whitelist()
def fetch_item_matrix(item_group):
	"""Build the visual price matrix with BOM material breakdowns for an Item Group tree."""
	if not item_group:
		frappe.throw(_("Item Group is required."))

	matrix = []
	for item in _fetch_group_sales_items(item_group):
		bom_name = _resolve_bom(item.item_code, item.default_bom)
		if bom_name:
			bom_total = flt(frappe.db.get_value("BOM", bom_name, "total_cost"))
			matrix.append(
				{
					"item_code": item.item_code,
					"item_name": item.item_name,
					"bom_reference": bom_name,
					"material_breakdown": _build_material_breakdown(bom_name),
					"current_cost": flt(bom_total, 2),
					"proposed_selling_price": 0,
					"gross_profit_amount": 0,
				}
			)
		else:
			matrix.append(
				{
					"item_code": item.item_code,
					"item_name": item.item_name,
					"bom_reference": None,
					"material_breakdown": "No BOM Found",
					"current_cost": flt(
						_get_item_current_cost(
							item.item_code,
							valuation_rate=item.valuation_rate,
							standard_rate=item.standard_rate,
						),
						2,
					),
					"proposed_selling_price": 0,
					"gross_profit_amount": 0,
				}
			)
	return matrix
