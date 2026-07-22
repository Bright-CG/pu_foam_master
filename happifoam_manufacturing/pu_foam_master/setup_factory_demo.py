"""
Data-driven factory demo loader for PU Foam Master.

Run:
    bench --site <site> execute pu_foam_master.setup_factory_demo.run

Optional args:
    items_csv, density_csv, skip_assertions
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

import frappe
from frappe.utils import cint, flt, getdate, nowdate

from pu_foam_master.pufm_manufacturing.utils.density_bom import get_virtual_item_code

DEMO_DATA_DIR = Path(__file__).resolve().parent / "demo_data"
DEFAULT_ITEMS_CSV = DEMO_DATA_DIR / "Item.csv"
DEFAULT_DENSITY_CSV = DEMO_DATA_DIR / "Density Config.csv"
KINGS_BLOCK = "Kings Block"


def run(items_csv=None, density_csv=None, skip_assertions=0, skip_foundation=0):
	"""Full demo runner (manual only — never hooked into install/migrate)."""
	frappe.flags.in_setup_factory_demo = True
	results = {}

	try:
		results.update(load_csv_master_data(items_csv=items_csv, density_csv=density_csv))

		if not cint(skip_assertions):
			results["bom_lifecycle"] = assert_kings_block_bom_lifecycle()

		if not cint(skip_foundation):
			results["foundation"] = setup_foundation_and_scrap_test()

		frappe.db.commit()
		return results
	finally:
		frappe.flags.in_setup_factory_demo = False


def load_csv_master_data(items_csv=None, density_csv=None):
	"""
	One-time site loader for Item.csv + Density Config.csv.
	Does NOT run on app install/migrate — call via bench execute only.
	"""
	from pu_foam_master.custom_fields import ensure_item_custom_fields

	# Ensure current custom fieldnames exist before mapping CSV columns
	ensure_item_custom_fields()

	items_path = _resolve_csv_path(items_csv, DEFAULT_ITEMS_CSV, "Item.csv")
	density_path = _resolve_csv_path(density_csv, DEFAULT_DENSITY_CSV, "Density Config.csv")

	return {
		"items": import_items_from_csv(items_path),
		"density_configurations": import_density_configs_from_csv(density_path),
		"note": "Manual one-time load only; not part of app install.",
	}


def repair_missing_density_boms():
	"""Create active BOMs for submitted Density Configurations that are missing them."""
	from pu_foam_master.pufm_manufacturing.utils.density_bom import sync_bom_for_density_config

	repaired = []
	failed = []
	rows = frappe.get_all(
		"Density Configuration",
		filters={"docstatus": 1},
		fields=["name", "active_bom"],
	)
	for row in rows:
		if row.active_bom:
			continue
		try:
			doc = frappe.get_doc("Density Configuration", row.name)
			bom_name = sync_bom_for_density_config(doc, cancel_existing=False)
			repaired.append({"density": row.name, "bom": bom_name})
		except Exception as exc:
			failed.append({"density": row.name, "error": str(exc)})
			frappe.log_error(
				title=f"BOM repair failed: {row.name}",
				message=frappe.get_traceback(),
			)

	frappe.db.commit()
	return {"repaired": repaired, "failed": failed}


def import_items_from_csv(csv_path):
	stats = {"created": 0, "updated": 0, "skipped": 0, "errors": []}

	with open(csv_path, newline="", encoding="utf-8-sig") as handle:
		reader = csv.DictReader(handle)
		for row in reader:
			item_code = _normalize_item_code(row)
			if not item_code:
				stats["skipped"] += 1
				continue

			try:
				action = _upsert_item_from_row(row)
				stats[action] += 1
			except Exception as exc:
				stats["errors"].append({"item_code": item_code, "error": str(exc)})
				frappe.log_error(title=f"Item import failed: {item_code}", message=frappe.get_traceback())

	frappe.db.commit()
	return stats


def import_density_configs_from_csv(csv_path):
	stats = {"created": 0, "updated": 0, "submitted": 0, "skipped": 0, "errors": []}
	configs = _parse_density_config_csv(csv_path)

	for config in configs:
		density_name = config["density_name"]
		try:
			action, submitted = _upsert_density_configuration(config)
			stats[action] += 1
			if submitted:
				stats["submitted"] += 1
		except Exception as exc:
			stats["errors"].append({"density_name": density_name, "error": str(exc)})
			frappe.log_error(
				title=f"Density Configuration import failed: {density_name}",
				message=frappe.get_traceback(),
			)

	frappe.db.commit()
	return stats


def assert_kings_block_bom_lifecycle():
	virtual_item = get_virtual_item_code(KINGS_BLOCK)
	if not frappe.db.exists("Item", virtual_item):
		raise AssertionError(f"Virtual item not found: {virtual_item}")

	config = frappe.get_doc("Density Configuration", KINGS_BLOCK)
	if config.docstatus != 1:
		raise AssertionError(f"{KINGS_BLOCK} Density Configuration is not submitted.")

	original_bom = config.active_bom
	if not original_bom:
		raise AssertionError(f"{KINGS_BLOCK} has no active BOM.")

	original_docstatus = frappe.db.get_value("BOM", original_bom, "docstatus")
	if original_docstatus != 1:
		raise AssertionError(f"Original BOM {original_bom} docstatus is {original_docstatus}, expected 1.")

	original_speed = flt(config.conveyor_speed)
	config.conveyor_speed = 4.0 if original_speed != 4.0 else 4.1
	config.save(ignore_permissions=True)
	frappe.db.commit()

	config.reload()
	new_bom = config.active_bom

	cancelled_docstatus = frappe.db.get_value("BOM", original_bom, "docstatus")
	if cancelled_docstatus != 2:
		raise AssertionError(
			f"Original BOM {original_bom} docstatus is {cancelled_docstatus}, expected 2 (Cancelled)."
		)

	if not new_bom or new_bom == original_bom:
		raise AssertionError("A new active BOM was not created after conveyor speed update.")

	new_docstatus = frappe.db.get_value("BOM", new_bom, "docstatus")
	if new_docstatus != 1:
		raise AssertionError(f"New BOM {new_bom} docstatus is {new_docstatus}, expected 1.")

	return {
		"virtual_item": virtual_item,
		"original_bom": original_bom,
		"new_bom": new_bom,
		"original_speed": original_speed,
		"updated_speed": flt(config.conveyor_speed),
	}


def setup_foundation_and_scrap_test():
	company = _get_company()
	warehouses = _ensure_demo_warehouses(company)
	accounts = _ensure_demo_expense_accounts(company)
	scrap_item = _resolve_item_code("SCRAP-FOAM") or _resolve_item_code("Scrap Foam")

	settings = frappe.get_single("Pufm Manufacturing Settings")
	settings.default_wip_warehouse = warehouses["wip"]
	settings.default_fg_warehouse = warehouses["fg"]
	settings.default_scrap_warehouse = warehouses["scrap"]
	settings.scrap_item = scrap_item
	settings.mdi_item = _resolve_item_code("TDI") or scrap_item
	settings.rebound_exchange_rate = flt(settings.rebound_exchange_rate) or 1550
	settings.power_cost_usd_per_hour = flt(settings.power_cost_usd_per_hour) or 10
	settings.diesel_cost_usd_per_hour = flt(settings.diesel_cost_usd_per_hour) or 8
	settings.labour_cost_usd_per_hour = flt(settings.labour_cost_usd_per_hour) or 12
	settings.depreciation_cost_usd_per_hour = flt(settings.depreciation_cost_usd_per_hour) or 5
	settings.power_absorption_account = accounts["power"]
	settings.diesel_absorption_account = accounts["diesel"]
	settings.labour_absorption_account = accounts["labour"]
	settings.depreciation_absorption_account = accounts["depreciation"]
	settings.rebate_expense_account = accounts["rebate"]
	settings.primary_volume_uom = settings.primary_volume_uom or "CBM"
	settings.default_vat_rate = flt(settings.default_vat_rate) or 7.5
	settings.save(ignore_permissions=True)

	_ensure_scrap_stock(scrap_item, warehouses["scrap"], qty=500)

	calc = frappe.new_doc("Scrap Costing Calculator")
	calc.posting_date = nowdate()
	calc.scrap_item = scrap_item
	calc.container_capacity_kg = 20000
	calc.shipping_cost_ngn = 5000000
	calc.local_logistics_ngn = 1200000
	calc.process_loss_contingency_ngn = 3000000
	calc.insert(ignore_permissions=True)
	calc.submit()

	if not calc.stock_reconciliation:
		raise AssertionError("Scrap Costing Calculator did not create a Stock Reconciliation.")

	reconciliation = frappe.get_doc("Stock Reconciliation", calc.stock_reconciliation)
	if reconciliation.docstatus != 1:
		raise AssertionError("Linked Stock Reconciliation is not submitted.")

	return {
		"company": company,
		"warehouses": warehouses,
		"accounts": accounts,
		"scrap_item": scrap_item,
		"scrap_costing_calculator": calc.name,
		"stock_reconciliation": calc.stock_reconciliation,
		"calculated_cost_per_kg": flt(calc.calculated_cost_per_kg),
	}


def _normalize_item_code(row):
	"""Map CSV Item Code to a usable code; fix known bad export rows."""
	item_code = (row.get("Item Code") or "").strip()
	item_name = (row.get("Item Name") or "").strip()

	# Bad export row: Item Code="Item Group", Item Name="POLYOL I"
	if item_code == "Item Group" and item_name:
		return item_name

	if item_code == "Item Group":
		return ""

	return item_code


def _upsert_item_from_row(row):
	item_code = _normalize_item_code(row)
	item_group = (row.get("Item Group") or "Products").strip()
	if item_group == item_code:
		# Guard against swapped export columns on bad rows
		item_group = "Raw Material"
	_ensure_item_group(item_group)
	_ensure_uom((row.get("Default Unit of Measure") or "Nos").strip())

	# CSV labels -> current custom fieldnames in this app version
	# Width Inches  -> custom_width
	# Height Inches -> custom_height
	# Length Inches -> custom_length
	# CBM Value     -> custom_cbm_value
	payload = {
		"item_name": (row.get("Item Name") or item_code).strip(),
		"item_group": item_group,
		"stock_uom": (row.get("Default Unit of Measure") or "Nos").strip(),
		"is_stock_item": cint(row.get("Maintain Stock", 1)),
		"include_item_in_manufacturing": cint(row.get("Include Item In Manufacturing", 0)),
		"valuation_method": (row.get("Valuation Method") or "").strip() or None,
		"disabled": cint(row.get("Disabled", 0)),
		"custom_width": _float_or_none(row.get("Width Inches")),
		"custom_height": _float_or_none(row.get("Height Inches")),
		"custom_length": _float_or_none(row.get("Length Inches")),
		"custom_cbm_value": _float_or_none(row.get("CBM Value")),
	}

	if frappe.db.exists("Item", item_code):
		doc = frappe.get_doc("Item", item_code)
		changed = False
		for fieldname, value in payload.items():
			if value is None:
				continue
			if doc.get(fieldname) != value:
				doc.set(fieldname, value)
				changed = True
		if changed:
			doc.save(ignore_permissions=True)
			return "updated"
		return "skipped"

	doc = frappe.new_doc("Item")
	doc.item_code = item_code
	for fieldname, value in payload.items():
		if value is not None:
			doc.set(fieldname, value)
	doc.insert(ignore_permissions=True)
	return "created"


def _upsert_density_configuration(config):
	density_name = config["density_name"]
	submitted = False

	if frappe.db.exists("Density Configuration", density_name):
		doc = frappe.get_doc("Density Configuration", density_name)
		if doc.docstatus == 1:
			return "skipped", False
		if doc.docstatus == 2:
			frappe.delete_doc("Density Configuration", density_name, force=1)
			doc = frappe.new_doc("Density Configuration")
			doc.density_name = density_name
			action = "updated"
		else:
			action = "updated"
	else:
		doc = frappe.new_doc("Density Configuration")
		doc.density_name = density_name
		action = "created"

	for fieldname in (
		"blow_index",
		"conveyor_speed",
		"calibration_factor",
		"width_inches",
		"height_inches",
	):
		doc.set(fieldname, config.get(fieldname))

	if not doc.company:
		doc.company = _get_company()

	doc.set("production_inputs", [])
	for row in config.get("production_inputs", []):
		item_code = _resolve_item_code(row["item_code"])
		if not item_code or not frappe.db.exists("Item", item_code):
			continue
		doc.append(
			"production_inputs",
			{
				"item_code": item_code,
				"flow_factor": row.get("flow_factor"),
				"set_at": row.get("set_at"),
			},
		)

	doc.set("bom_operations", [])
	for row in config.get("bom_operations", []):
		if not row.get("operation"):
			continue
		_ensure_operation(row["operation"])
		if row.get("workstation"):
			_ensure_workstation(row["workstation"])
		doc.append(
			"bom_operations",
			{
				"operation": row["operation"],
				"workstation": row.get("workstation"),
				"time": row.get("time"),
				"hour_rate": row.get("hour_rate"),
			},
		)

	if doc.is_new():
		doc.insert(ignore_permissions=True)
	else:
		doc.save(ignore_permissions=True)

	if doc.docstatus == 0:
		doc.submit()
		submitted = True

	return action, submitted


def _parse_density_config_csv(csv_path):
	configs = []
	current = None

	with open(csv_path, newline="", encoding="utf-8-sig") as handle:
		reader = csv.DictReader(handle)
		for row in reader:
			density_name = (row.get("Density") or "").strip()
			if density_name:
				if current:
					configs.append(current)
				current = {
					"density_name": density_name,
					"blow_index": _float_or_none(row.get("Blow Index")),
					"conveyor_speed": _float_or_none(row.get("Conveyor Speed")),
					"calibration_factor": _float_or_none(row.get("Calibration Factor")) or 1.0,
					"width_inches": _float_or_none(row.get("Width Inches")),
					"height_inches": _float_or_none(row.get("Height Inches")),
					"production_inputs": [],
					"bom_operations": [],
				}

			if not current:
				continue

			item_input = (row.get("Input (Production Inputs)") or "").strip()
			if item_input:
				current["production_inputs"].append(
					{
						"item_code": item_input,
						"flow_factor": _float_or_none(row.get("Flow Factor (Production Inputs)")),
						"set_at": _float_or_none(row.get("Set At (Production Inputs)")),
					}
				)

			operation = (row.get("Operation (Operations)") or "").strip()
			if operation:
				current["bom_operations"].append(
					{
						"operation": operation,
						"workstation": (row.get("Workstation (Operations)") or "").strip() or None,
						"time": _float_or_none(row.get("Operation Time (Minutes) (Operations)")),
						"hour_rate": _float_or_none(row.get("Hourly Cost (Operations)")),
					}
				)

	if current:
		configs.append(current)

	return configs


def _resolve_csv_path(explicit_path, default_path, fallback_name):
	if explicit_path:
		path = Path(explicit_path)
		if path.exists():
			return str(path)

	if default_path.exists():
		return str(default_path)

	downloads = Path.home() / "Downloads" / fallback_name
	if downloads.exists():
		return str(downloads)

	raise FileNotFoundError(
		f"Could not find CSV file. Tried: {explicit_path or default_path} and {downloads}"
	)


def _ensure_item_group(item_group_name):
	if frappe.db.exists("Item Group", item_group_name):
		return

	parent = "All Item Groups"
	if not frappe.db.exists("Item Group", parent):
		frappe.get_doc(
			{"doctype": "Item Group", "item_group_name": parent, "is_group": 1}
		).insert(ignore_permissions=True, ignore_if_duplicate=True)

	frappe.get_doc(
		{
			"doctype": "Item Group",
			"item_group_name": item_group_name,
			"parent_item_group": parent,
			"is_group": 0,
		}
	).insert(ignore_permissions=True, ignore_if_duplicate=True)


def _ensure_uom(uom):
	if not uom or frappe.db.exists("UOM", uom):
		return
	frappe.get_doc({"doctype": "UOM", "uom_name": uom}).insert(
		ignore_permissions=True, ignore_if_duplicate=True
	)


def _ensure_operation(operation):
	if not operation or frappe.db.exists("Operation", operation):
		return
	frappe.get_doc({"doctype": "Operation", "name": operation, "operation": operation}).insert(
		ignore_permissions=True, ignore_if_duplicate=True
	)


def _ensure_workstation(workstation):
	if not workstation or frappe.db.exists("Workstation", workstation):
		return
	frappe.get_doc(
		{"doctype": "Workstation", "name": workstation, "workstation_name": workstation}
	).insert(ignore_permissions=True, ignore_if_duplicate=True)


def _resolve_item_code(value):
	value = (value or "").strip()
	if not value:
		return None
	if frappe.db.exists("Item", value):
		return value
	return frappe.db.get_value("Item", {"item_name": value}, "name")


def _get_company():
	from pu_foam_master.pufm_manufacturing.utils.density_bom import get_preferred_company

	company = get_preferred_company()
	if company:
		return company
	raise frappe.ValidationError("No Company found. Complete ERPNext setup first.")


def _ensure_demo_warehouses(company):
	names = {
		"wip": "PUFM WIP",
		"fg": "PUFM Finished Goods",
		"scrap": "PUFM Scrap",
	}
	created = {}
	for key, label in names.items():
		created[key] = _ensure_warehouse(label, company)
	return created


def _ensure_warehouse(warehouse_name, company):
	existing = frappe.db.get_value(
		"Warehouse", {"warehouse_name": warehouse_name, "company": company}, "name"
	)
	if existing:
		return existing

	doc = frappe.new_doc("Warehouse")
	doc.warehouse_name = warehouse_name
	doc.company = company
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_demo_expense_accounts(company):
	labels = {
		"power": "Power Absorption",
		"diesel": "Diesel Absorption",
		"labour": "Labour Absorption",
		"depreciation": "Depreciation Absorption",
		"rebate": "Rebate Expense",
	}
	return {key: _ensure_expense_account(label, company) for key, label in labels.items()}


def _ensure_expense_account(label, company):
	abbr = frappe.db.get_value("Company", company, "abbr")
	account_name = f"PUFM {label} - {abbr}"
	if frappe.db.exists("Account", account_name):
		return account_name

	parent = frappe.db.get_value(
		"Account",
		{"company": company, "account_name": ["in", ["Indirect Expenses", "Direct Expenses"]]},
		"name",
	)
	if not parent:
		parent = frappe.db.get_value(
			"Account",
			{"company": company, "is_group": 1, "root_type": "Expense"},
			"name",
		)
	if not parent:
		raise frappe.ValidationError(f"No expense group account found for company {company}.")

	doc = frappe.new_doc("Account")
	doc.account_name = f"PUFM {label}"
	doc.parent_account = parent
	doc.company = company
	doc.account_type = "Expense Account"
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_scrap_stock(item_code, warehouse, qty=100):
	bin_qty = flt(
		frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty")
	)
	if bin_qty > 0:
		return

	entry = frappe.new_doc("Stock Entry")
	entry.stock_entry_type = "Material Receipt"
	entry.company = frappe.db.get_value("Warehouse", warehouse, "company")
	entry.posting_date = nowdate()
	entry.append(
		"items",
		{
			"item_code": item_code,
			"qty": qty,
			"t_warehouse": warehouse,
			"basic_rate": 100,
			"allow_zero_valuation_rate": 1,
		},
	)
	entry.insert(ignore_permissions=True)
	entry.submit()


def _float_or_none(value):
	if value in (None, ""):
		return None
	try:
		return flt(value)
	except (TypeError, ValueError):
		return None
