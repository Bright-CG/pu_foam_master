import frappe
from frappe import _
from frappe.utils import flt

from pu_foam_master.pufm_manufacturing.utils.settings import get_rebate_expense_account

INSTANT_REBATE_ROW_DESCRIPTION = "Instant Rebate"


def apply_instant_rebate(doc, method=None):
	if not doc.get("custom_apply_instant_rebate"):
		doc.custom_instant_rebate_amount = 0
		return

	base_amount = flt(doc.net_total) - flt(doc.discount_amount)
	doc.custom_instant_rebate_amount = base_amount * flt(doc.custom_instant_rebate_percentage) / 100


def ensure_rebate_tax_row(doc, method=None):
	existing = [
		row
		for row in (doc.taxes or [])
		if row.description != INSTANT_REBATE_ROW_DESCRIPTION
	]
	doc.set("taxes", existing)

	if not doc.get("custom_apply_instant_rebate"):
		return

	amount = flt(doc.custom_instant_rebate_amount)
	if amount <= 0:
		return

	account = get_rebate_expense_account()
	doc.append(
		"taxes",
		{
			"charge_type": "Actual",
			"account_head": account,
			"description": INSTANT_REBATE_ROW_DESCRIPTION,
			"tax_amount": -amount,
			"category": "Total",
			"add_deduct_tax": "Deduct",
			"included_in_print_rate": 0,
		},
	)


def _remove_instant_rebate_tax_rows(doc):
	pass
