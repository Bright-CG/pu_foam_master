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


def prepare_instant_rebate_before_validate(doc, method=None):
	"""Set the rebate from qty × rate before ERPNext spreads Additional Discount into item net."""
	_strip_instant_rebate_tax_rows(doc)

	if doc.get("custom_exclude_from_rebate") and doc.get("custom_apply_instant_rebate"):
		frappe.throw(
			_("Cannot apply Instant Rebate on a Non-Rebateable invoice. Choose one.")
		)

	if doc.get("custom_exclude_from_rebate") or not doc.get("custom_apply_instant_rebate"):
		doc.custom_instant_rebate_amount = 0
		_clear_instant_discount_fields(doc)
		return

	_ensure_not_rebate_wallet_customer(doc)
	_ensure_discount_accounting_enabled()
	_reject_foreign_additional_discount(doc)

	amount = _expected_instant_rebate_amount(doc)
	doc.custom_instant_rebate_amount = amount
	if amount <= 0:
		_clear_instant_discount_fields(doc)
		return
	_apply_instant_as_additional_discount(doc, amount)


def validate_sales_invoice_rebate(doc, method=None):
	"""After ERPNext totals: reject a manual discount mixed with instant rebate."""
	_strip_instant_rebate_tax_rows(doc)

	if doc.get("custom_exclude_from_rebate") and doc.get("custom_apply_instant_rebate"):
		frappe.throw(
			_("Cannot apply Instant Rebate on a Non-Rebateable invoice. Choose one.")
		)

	if doc.get("custom_apply_instant_rebate"):
		_ensure_not_rebate_wallet_customer(doc)
		_ensure_discount_accounting_enabled()
		_reject_foreign_additional_discount(doc)
		return

	doc.custom_instant_rebate_amount = 0
	_apply_manual_additional_discount_account(doc)


def assert_instant_rebate_after_totals(doc, method=None):
	"""Save and submit must keep the qty × rate rebate. Do not recompute from discounted net."""
	_strip_instant_rebate_tax_rows(doc)
	if doc.get("custom_exclude_from_rebate") or not doc.get("custom_apply_instant_rebate"):
		return

	expected = _expected_instant_rebate_amount(doc)
	custom_amount = flt(doc.get("custom_instant_rebate_amount"), 2)
	discount_amount = flt(doc.get("discount_amount"), 2)
	if abs(custom_amount - expected) > 0.01 or abs(discount_amount - expected) > 0.01:
		frappe.throw(
			_(
				"Instant Rebate Amount must stay {0} based on item quantity × rate. "
				"It was {1} on the rebate field and {2} on Additional Discount. Save again after the items settle, "
				"or clear Additional Discount and leave Instant Rebate in control."
			).format(expected, custom_amount, discount_amount)
		)
	if flt(doc.get("additional_discount_percentage")) > 0:
		frappe.throw(
			_("Clear Additional Discount percentage. Use either Instant Rebate or Additional Discount, not both.")
		)
	rebate_account = get_rebate_expense_account()
	if (doc.get("additional_discount_account") or "").strip() != rebate_account:
		frappe.throw(
			_("Instant Rebate must post to the Rebate Expense Account on Additional Discount.")
		)


def apply_instant_rebate_on_save(doc, method=None):
	"""Backward-compatible name. Asserts only — does not recalculate totals."""
	assert_instant_rebate_after_totals(doc, method)


def apply_instant_rebate(doc, method=None):
	prepare_instant_rebate_before_validate(doc, method)


def apply_instant_rebate_impl(doc, method=None):
	prepare_instant_rebate_before_validate(doc, method)


def ensure_rebate_tax_row(doc, method=None):
	assert_instant_rebate_after_totals(doc, method)


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


def _expected_instant_rebate_amount(doc):
	return _instant_rebate_amount_from_base(doc, get_sales_invoice_rebatable_base(doc))


def _reject_foreign_additional_discount(doc):
	"""A manual Additional Discount cannot share the invoice with Instant Rebate.

	A discount already posted to the rebate expense account is this feature's own row
	and is replaced with the qty × rate amount.
	"""
	if not doc.get("custom_apply_instant_rebate"):
		return
	rebate_account = get_rebate_expense_account()
	account = (doc.get("additional_discount_account") or "").strip()
	amount = flt(doc.get("discount_amount"))
	pct = flt(doc.get("additional_discount_percentage"))

	if pct > 0:
		frappe.throw(
			_("Clear Additional Discount percentage. Use either Instant Rebate or Additional Discount, not both.")
		)

	if amount > 0 and account != rebate_account:
		frappe.throw(
			_("Clear Additional Discount. Use either Instant Rebate or Additional Discount, not both.")
		)


def _reject_manual_additional_discount(doc):
	_reject_foreign_additional_discount(doc)


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
	items=None,
):
	"""Same calculation as before_save — keeps the form in sync before save."""
	doc = frappe._dict(
		net_total=net_total,
		total=total if total is not None else net_total,
		discount_amount=discount_amount,
		taxes=frappe.parse_json(taxes) if isinstance(taxes, str) else (taxes or []),
		items=frappe.parse_json(items) if isinstance(items, str) else (items or []),
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