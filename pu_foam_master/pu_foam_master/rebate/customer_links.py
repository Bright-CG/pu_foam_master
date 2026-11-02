# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

"""Main ↔ rebate Customer links and receivable account resolution."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, flt


def validate_customer_rebate_links(doc, method=None):
	"""Customer master validation for distributor / rebate wallet pairing."""
	is_rebate = cint(doc.get("custom_is_rebate_account"))
	is_distributor = cint(doc.get("custom_is_distributor"))
	main_link = doc.get("custom_linked_main_customer")
	rebate_link = doc.get("custom_linked_rebate_customer")

	if is_rebate and is_distributor:
		frappe.throw(_("A rebate wallet account cannot be marked as Is Distributor."))

	if is_rebate:
		doc.custom_is_distributor = 0
		if not main_link:
			frappe.throw(_("Rebate wallet accounts must have Linked Main Customer."))
		_validate_main_customer(main_link, doc.name)
		if rebate_link:
			frappe.throw(_("Rebate wallet accounts cannot have Linked Rebate Customer."))
		return

	if rebate_link:
		_validate_rebate_customer(rebate_link, doc.name)
		if main_link:
			frappe.throw(_("Only rebate wallet accounts should use Linked Main Customer."))

	if is_distributor and not is_rebate and not rebate_link:
		# Allowed at save time; settlement submit enforces link for posting.
		return


def _validate_main_customer(main_customer, rebate_customer_name):
	if not frappe.db.exists("Customer", main_customer):
		frappe.throw(_("Linked Main Customer {0} does not exist.").format(main_customer))
	if cint(frappe.db.get_value("Customer", main_customer, "custom_is_rebate_account")):
		frappe.throw(_("Linked Main Customer cannot be a rebate wallet account."))
	if cint(frappe.db.get_value("Customer", main_customer, "custom_is_distributor")) != 1:
		frappe.throw(
			_("Linked Main Customer {0} must be a distributor.").format(main_customer)
		)
	linked_back = frappe.db.get_value(
		"Customer", main_customer, "custom_linked_rebate_customer"
	)
	if linked_back and linked_back != rebate_customer_name:
		frappe.throw(
			_(
				"Main customer {0} is already linked to rebate account {1}. "
				"Update that link before pairing with {2}."
			).format(main_customer, linked_back, rebate_customer_name)
		)


def _validate_rebate_customer(rebate_customer, main_customer_name):
	if not frappe.db.exists("Customer", rebate_customer):
		frappe.throw(_("Linked Rebate Customer {0} does not exist.").format(rebate_customer))
	if cint(frappe.db.get_value("Customer", rebate_customer, "custom_is_rebate_account")) != 1:
		frappe.throw(
			_("Linked Rebate Customer {0} must be marked as Rebate Wallet Account.").format(
				rebate_customer
			)
		)
	linked_back = frappe.db.get_value(
		"Customer", rebate_customer, "custom_linked_main_customer"
	)
	if linked_back and linked_back != main_customer_name:
		frappe.throw(
			_(
				"Rebate account {0} is already linked to main customer {1}. "
				"Update that link before pairing with {2}."
			).format(rebate_customer, linked_back, main_customer_name)
		)


def get_linked_rebate_customer(main_customer):
	"""Return rebate Customer linked from a main distributor, or None."""
	if not main_customer:
		return None
	rebate = frappe.db.get_value("Customer", main_customer, "custom_linked_rebate_customer")
	if not rebate:
		return None
	if cint(frappe.db.get_value("Customer", rebate, "custom_is_rebate_account")) != 1:
		return None
	return rebate


def require_linked_rebate_customer(main_customer):
	rebate = get_linked_rebate_customer(main_customer)
	if not rebate:
		frappe.throw(
			_(
				"Customer {0} has no linked rebate wallet account. "
				"Set Linked Rebate Customer on the Customer master before rebate settlement."
			).format(main_customer),
			title=_("Missing Rebate Wallet Link"),
		)
	return rebate


def get_customer_receivable_account(customer, company):
	"""Company receivable from Customer Accounts row, else company default."""
	if not customer:
		frappe.throw(_("Customer is required to resolve receivable account."))
	if not company:
		frappe.throw(_("Company is required to resolve receivable account."))

	customer_doc = frappe.get_cached_doc("Customer", customer)
	for row in customer_doc.get("accounts") or []:
		if row.company == company and row.account:
			return row.account

	default = frappe.get_cached_value("Company", company, "default_receivable_account")
	if not default:
		frappe.throw(
			_("No receivable account for customer {0} in company {1}.").format(
				customer, company
			)
		)
	return default


def get_rebate_wallet_credit_available(rebate_customer, company, posting_date):
	"""
	Available rebate wallet credit (positive number) on the rebate party receivable.

	After settlement credit notes, rebate customers typically show a credit balance
	(negative receivable balance in ERPNext).
	"""
	account = get_customer_receivable_account(rebate_customer, company)
	from erpnext.accounts.utils import get_balance_on

	balance = flt(
		get_balance_on(
			account=account,
			date=posting_date,
			party_type="Customer",
			party=rebate_customer,
			company=company,
		)
	)
	if balance >= 0:
		return 0
	return flt(-balance)
