import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from pu_foam_master.pufm_manufacturing.utils.settings import get_rebate_expense_account
from pu_foam_master.rebate.customer import get_customer_rebate_rate


class RebateSettlementTool(Document):
	def validate(self):
		if self.from_date and self.to_date and self.from_date > self.to_date:
			frappe.throw(_("From Date cannot be after To Date."))

	def on_submit(self):
		self._create_credit_notes()

	def on_cancel(self):
		for row in self.entries or []:
			if not row.credit_note:
				continue
			cn = frappe.get_doc("Sales Invoice", row.credit_note)
			if cn.docstatus == 1:
				cn.cancel()

	def _create_credit_notes(self):
		expense_account = get_rebate_expense_account()
		company = frappe.defaults.get_user_default("Company")

		for row in self.entries or []:
			if not row.customer or flt(row.final_rebate_amount) <= 0:
				continue
			if row.credit_note:
				continue

			receivable_account = _get_customer_receivable_account(row.customer, company)
			item_code = _get_settlement_item(company)

			cn = frappe.new_doc("Sales Invoice")
			cn.is_return = 1
			cn.customer = row.customer
			cn.company = company
			cn.posting_date = self.to_date
			cn.debit_to = receivable_account
			cn.update_stock = 0
			cn.set_posting_time = 1
			cn.remarks = _("Rebate settlement for {0} ({1})").format(row.customer, self.name)
			cn.append(
				"items",
				{
					"item_code": item_code,
					"qty": 1,
					"rate": flt(row.final_rebate_amount),
					"income_account": expense_account,
				},
			)
			cn.insert(ignore_permissions=True)
			cn.submit()
			row.db_set("credit_note", cn.name, update_modified=False)


@frappe.whitelist()
def get_customers(from_date, to_date, customer_group=None):
	get_rebate_expense_account()

	if not from_date or not to_date:
		frappe.throw(_("From Date and To Date are required."))

	conditions = [
		"si.docstatus = 1",
		"si.posting_date BETWEEN %(from_date)s AND %(to_date)s",
		"IFNULL(c.custom_is_distributor, 0) = 1",
		"IFNULL(si.custom_apply_instant_rebate, 0) = 0",
	]
	params = {"from_date": from_date, "to_date": to_date}
	if customer_group:
		conditions.append("c.customer_group = %(customer_group)s")
		params["customer_group"] = customer_group

	rows = frappe.db.sql(
		f"""
		SELECT
			si.customer AS customer,
			SUM(si.grand_total) AS total_turnover
		FROM `tabSales Invoice` si
		INNER JOIN `tabCustomer` c ON c.name = si.customer
		WHERE {' AND '.join(conditions)}
		GROUP BY si.customer
		HAVING SUM(si.grand_total) > 0
		ORDER BY si.customer
		""",
		params,
		as_dict=True,
	)

	results = []
	for row in rows:
		rebate_pct, freight_pct = get_customer_rebate_rate(row.customer)
		if rebate_pct <= 0 and freight_pct <= 0:
			continue

		turnover = flt(row.total_turnover)
		rebate_amount = turnover * rebate_pct / 100
		freight_amount = turnover * freight_pct / 100
		results.append(
			{
				"customer": row.customer,
				"total_turnover": turnover,
				"rebate_percentage": rebate_pct,
				"freight_rebate_percentage": freight_pct,
				"rebate_amount": rebate_amount,
				"freight_rebate_amount": freight_amount,
				"final_rebate_amount": rebate_amount + freight_amount,
			}
		)

	return results


def _get_settlement_item(company):
	item = frappe.db.get_value(
		"Item",
		{"is_stock_item": 0, "disabled": 0, "item_name": ("like", "%Rebate%")},
		"name",
	)
	if item:
		return item

	item = frappe.db.get_value(
		"Item",
		{"is_stock_item": 0, "disabled": 0},
		"name",
		order_by="creation asc",
	)
	if not item:
		frappe.throw(
			_(
				"Please create a non-stock Item (e.g. 'Rebate Settlement') for rebate credit notes."
			)
		)
	return item


def _get_customer_receivable_account(customer, company):
	customer_doc = frappe.get_cached_doc("Customer", customer)
	company = company or frappe.defaults.get_user_default("Company")
	for row in customer_doc.get("accounts") or []:
		if row.company == company and row.account:
			return row.account
	return frappe.get_cached_value("Company", company, "default_receivable_account")
