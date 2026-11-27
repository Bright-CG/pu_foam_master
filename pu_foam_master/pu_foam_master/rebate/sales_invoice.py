import frappe
from frappe import _
from frappe.utils import cint, flt

from pu_foam_master.pufm_manufacturing.utils.settings import (
	get_rebate_expense_account,
	get_sales_additional_discount_account,
)
from pu_foam_master.rebate.turnover import (
	INSTANT_REBATE_ROW_DESCRIPTION,
	get_sales_invoice_rebatable_base,
)


def apply_instant_rebate(doc, method=None):
	"""Instant rebate: ex-VAT base × % → ERPNext Additional Discount on Grand Total."""
	apply_instant_rebate_impl(doc, method)


def apply_instant_rebate_on_save(doc, method=None):
	"""Re-apply after ERPNext validate so discount/amount persist on the saved document."""
	if doc.get("custom_apply_instant_rebate") and not doc.get("custom_exclude_from_rebate"):
		apply_instant_rebate_impl(doc, method)


def apply_instant_rebate_impl(doc, method=None):
	_strip_instant_rebate_tax_rows(doc)

	if doc.get("custom_exclude_from_rebate") and doc.get("custom_apply_instant_rebate"):
		frappe.throw(
			_("Cannot apply Instant Rebate on a Non-Rebateable invoice. Choose one.")
		)

	if doc.get("custom_apply_instant_rebate"):
		_ensure_not_rebate_wallet_customer(doc)
		_ensure_discount_accounting_enabled()
		_reject_manual_additional_discount(doc)

	if doc.get("custom_exclude_from_rebate") or not doc.get("custom_apply_instant_rebate"):
		doc.custom_instant_rebate_amount = 0
		_apply_manual_additional_discount_account(doc)
		return

	base_amount = get_sales_invoice_rebatable_base(doc)
	amount = _instant_rebate_amount_from_base(doc, base_amount)
	doc.custom_instant_rebate_amount = amount

	if amount <= 0:
		_clear_instant_discount_fields(doc)
	else:
		_apply_instant_as_additional_discount(doc, amount)

	_recalculate_invoice_totals(doc)


def ensure_rebate_tax_row(doc, method=None):
	"""Submit safety net — re-apply discount path and strip legacy tax rows."""
	_strip_instant_rebate_tax_rows(doc)
	apply_instant_rebate(doc, method)
	if doc.get("custom_apply_instant_rebate"):
		_reject_manual_additional_discount(doc)


def _strip_instant_rebate_tax_rows(doc):
	rows = [row for row in (doc.taxes or []) if row.description != INSTANT_REBATE_ROW_DESCRIPTION]
	if len(rows) != len(doc.taxes or []):
		doc.set("taxes", rows)


def _ensure_not_rebate_wallet_customer(doc):
	if not doc.get("customer"):
		return
	if cint(frappe.db.get_value("Customer", doc.customer, "custom_is_rebate_account")):
		frappe.throw(
			_("Instant Rebate cannot be used for rebate wallet customer {0}. Use the main customer.").format(
				doc.customer
			)
		)


def _ensure_discount_accounting_enabled():
	if not cint(frappe.db.get_single_value("Selling Settings", "enable_discount_accounting")):
		frappe.throw(
			_(
				"Enable <b>Discount Accounting</b> in Selling Settings before using Instant Rebate "
				"(so the rebate posts to the rebate expense account)."
			)
		)


def _reject_manual_additional_discount(doc):
	"""Instant rebate and manual Additional Discount are mutually exclusive."""
	if not doc.get("custom_apply_instant_rebate"):
		return
	rebate_account = get_rebate_expense_account()
	account = (doc.get("additional_discount_account") or "").strip()
	amount = flt(doc.get("discount_amount"))
	pct = flt(doc.get("additional_discount_percentage"))
	instant = flt(doc.get("custom_instant_rebate_amount"))

	if pct > 0:
		frappe.throw(
			_("Clear Additional Discount percentage. Use either Instant Rebate or Additional Discount, not both.")
		)

	if amount > 0 and account and account != rebate_account:
		frappe.throw(
			_("Clear Additional Discount. Use either Instant Rebate or Additional Discount, not both.")
		)

	if amount > 0 and abs(amount - instant) > 0.01 and account != rebate_account:
		frappe.throw(
			_("Clear Additional Discount. Use either Instant Rebate or Additional Discount, not both.")
		)


def _apply_instant_as_additional_discount(doc, amount):
	doc.apply_discount_on = "Grand Total"
	doc.additional_discount_percentage = 0
	doc.discount_amount = amount
	doc.additional_discount_account = get_rebate_expense_account()


def _clear_instant_discount_fields(doc):
	rebate_account = ""
	try:
		rebate_account = get_rebate_expense_account()
	except Exception:
		pass
	if rebate_account and doc.get("additional_discount_account") == rebate_account:
		doc.discount_amount = 0
		doc.additional_discount_percentage = 0
		doc.additional_discount_account = None


def _instant_rebate_amount_from_base(doc, base_amount):
	return flt(base_amount * flt(doc.get("custom_instant_rebate_percentage")) / 100, 2)


def _recalculate_invoice_totals(doc):
	if hasattr(doc, "calculate_taxes_and_totals"):
		doc.calculate_taxes_and_totals()


def _has_manual_additional_discount(doc):
	return flt(doc.get("discount_amount")) > 0 or flt(doc.get("additional_discount_percentage")) > 0


def _apply_manual_additional_discount_account(doc):
	"""Staff additional discount → fixed discount account from PUFM Settings."""
	if doc.get("custom_apply_instant_rebate"):
		return
	if not _has_manual_additional_discount(doc):
		return
	if not cint(frappe.db.get_single_value("Selling Settings", "enable_discount_accounting")):
		frappe.throw(
			_(
				"Enable <b>Discount Accounting</b> in Selling Settings before using Additional Discount."
			)
		)
	if not doc.get("apply_discount_on"):
		doc.apply_discount_on = "Grand Total"
	account = (doc.get("additional_discount_account") or "").strip()
	sales_discount_ac = get_sales_additional_discount_account()
	rebate_ac = get_rebate_expense_account()
	if account and account == rebate_ac:
		frappe.throw(
			_(
				"Rebate Expense Account is for Instant Rebate only. "
				"Clear Additional Discount or turn off Instant Rebate."
			)
		)
	if not account or account != sales_discount_ac:
		doc.additional_discount_account = sales_discount_ac


@frappe.whitelist()
def compute_instant_rebate_amount(
	net_total,
	custom_instant_rebate_percentage=0,
	custom_apply_instant_rebate=0,
	custom_exclude_from_rebate=0,
	discount_amount=0,
	total=None,
	taxes=None,
):
	"""Same calculation as validate — keeps the form in sync before save."""
	doc = frappe._dict(
		net_total=net_total,
		total=total if total is not None else net_total,
		discount_amount=discount_amount,
		taxes=frappe.parse_json(taxes) if isinstance(taxes, str) else (taxes or []),
		custom_apply_instant_rebate=cint(custom_apply_instant_rebate),
		custom_exclude_from_rebate=cint(custom_exclude_from_rebate),
		custom_instant_rebate_percentage=custom_instant_rebate_percentage,
	)
	if (
		not doc.custom_apply_instant_rebate
		or doc.custom_exclude_from_rebate
		or flt(doc.custom_instant_rebate_percentage) <= 0
	):
		return {"rebatable_base": 0, "amount": 0}
	base = get_sales_invoice_rebatable_base(doc)
	amount = _instant_rebate_amount_from_base(doc, base)
	return {"rebatable_base": base, "amount": amount}


@frappe.whitelist()
def get_instant_rebate_discount_defaults():
	return get_pufm_sales_invoice_discount_accounts()


@frappe.whitelist()
def get_pufm_sales_invoice_discount_accounts():
	"""Client: locked discount accounts for Sales Invoice."""
	out = {
		"apply_discount_on": "Grand Total",
		"enable_discount_accounting": cint(
			frappe.db.get_single_value("Selling Settings", "enable_discount_accounting")
		),
	}
	rebate = frappe.db.get_single_value("Pufm Manufacturing Settings", "rebate_expense_account")
	if rebate:
		out["rebate_expense_account"] = rebate
	sales_discount = frappe.db.get_single_value(
		"Pufm Manufacturing Settings", "sales_additional_discount_account"
	)
	if sales_discount:
		out["sales_additional_discount_account"] = sales_discount
	return out