# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

"""Create Customer records with explicit IDs for PUFM Create Customer."""

from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.utils import cint

MAIN_ID_RE = re.compile(r"^[1-9]\d*$")
REBATE_ID_PREFIX = "REBATE"


def normalize_main_customer_id(value: str | None) -> str:
	text = (value or "").strip()
	if not MAIN_ID_RE.match(text):
		frappe.throw(
			_(
				"Main Customer ID must be a positive integer with no leading zeros (e.g. 330, 921)."
			)
		)
	return text


def rebate_id_for_main(main_id: str) -> str:
	return f"{REBATE_ID_PREFIX}{main_id}"


def validate_customer_id_available(customer_id: str, label: str | None = None):
	label = label or _("Customer ID")
	if frappe.db.exists("Customer", customer_id):
		frappe.throw(_("{0} {1} already exists.").format(label, customer_id))


def get_rebate_wallet_receivable_account():
	account = frappe.db.get_single_value(
		"Pufm Manufacturing Settings", "rebate_wallet_receivable_account"
	)
	if not account:
		frappe.throw(
			_(
				"Set <b>Rebate Wallet Receivable Account</b> on "
				"<a href='/app/pufm-manufacturing-settings'>Pufm Manufacturing Settings</a> "
				"before creating rebate wallet customers."
			)
		)
	account_type = frappe.db.get_value("Account", account, "account_type")
	if account_type != "Receivable":
		frappe.throw(
			_("Rebate Wallet Receivable Account {0} must be Account Type Receivable.").format(
				account
			)
		)
	return account


def get_trade_receivable_account(company: str) -> str:
	trade = frappe.db.get_value("Company", company, "default_receivable_account")
	if not trade:
		frappe.throw(
			_("Company {0} has no Default Receivable Account. Set it on the Company record.").format(
				company
			)
		)
	return trade


def insert_customer_with_id(customer_id: str, values: dict) -> str:
	"""Insert Customer with explicit ``name`` via ``insert(set_name=...)``."""
	doc = frappe.get_doc({"doctype": "Customer", **values})
	doc.flags.ignore_mandatory = True
	doc.insert(ignore_permissions=True, set_name=customer_id)
	if doc.name != customer_id:
		frappe.throw(
			_("ERPNext assigned Customer name {0} instead of {1}.").format(doc.name, customer_id)
		)
	return doc.name


def _append_party_account(customer_doc, company: str, account: str):
	customer_doc.append(
		"accounts",
		{"company": company, "account": account},
	)


def _default_customer_group(customer_group: str | None) -> str | None:
	if customer_group:
		return customer_group
	return frappe.db.get_single_value("Selling Settings", "customer_group")


def create_trade_customer(
	*,
	main_id: str,
	customer_name: str,
	company: str,
	customer_type: str | None = None,
	customer_group: str | None = None,
	is_distributor: bool = False,
	rebate_tier: str | None = None,
) -> str:
	values = {
		"customer_name": customer_name,
		"customer_type": customer_type or "Company",
		"customer_group": _default_customer_group(customer_group),
		"custom_is_distributor": 1 if is_distributor else 0,
	}
	if rebate_tier:
		values["custom_rebate_tier"] = rebate_tier
	trade = get_trade_receivable_account(company)
	doc = frappe.get_doc({"doctype": "Customer", **values})
	_append_party_account(doc, company, trade)
	doc.flags.ignore_mandatory = True
	# ERPNext Customer autoname follows Selling Settings; set_name bypasses that.
	doc.insert(ignore_permissions=True, set_name=main_id)
	if doc.name != main_id:
		frappe.throw(
			_("Could not create main Customer as ID {0} (saved as {1}).").format(main_id, doc.name)
		)
	return doc.name


def create_rebate_wallet_customer(
	*,
	rebate_id: str,
	rebate_customer_name: str,
	main_id: str,
	company: str,
	customer_type: str | None = None,
	customer_group: str | None = None,
) -> str:
	rebate_recv = get_rebate_wallet_receivable_account()
	trade = get_trade_receivable_account(company)
	if rebate_recv == trade:
		frappe.throw(
			_(
				"Rebate wallet receivable and company trade receivable must differ "
				"(check Settings and Company default receivable)."
			)
		)
	values = {
		"customer_name": rebate_customer_name,
		"customer_type": customer_type or "Company",
		"customer_group": _default_customer_group(customer_group),
		"custom_is_rebate_account": 1,
		"custom_is_distributor": 0,
		"custom_linked_main_customer": main_id,
	}
	doc = frappe.get_doc({"doctype": "Customer", **values})
	_append_party_account(doc, company, rebate_recv)
	doc.flags.ignore_mandatory = True
	doc.insert(ignore_permissions=True, set_name=rebate_id)
	if doc.name != rebate_id:
		frappe.throw(
			_("Could not create rebate Customer as ID {0} (saved as {1}).").format(
				rebate_id, doc.name
			)
		)
	return doc.name


def link_main_to_rebate(main_id: str, rebate_id: str):
	main = frappe.get_doc("Customer", main_id)
	main.custom_linked_rebate_customer = rebate_id
	main.flags.ignore_permissions = True
	main.save()


def sync_customer_naming_series_counter(main_id: str):
	"""Bump Customer naming-series counters when numeric IDs are assigned manually."""
	if not MAIN_ID_RE.match(main_id):
		return
	target = int(main_id)
	for row in frappe.db.sql(
		"""
		SELECT name, `current`
		FROM `tabSeries`
		WHERE name LIKE %s OR name LIKE %s
		""",
		("Customer%", "%Customer"),
		as_dict=True,
	):
		try:
			current = cint(row.current)
		except (TypeError, ValueError):
			continue
		if current < target:
			frappe.db.set_value("Series", row.name, "current", target, update_modified=False)


@frappe.whitelist()
def suggest_next_main_customer_id() -> int:
	"""Next unused positive integer ID (max numeric Customer name + 1)."""
	rows = frappe.db.sql(
		"""
		SELECT name FROM `tabCustomer`
		WHERE name REGEXP '^[1-9][0-9]*$'
		ORDER BY CAST(name AS UNSIGNED) DESC
		LIMIT 1
		"""
	)
	if rows:
		return int(rows[0][0]) + 1
	return 1


@frappe.whitelist()
def validate_customer_ids(main_customer_id, rebate_customer_id=None, include_rebate=0):
	include_rebate = cint(include_rebate)
	main_customer_id = normalize_main_customer_id(main_customer_id)
	validate_customer_id_available(main_customer_id, _("Main Customer ID"))
	if include_rebate:
		expected = rebate_id_for_main(main_customer_id)
		if rebate_customer_id and (rebate_customer_id or "").strip():
			rebate_customer_id = (rebate_customer_id or "").strip().upper()
			if rebate_customer_id != expected:
				frappe.throw(
					_("Rebate Customer ID must be {0} for main ID {1}.").format(
						expected, main_customer_id
					)
				)
		else:
			rebate_customer_id = expected
		if not rebate_customer_id.startswith(REBATE_ID_PREFIX):
			frappe.throw(_("Rebate Customer ID must start with {0}.").format(REBATE_ID_PREFIX))
		validate_customer_id_available(rebate_customer_id, _("Rebate Customer ID"))
	return {
		"main_customer_id": main_customer_id,
		"rebate_customer_id": rebate_customer_id if include_rebate else None,
	}