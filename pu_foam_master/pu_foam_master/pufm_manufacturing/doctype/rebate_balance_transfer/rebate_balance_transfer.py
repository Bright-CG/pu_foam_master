# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, fmt_money

from pu_foam_master.pufm_manufacturing.utils.density_bom import get_preferred_company
from pu_foam_master.rebate.customer_links import (
	get_customer_receivable_account,
	get_linked_rebate_customer,
	get_rebate_wallet_credit_available,
	require_linked_rebate_customer,
)


class RebateBalanceTransfer(Document):
	def validate(self):
		if not self.company:
			self.company = get_preferred_company()
		if not self.company:
			frappe.throw(_("Company is required."))
		if flt(self.amount) <= 0:
			frappe.throw(_("Amount must be greater than zero."))

		expected_rebate = require_linked_rebate_customer(self.main_customer)
		if not self.rebate_customer:
			self.rebate_customer = expected_rebate
		elif self.rebate_customer != expected_rebate:
			frappe.throw(
				_(
					"Rebate wallet {0} does not match the link on main customer {1} ({2})."
				).format(self.rebate_customer, self.main_customer, expected_rebate)
			)

		main_recv = get_customer_receivable_account(self.main_customer, self.company)
		rebate_recv = get_customer_receivable_account(self.rebate_customer, self.company)
		if main_recv == rebate_recv:
			frappe.throw(
				_(
					"Main and rebate customers must use different receivable accounts in {0}. "
					"Configure separate Trade Debtors and Rebate Wallet accounts on each Customer."
				).format(self.company)
			)

		available = get_rebate_wallet_credit_available(
			self.rebate_customer, self.company, self.posting_date
		)
		if flt(self.amount) > available:
			frappe.throw(
				_(
					"Rebate wallet {0} has only {1} available credit on {2}; transfer amount is {3}."
				).format(
					self.rebate_customer,
					fmt_money(available),
					self.posting_date,
					fmt_money(flt(self.amount)),
				)
			)

	def on_submit(self):
		if self.journal_entry:
			return
		je_name = _create_rebate_transfer_journal(self)
		self.db_set("journal_entry", je_name, update_modified=False)

	def on_cancel(self):
		if not self.journal_entry:
			return
		je = frappe.get_doc("Journal Entry", self.journal_entry)
		if je.docstatus == 1:
			je.cancel()


@frappe.whitelist()
def get_rebate_customer_for_main(main_customer):
	if not main_customer:
		return {}
	rebate = get_linked_rebate_customer(main_customer)
	if not rebate:
		return {"rebate_customer": None}
	company = get_preferred_company()
	available = 0
	if company:
		available = get_rebate_wallet_credit_available(
			rebate, company, frappe.utils.today()
		)
	return {"rebate_customer": rebate, "available_credit": available}


def _create_rebate_transfer_journal(doc):
	"""Move rebate wallet credit to main trade receivable (Dr rebate, Cr main)."""
	amount = flt(doc.amount)
	main_account = get_customer_receivable_account(doc.main_customer, doc.company)
	rebate_account = get_customer_receivable_account(doc.rebate_customer, doc.company)

	je = frappe.new_doc("Journal Entry")
	je.voucher_type = "Journal Entry"
	je.company = doc.company
	je.posting_date = doc.posting_date
	je.user_remark = doc.remarks or _("Rebate balance transfer {0}").format(doc.name)

	je.append(
		"accounts",
		{
			"account": rebate_account,
			"party_type": "Customer",
			"party": doc.rebate_customer,
			"debit_in_account_currency": amount,
			"credit_in_account_currency": 0,
		},
	)
	je.append(
		"accounts",
		{
			"account": main_account,
			"party_type": "Customer",
			"party": doc.main_customer,
			"debit_in_account_currency": 0,
			"credit_in_account_currency": amount,
		},
	)

	je.insert(ignore_permissions=True)
	je.submit()
	return je.name
