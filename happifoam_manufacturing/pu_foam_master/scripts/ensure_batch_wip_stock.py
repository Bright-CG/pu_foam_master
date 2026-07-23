"""Ensure all Production Batch BOM chemicals exist in WIP as of batch posting date."""
import frappe
from frappe.utils import flt, getdate


def run(batch_name="PB-2026-07-001", qty=50000, valuation_rate=3500, posting_date="2026-07-01"):
	batch = frappe.get_doc("Pufm Production Batch", batch_name)
	warehouse = (
		frappe.db.get_single_value("Pufm Manufacturing Settings", "default_wip_warehouse")
		or "Goods In Transit - SF"
	)
	company = batch.company or frappe.db.get_value("Warehouse", warehouse, "company")
	as_of_date = str(getdate(batch.posting_date))
	inject_date = str(getdate(posting_date))

	from erpnext.stock.stock_ledger import get_previous_sle

	needed = {}
	runs = batch._get_linked_runs()
	for run in runs:
		bom_name = frappe.db.get_value("Density Configuration", run.density_config, "active_bom")
		if not bom_name:
			print(f"WARN: no active_bom for {run.density_config}")
			continue
		basis = flt(run.actual_cbm) or flt(run.expected_cbm)
		for row in frappe.get_all(
			"BOM Item",
			filters={"parent": bom_name},
			fields=["item_code", "qty", "uom"],
		):
			req = flt(row.qty) * basis
			needed[row.item_code] = needed.get(row.item_code, 0) + req

	print(f"Batch {batch_name} posting_date={as_of_date} wip={warehouse}")
	print(f"Items required ({len(needed)}):")

	short = []
	for item_code, req_qty in sorted(needed.items(), key=lambda x: x[0]):
		prev = get_previous_sle(
			frappe._dict(
				{
					"item_code": item_code,
					"warehouse": warehouse,
					"posting_date": as_of_date,
					"posting_time": "23:59:59",
				}
			)
		)
		avail = flt(prev.get("qty_after_transaction")) if prev else 0.0
		bin_now = flt(
			frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty")
		)
		ok = avail >= req_qty
		status = "OK" if ok else "SHORT"
		print(f"  [{status}] {item_code}: need={req_qty:.4f} as_of={avail} bin_now={bin_now}")
		if not ok:
			short.append(item_code)

	if not short:
		print("All BOM chemicals available as of batch posting date.")
		return {"short": [], "sr": None}

	expense = frappe.db.get_value(
		"Account",
		{"company": company, "account_name": ["like", "%Stock Adjustment%"], "is_group": 0},
		"name",
	)

	sr = frappe.new_doc("Stock Reconciliation")
	sr.company = company
	sr.purpose = "Stock Reconciliation"
	sr.posting_date = inject_date
	sr.posting_time = "00:00:01"
	sr.set_posting_time = 1
	if expense:
		sr.expense_account = expense

	# Inject ALL required BOM items (not only short) so future batches are covered
	for item_code in sorted(needed.keys()):
		if not frappe.db.exists("Item", item_code):
			print(f"SKIP missing Item {item_code}")
			continue
		# keep existing valuation if known, else default
		rate = (
			frappe.db.get_value(
				"Bin", {"item_code": item_code, "warehouse": warehouse}, "valuation_rate"
			)
			or valuation_rate
		)
		sr.append(
			"items",
			{
				"item_code": item_code,
				"warehouse": warehouse,
				"qty": qty,
				"valuation_rate": flt(rate) or valuation_rate,
			},
		)

	sr.insert(ignore_permissions=True)
	sr.submit()
	frappe.db.commit()
	print(f"Submitted {sr.name} on {inject_date} for {len(sr.items)} items @ {qty}")

	still_short = []
	for item_code, req_qty in sorted(needed.items()):
		prev = get_previous_sle(
			frappe._dict(
				{
					"item_code": item_code,
					"warehouse": warehouse,
					"posting_date": as_of_date,
					"posting_time": "23:59:59",
				}
			)
		)
		avail = flt(prev.get("qty_after_transaction")) if prev else 0.0
		if avail < req_qty:
			still_short.append(item_code)
			print(f"  STILL SHORT {item_code}: as_of={avail} need={req_qty}")
		else:
			print(f"  FIXED {item_code}: as_of={avail}")

	return {"short_before": short, "still_short": still_short, "sr": sr.name}
