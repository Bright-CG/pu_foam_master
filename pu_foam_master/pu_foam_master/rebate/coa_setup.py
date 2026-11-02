# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

"""Chart of Accounts helper for rebate wallet receivable (separate from trade debtors)."""

from __future__ import annotations

import frappe
from frappe import _

# Recommended naming for live + local (adjust account number to fit your CoA series).
REBATE_WALLET_ACCOUNT_NUMBER = "200-18"
REBATE_WALLET_ACCOUNT_NAME = "Rebate Wallet Receivable"


def ensure_rebate_wallet_receivable_account(company=None):
	"""
	Create ``Rebate Wallet Receivable`` under the same parent as the company default
	receivable, if it does not exist.

	Run:
	  bench --site <site> execute pu_foam_master.rebate.coa_setup.ensure_rebate_wallet_receivable_account
	"""
	company = company or frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)
	if not company:
		frappe.throw(_("Set a default Company or pass company=..."))

	trade_receivable = frappe.db.get_value("Company", company, "default_receivable_account")
	if not trade_receivable:
		frappe.throw(
			_("Company {0} has no Default Receivable Account. Set it on the Company record first.").format(
				company
			)
		)

	existing = frappe.db.get_value(
		"Account",
		{
			"company": company,
			"account_name": ("like", f"%{REBATE_WALLET_ACCOUNT_NAME}%"),
			"is_group": 0,
		},
		"name",
	)
	if existing:
		print(f"[coa_setup] Rebate wallet account already exists: {existing}")
		return existing

	parent = frappe.db.get_value("Account", trade_receivable, "parent_account")
	if not parent:
		frappe.throw(
			_("Could not find parent account for default receivable {0}.").format(trade_receivable)
		)

	doc = frappe.get_doc(
		{
			"doctype": "Account",
			"account_name": REBATE_WALLET_ACCOUNT_NAME,
			"account_number": REBATE_WALLET_ACCOUNT_NUMBER,
			"company": company,
			"parent_account": parent,
			"account_type": "Receivable",
			"root_type": "Asset",
			"report_type": "Balance Sheet",
			"is_group": 0,
		}
	)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	print(f"[coa_setup] Created rebate wallet receivable: {doc.name}")
	return doc.name


def print_customer_receivable_setup_steps(company=None):
	"""Print human-readable setup steps (also returned as string for execute)."""
	company = company or frappe.defaults.get_user_default("Company") or "Your Company"
	trade = frappe.db.get_value("Company", company, "default_receivable_account") if company else None
	rebate = None
	if company and frappe.db.exists("Company", company):
		rebate = frappe.db.get_value(
			"Account",
			{"company": company, "account_name": ("like", f"%{REBATE_WALLET_ACCOUNT_NAME}%")},
			"name",
		)

	lines = [
		"=== Rebate wallet receivable setup ===",
		f"Company: {company}",
		f"Trade receivable (default on Company): {trade or '(not set)'}",
		f"Rebate wallet receivable: {rebate or '(run ensure_rebate_wallet_receivable_account)'}",
		"",
		"1. Chart of Accounts → New Account (or run ensure_rebate_wallet_receivable_account).",
		f"   Name: {REBATE_WALLET_ACCOUNT_NUMBER} - {REBATE_WALLET_ACCOUNT_NAME} - <Company Abbr>",
		"   Parent: same group as Trade Debtors / default receivable",
		"   Account Type: Receivable | Root Type: Asset",
		"",
		"2. Main distributor Customer → Accounting tab → Accounts row:",
		"   Company = Solarfoam → Receivable = Trade Debtors (default receivable)",
		"",
		"3. Rebate wallet Customer → Accounting tab → Accounts row:",
		f"   Company = Solarfoam → Receivable = {REBATE_WALLET_ACCOUNT_NAME}",
		"",
		"4. Rebate Configuration: link main ↔ rebate on both Customer records.",
	]
	text = "\n".join(lines)
	print(text)
	return text
