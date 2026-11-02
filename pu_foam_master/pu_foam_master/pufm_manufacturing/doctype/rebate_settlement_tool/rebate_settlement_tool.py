import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

from pu_foam_master.pufm_manufacturing.utils.settings import get_rebate_expense_account
from pu_foam_master.rebate.customer import get_customer_rebate_rate
from pu_foam_master.rebate.customer_links import (
	get_customer_receivable_account,
	get_linked_rebate_customer,
	require_linked_rebate_customer,
)


class RebateSettlementTool(Document):
	def validate(self):
		if not self.company:
			from pu_foam_master.pufm_manufacturing.utils.density_bom import get_preferred_company

			self.company = get_preferred_company()
		if not self.company:
			frappe.throw(_("Company is required."))
		if self.from_date and self.to_date and self.from_date > self.to_date:
			frappe.throw(_("From Date cannot be after To Date."))
		self._sync_entry_rebate_customers()

	def before_submit(self):
		for row in self.entries or []:
			if not row.customer or flt(row.final_rebate_amount) <= 0:
				continue
			require_linked_rebate_customer(row.customer)
			rebate = get_linked_rebate_customer(row.customer)
			if row.rebate_customer and row.rebate_customer != rebate:
				frappe.throw(
					_("Row for {0}: rebate wallet mismatch. Refresh eligible customers.").format(
						row.customer
					)
				)
			row.rebate_customer = rebate

	def on_submit(self):
		self._create_credit_notes()
		self._mark_invoices_settled()

	def on_cancel(self):
		self._clear_invoice_settlement_marks()
		for row in self.entries or []:
			if not row.credit_note:
				continue
			cn = frappe.get_doc("Sales Invoice", row.credit_note)
			if cn.docstatus == 1:
				cn.cancel()

	def _sync_entry_rebate_customers(self):
		for row in self.entries or []:
			if not row.customer:
				row.rebate_customer = None
				continue
			row.rebate_customer = get_linked_rebate_customer(row.customer)

	def _create_credit_notes(self):
		expense_account = get_rebate_expense_account()
		company = self.company
		if not company:
			frappe.throw(_("Company is required on Rebate Settlement Tool."))

		for row in self.entries or []:
			if not row.customer or flt(row.final_rebate_amount) <= 0:
				continue
			if row.credit_note:
				continue

			rebate_customer = require_linked_rebate_customer(row.customer)
			receivable_account = get_customer_receivable_account(rebate_customer, company)
			trade_receivable = get_customer_receivable_account(row.customer, company)
			if receivable_account == trade_receivable:
				frappe.throw(
					_(
						"Customer <b>{0}</b> and rebate wallet <b>{1}</b> both use receivable account "
						"<b>{2}</b> for company {3}.<br><br>"
						"Create a separate <b>Rebate Wallet Receivable</b> account in Chart of Accounts "
						"(same parent as Trade Debtors), assign it on the rebate Customer → Accounting tab, "
						"and keep Trade Debtors on the main Customer.<br><br>"
						"Local helper: "
						"<code>bench --site &lt;site&gt; execute "
						"pu_foam_master.rebate.coa_setup.ensure_rebate_wallet_receivable_account</code>"
					).format(
						row.customer,
						rebate_customer,
						receivable_account,
						company,
					),
					title=_("Receivable accounts must differ"),
				)

			item_code = _get_settlement_item(company)

			cn = frappe.new_doc("Sales Invoice")
			cn.is_return = 1
			cn.customer = rebate_customer
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
					"qty": -1,
					"rate": flt(row.final_rebate_amount),
					"income_account": expense_account,
				},
			)
			cn.insert(ignore_permissions=True)
			cn.submit()
			row.db_set("credit_note", cn.name, update_modified=False)

	def _mark_invoices_settled(self):
		"""Tag period invoices so they cannot be settled twice."""
		if not frappe.db.has_column("Sales Invoice", "custom_rebate_settlement"):
			return

		customers = [row.customer for row in (self.entries or []) if row.customer]
		if not customers:
			return

		frappe.db.sql(
			"""
			UPDATE `tabSales Invoice` si
			SET si.custom_rebate_settlement = %s
			WHERE si.docstatus = 1
				AND IFNULL(si.is_return, 0) = 0
				AND IFNULL(si.custom_apply_instant_rebate, 0) = 0
				{exclude_non_rebateable}
				AND si.posting_date BETWEEN %s AND %s
				AND si.customer IN ({customers})
				AND IFNULL(si.custom_rebate_settlement, '') = ''
			""".format(
				exclude_non_rebateable=_non_rebateable_sql("si"),
				customers=", ".join(["%s"] * len(customers)),
			),
			tuple([self.name, self.from_date, self.to_date] + customers),
		)

	def _clear_invoice_settlement_marks(self):
		if not frappe.db.has_column("Sales Invoice", "custom_rebate_settlement"):
			return
		frappe.db.sql(
			"""
			UPDATE `tabSales Invoice`
			SET custom_rebate_settlement = ''
			WHERE custom_rebate_settlement = %s
			""",
			(self.name,),
		)


@frappe.whitelist()
def get_customers(from_date, to_date, customer_group=None):
	get_rebate_expense_account()

	if not from_date or not to_date:
		frappe.throw(_("From Date and To Date are required."))

	conditions = [
		"si.docstatus = 1",
		"IFNULL(si.is_return, 0) = 0",
		"si.posting_date BETWEEN %(from_date)s AND %(to_date)s",
		"IFNULL(c.custom_is_distributor, 0) = 1",
		"IFNULL(c.custom_is_rebate_account, 0) = 0",
		"IFNULL(si.custom_apply_instant_rebate, 0) = 0",
	]
	if frappe.db.has_column("Sales Invoice", "custom_exclude_from_rebate"):
		conditions.append("IFNULL(si.custom_exclude_from_rebate, 0) = 0")
	params = {"from_date": from_date, "to_date": to_date}

	if frappe.db.has_column("Sales Invoice", "custom_rebate_settlement"):
		conditions.append("IFNULL(si.custom_rebate_settlement, '') = ''")

	if customer_group:
		conditions.append("c.customer_group = %(customer_group)s")
		params["customer_group"] = customer_group

	rows = frappe.db.sql(
		f"""
		SELECT
			si.customer AS customer,
			SUM(si.net_total) AS rebatable_turnover
		FROM `tabSales Invoice` si
		INNER JOIN `tabCustomer` c ON c.name = si.customer
		WHERE {' AND '.join(conditions)}
		GROUP BY si.customer
		HAVING SUM(si.net_total) > 0
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

		turnover = flt(row.rebatable_turnover)
		rebate_amount = turnover * rebate_pct / 100
		freight_amount = turnover * freight_pct / 100
		results.append(
			{
				"customer": row.customer,
				"rebate_customer": get_linked_rebate_customer(row.customer),
				"rebatable_turnover": turnover,
				"total_turnover": turnover,
				"rebate_percentage": rebate_pct,
				"freight_rebate_percentage": freight_pct,
				"rebate_amount": rebate_amount,
				"freight_rebate_amount": freight_amount,
				"final_rebate_amount": rebate_amount + freight_amount,
			}
		)

	return results


def _non_rebateable_sql(alias="si"):
	"""AND clause so Non-Rebateable invoices are never tagged as settled."""
	if not frappe.db.has_column("Sales Invoice", "custom_exclude_from_rebate"):
		return ""
	return f"AND IFNULL({alias}.custom_exclude_from_rebate, 0) = 0"


def _get_settlement_item(company):
	"""Non-stock service item for rebate credit notes (not a Product Bundle)."""
	preferred_codes = ("Rebate Settlement", "Rebate Credit", "Distributor Rebate Settlement")
	for code in preferred_codes:
		if frappe.db.exists("Item", code) and _is_valid_settlement_item(code):
			return code

	items = frappe.get_all(
		"Item",
		filters={
			"is_stock_item": 0,
			"disabled": 0,
			"item_name": ("like", "%Rebate%"),
		},
		pluck="name",
		order_by="name asc",
	)
	for item in items:
		if _is_valid_settlement_item(item):
			return item

	frappe.throw(
		_(
			"Create a non-stock Item named <b>Rebate Settlement</b> (Service, not a Product Bundle) "
			"for rebate credit notes. The system must not use test or bundle items."
		),
		title=_("Rebate settlement item missing"),
	)


def _is_valid_settlement_item(item_code):
	if not item_code or frappe.db.get_value("Item", item_code, "disabled"):
		return False
	if cint(frappe.db.get_value("Item", item_code, "is_stock_item")):
		return False
	if frappe.db.exists("Product Bundle", item_code):
		return False
	return True
