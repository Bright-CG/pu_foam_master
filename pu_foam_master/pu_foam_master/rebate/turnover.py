"""Rebatable turnover (ex-VAT) for instant rebate and period settlement."""

from collections import defaultdict

import frappe
from frappe.utils import flt

from pu_foam_master.pufm_manufacturing.utils.settings import get_default_vat_rate

INSTANT_REBATE_ROW_DESCRIPTION = "Instant Rebate"


def invoice_has_erpnext_vat_taxes(taxes):
	"""True when the invoice has add-on VAT charge rows (rate or amount), excluding Instant Rebate."""
	for row in taxes or []:
		description = row.get("description") if isinstance(row, dict) else getattr(row, "description", None)
		if description == INSTANT_REBATE_ROW_DESCRIPTION:
			continue
		add_deduct = row.get("add_deduct_tax") if isinstance(row, dict) else getattr(row, "add_deduct_tax", None)
		if add_deduct == "Deduct":
			continue
		rate = row.get("rate") if isinstance(row, dict) else getattr(row, "rate", None)
		tax_amount = row.get("tax_amount") if isinstance(row, dict) else getattr(row, "tax_amount", None)
		if flt(rate) > 0 or flt(tax_amount) > 0:
			return True
	return False


def selling_amount_is_vat_exclusive(doc, taxes=None):
	"""Net is already ex-VAT: explicit tax rows and/or Total > Net (VAT in item rates)."""
	taxes = taxes if taxes is not None else (doc.get("taxes") if doc else None)
	if invoice_has_erpnext_vat_taxes(taxes):
		return True
	if not doc:
		return False
	net = flt(doc.get("net_total"))
	total = flt(doc.get("total"))
	return total > net + 0.01


def sales_invoice_gross_amount(doc):
	"""Selling amount before instant rebate (ex-VAT logic uses this as gross)."""
	if doc.get("custom_apply_instant_rebate"):
		return flt(doc.get("net_total"))
	return flt(doc.get("net_total")) - flt(doc.get("discount_amount"))


def rebatable_base_from_gross(gross, taxes=None, doc=None):
	"""Ex-VAT rebatable amount from pre-rebate selling gross (PUFM Settings VAT % if no tax rows)."""
	gross = flt(gross)
	if gross <= 0:
		return 0.0
	if selling_amount_is_vat_exclusive(doc, taxes):
		return gross
	rate = get_default_vat_rate()
	if rate <= 0:
		return gross
	return gross - gross * rate / 100.0


def rebatable_base_from_values(net_total, discount_amount=0, taxes=None, total=None):
	"""Rebatable base: net minus manual additional discount, then ex-VAT rules."""
	gross = flt(net_total) - flt(discount_amount)
	doc = frappe._dict(net_total=net_total, total=total if total is not None else net_total)
	return rebatable_base_from_gross(gross, taxes, doc)


def get_sales_invoice_rebatable_base(doc):
	"""Live invoice: use selling gross before instant rebate (not rebate additional discount)."""
	gross = sales_invoice_gross_amount(doc)
	return rebatable_base_from_gross(gross, doc.get("taxes"), doc)


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
