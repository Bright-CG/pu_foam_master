"""Backdate WIP chemical stock so historical Production Batches can consume it."""
import frappe
from frappe.utils import getdate


def run(posting_date="2026-07-01", qty=50000, valuation_rate=3500):
	warehouse = "Goods In Transit - SF"
	company = frappe.db.get_value("Warehouse", warehouse, "company")
	if not company:
		company = frappe.db.get_value("Company", {"abbr": "SF"}, "name") or "Solarfoam"

	expense = frappe.db.get_value(
		"Account",
		{"company": company, "account_name": ["like", "%Stock Adjustment%"], "is_group": 0},
		"name",
	)

	items = ["15_POLYMERIC", "TDI", "POLYOL II", "FILLER"]
	posting_date = str(getdate(posting_date))

	sr = frappe.new_doc("Stock Reconciliation")
	sr.company = company
	sr.purpose = "Stock Reconciliation"
	sr.posting_date = posting_date
	sr.posting_time = "00:00:01"
	sr.set_posting_time = 1
	if expense:
		sr.expense_account = expense

	for item in items:
		if not frappe.db.exists("Item", item):
			continue
		sr.append(
			"items",
			{
				"item_code": item,
				"warehouse": warehouse,
				"qty": qty,
				"valuation_rate": valuation_rate,
			},
		)

	if not sr.items:
		frappe.throw("No chemical items found to inject.")

	sr.insert(ignore_permissions=True)
	sr.submit()
	frappe.db.commit()

	print(f"SR {sr.name} posted {posting_date} @ {warehouse} qty={qty}")
	from erpnext.stock.stock_ledger import get_previous_sle

	for item in items:
		prev = get_previous_sle(
			frappe._dict(
				{
					"item_code": item,
					"warehouse": warehouse,
					"posting_date": "2026-07-22",
					"posting_time": "12:00:00",
				}
			)
		)
		qty_asof = prev.get("qty_after_transaction") if prev else 0
		bin_qty = frappe.db.get_value(
			"Bin", {"item_code": item, "warehouse": warehouse}, "actual_qty"
		)
		print(f"  {item}: as_of_2026-07-22={qty_asof} bin_now={bin_qty}")

	return sr.name
