"""Rebatable turnover (ex-VAT) for instant rebate and period settlement."""

from collections import defaultdict

import frappe
from frappe.utils import flt

from pu_foam_master.pufm_manufacturing.utils.settings import get_default_vat_rate

INSTANT_REBATE_ROW_DESCRIPTION = "Instant Rebate"


def invoice_has_erpnext_vat_taxes(taxes):
	"""True when the invoice has charge tax rows other than Instant Rebate."""
	for row in taxes or []:
		description = row.get("description") if isinstance(row, dict) else getattr(row, "description", None)
		if description == INSTANT_REBATE_ROW_DESCRIPTION:
			continue
		add_deduct = row.get("add_deduct_tax") if isinstance(row, dict) else getattr(row, "add_deduct_tax", None)
		if add_deduct == "Deduct":
			continue
		tax_amount = row.get("tax_amount") if isinstance(row, dict) else getattr(row, "tax_amount", None)
		if flt(tax_amount) > 0:
			return True
	return False


def sales_invoice_gross_amount(doc):
	return flt(doc.get("net_total")) - flt(doc.get("discount_amount"))


def rebatable_base_from_values(net_total, discount_amount=0, taxes=None):
	"""Rebatable base: net minus discount, minus VAT % of that amount (PUFM Settings)."""
	gross = flt(net_total) - flt(discount_amount)
	if gross <= 0:
		return 0.0
	if invoice_has_erpnext_vat_taxes(taxes):
		return gross
	rate = get_default_vat_rate()
	if rate <= 0:
		return gross
	return gross - gross * rate / 100.0


def get_sales_invoice_rebatable_base(doc):
	return rebatable_base_from_values(
		doc.get("net_total"),
		doc.get("discount_amount"),
		doc.get("taxes"),
	)


def aggregate_rebatable_turnover_by_customer(invoice_rows, taxes_by_invoice):
	"""Sum ex-VAT turnover per customer from lightweight invoice dicts."""
	turnover_by_customer = defaultdict(float)
	for row in invoice_rows:
		customer = row.get("customer")
		if not customer:
			continue
		name = row.get("name")
		taxes = taxes_by_invoice.get(name, []) if name else []
		turnover_by_customer[customer] += rebatable_base_from_values(
			row.get("net_total"),
			row.get("discount_amount"),
			taxes,
		)
	return dict(turnover_by_customer)


def fetch_taxes_for_sales_invoices(invoice_names):
	if not invoice_names:
		return {}
	tax_rows = frappe.db.sql(
		"""
		SELECT parent, description, tax_amount, add_deduct_tax
		FROM `tabSales Taxes and Charges`
		WHERE parenttype = 'Sales Invoice'
			AND parent IN %(parents)s
		""",
		{"parents": tuple(invoice_names)},
		as_dict=True,
	)
	taxes_by_invoice = defaultdict(list)
	for row in tax_rows:
		taxes_by_invoice[row.parent].append(row)
	return dict(taxes_by_invoice)
