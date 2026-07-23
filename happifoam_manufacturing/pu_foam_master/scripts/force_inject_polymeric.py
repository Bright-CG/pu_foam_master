import frappe
from frappe.utils import getdate, nowdate


def force_inject_polymeric(posting_date=None):
	"""
	Inject chemicals into Goods In Transit - SF.

	posting_date defaults to today. For Production Batches with an earlier
	posting_date, pass an earlier date (e.g. 2026-07-01) — ERPNext validates
	stock as of the Stock Entry posting date, not "bin today".
	"""
	warehouse = "Goods In Transit - SF"
	company = frappe.db.get_value("Warehouse", warehouse, "company")
	if not company:
		company = frappe.db.get_value("Company", {"abbr": "SF"}, "name") or "Solarfoam"

	expense = frappe.db.get_value(
		"Account",
		{"company": company, "account_name": ["like", "%Stock Adjustment%"], "is_group": 0},
		"name",
	)

	sr = frappe.new_doc("Stock Reconciliation")
	sr.company = company
	sr.purpose = "Stock Reconciliation"
	sr.posting_date = str(getdate(posting_date or nowdate()))
	sr.posting_time = "00:00:01"
	sr.set_posting_time = 1
	if expense:
		sr.expense_account = expense

	items_to_inject = ["15_POLYMERIC", "TDI", "POLYOL II", "FILLER"]

	for item in items_to_inject:
		if frappe.db.exists("Item", item):
			sr.append(
				"items",
				{
					"item_code": item,
					"warehouse": warehouse,
					"qty": 50000,
					"valuation_rate": 3500,
				},
			)

	sr.insert(ignore_permissions=True)
	sr.submit()
	frappe.db.commit()
	print(
		"SR:",
		sr.name,
		"company:",
		company,
		"warehouse:",
		warehouse,
		"posting_date:",
		sr.posting_date,
	)

	for item in items_to_inject:
		bin_qty = frappe.db.get_value(
			"Bin", {"item_code": item, "warehouse": warehouse}, "actual_qty"
		)
		print(f"SUCCESS: {item} now has {bin_qty} qty in {warehouse}.")

	return sr.name
