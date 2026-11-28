"""Rebatable turnover (ex-VAT) for instant rebate and period settlement."""

from collections import defaultdict

import frappe
from frappe.utils import cint, flt

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


def sales_invoice_items_net_total(doc):
	"""Sum item net amounts — stable before instant rebate additional discount."""
	total = 0.0
	for row in doc.get("items") or []:
		val = flt(row.get("net_amount"))
		if not val:
			val = flt(row.get("amount"))
		total += val
	return total


def selling_amount_is_vat_exclusive(doc, taxes=None):
	"""Net is already ex-VAT: explicit tax rows and/or Total > Net (VAT in item rates)."""
	taxes = taxes if taxes is not None else (doc.get("taxes") if doc else None)
	if invoice_has_erpnext_vat_taxes(taxes):
		return True
	if not doc:
		return False
	net = sales_invoice_items_net_total(doc) or flt(doc.get("net_total"))
	total = flt(doc.get("total"))
	return total > net + 0.01


def sales_invoice_gross_amount(doc):
	"""Selling amount before instant rebate (ex-VAT logic uses this as gross)."""
	if doc.get("custom_apply_instant_rebate"):
		items_net = sales_invoice_items_net_total(doc)
		if items_net > 0:
			return items_net
		gross = flt(doc.get("net_total"))
		return _gross_before_instant_additional_discount(doc, gross)
	return flt(doc.get("net_total")) - flt(doc.get("discount_amount"))


def _gross_before_instant_additional_discount(doc, gross):
	"""Restore selling net if header net_total already reflects instant rebate discount."""
	disc = flt(doc.get("discount_amount"))
	if disc <= 0:
		return gross
	rebate_ac = frappe.db.get_single_value("Pufm Manufacturing Settings", "rebate_expense_account")
	account = (doc.get("additional_discount_account") or "").strip()
	if not rebate_ac or account != rebate_ac:
		return gross
	# Circular save: net_total ≈ total − instant rebate; restore pre-rebate selling net
	inv_total = flt(doc.get("total"))
	if inv_total > 0 and abs(flt(doc.get("net_total")) + disc - inv_total) < 0.02:
		return inv_total
	if gross + disc > flt(doc.get("net_total")) + 0.01:
		return gross + disc
	return gross


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


def item_selling_gross(doc):
	"""Sum of qty × rate. Falls back to row amount when rate is not on the row yet."""
	total = 0.0
	found = False
	for row in doc.get("items") or []:
		gross = flt(row.get("qty")) * flt(row.get("rate"))
		if gross <= 0:
			gross = flt(row.get("amount"))
		if gross:
			found = True
			total += gross
	return total if found else 0.0


def rebatable_base_excluding_vat_unless_taxed(gross, taxes=None):
	"""Ex-VAT base from selling gross. Strip settings VAT only when no real VAT tax row exists."""
	gross = flt(gross)
	if gross <= 0:
		return 0.0
	if invoice_has_erpnext_vat_taxes(taxes):
		return gross
	rate = get_default_vat_rate()
	if rate <= 0:
		return gross
	return gross - gross * rate / 100.0


def get_sales_invoice_rebatable_base(doc):
	"""Instant rebate uses qty × rate and ignores net_amount after the rebate discount is spread."""
	if cint(doc.get("custom_apply_instant_rebate")) and not cint(doc.get("custom_exclude_from_rebate")):
		gross = item_selling_gross(doc)
		if gross <= 0:
			gross = flt(doc.get("total")) or flt(doc.get("net_total"))
		return rebatable_base_excluding_vat_unless_taxed(gross, doc.get("taxes"))
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
