import json

import frappe


# Legacy Desk workspace label from pre-white-label builds.
# Kept only so migrate can delete the old sidebar entry if it still exists.
OLD_WORKSPACE_NAME = "Happifoam Manufacturing"

PUFM_CREATE_CUSTOMER_DOCTYPE = "PUFM Create Customer"
PUFM_CREATE_CUSTOMER_LABEL = "PUFM Create Customer"
ACCOUNTING_WORKSPACE_CANDIDATES = ("Accounting", "Accounts")

PUFM_CREATE_CUSTOMER_LINK = {
	"type": "Link",
	"label": PUFM_CREATE_CUSTOMER_LABEL,
	"link_type": "DocType",
	"link_to": PUFM_CREATE_CUSTOMER_DOCTYPE,
	"onboard": 0,
	"is_query_report": 0,
}


def create_workspace():
	workspace_name = "PU Foam Master"

	if frappe.db.exists("Workspace", OLD_WORKSPACE_NAME):
		frappe.delete_doc("Workspace", OLD_WORKSPACE_NAME, force=1)

	shortcuts = [
		{
			"label": "Pufm Manufacturing Settings",
			"link_to": "Pufm Manufacturing Settings",
			"type": "DocType",
			"icon": "settings",
		},
		{
			"label": "Density Configuration",
			"link_to": "Density Configuration",
			"type": "DocType",
			"icon": "settings",
		},
		{
			"label": "Rebate Tier",
			"link_to": "Rebate Tier",
			"type": "DocType",
			"icon": "settings",
		},
		{
			"label": "Pufm Production Batch",
			"link_to": "Pufm Production Batch",
			"type": "DocType",
			"icon": "manufacturing",
		},
		{
			"label": "Pufm Density Run",
			"link_to": "Pufm Density Run",
			"type": "DocType",
			"icon": "list",
		},
		{
			"label": "Mattress Core Conversion",
			"link_to": "Mattress Core Conversion",
			"type": "DocType",
			"icon": "shuffle",
		},
		{
			"label": "Pufm Sheeting Conversion",
			"link_to": "Pufm Sheeting Conversion",
			"type": "DocType",
			"icon": "file",
		},
		{
			"label": "Pufm Job Order",
			"link_to": "Pufm Job Order",
			"type": "DocType",
			"icon": "file",
		},
		{
			"label": "Production Variance Report",
			"link_to": "Production Variance Report",
			"type": "Report",
			"icon": "file",
			"is_query_report": 1,
		},
		{
			"label": "Pufm Stock Matrix",
			"link_to": "Pufm Stock Matrix",
			"type": "Report",
			"icon": "stock",
			"is_query_report": 1,
		},
		{
			"label": "PUFM Production Cost Inquiry",
			"link_to": "PUFM Production Cost Inquiry",
			"type": "Report",
			"icon": "accounting",
			"is_query_report": 1,
		},
		{
			"label": "Pufm Price Engine",
			"link_to": "Pufm Price Engine",
			"type": "DocType",
			"icon": "money",
		},
		{
			"label": "Rebound Configuration",
			"link_to": "Rebound Configuration",
			"type": "DocType",
			"icon": "settings",
		},
		{
			"label": "Pufm Rebond Item Generator",
			"link_to": "Pufm Rebond Item Generator",
			"type": "DocType",
			"icon": "manufacturing",
		},
		{
			"label": "Rebound Production Entry",
			"link_to": "Rebound Production Entry",
			"type": "DocType",
			"icon": "manufacturing",
		},
		{
			"label": "Scrap Costing Calculator",
			"link_to": "Scrap Costing Calculator",
			"type": "DocType",
			"icon": "money",
		},
		{
			"label": "Rebate Settlement Tool",
			"link_to": "Rebate Settlement Tool",
			"type": "DocType",
			"icon": "money",
		},
		{
			"label": "Rebate Balance Transfer",
			"link_to": "Rebate Balance Transfer",
			"type": "DocType",
			"icon": "exchange",
		},
		{
			"label": "PUFM Create Customer",
			"link_to": "PUFM Create Customer",
			"type": "DocType",
			"icon": "customer",
		},
		{
			"label": "Standard Mattress Size",
			"link_to": "Standard Mattress Size",
			"type": "DocType",
			"icon": "list",
		},
		{
			"label": "Mattress Item Generator",
			"link_to": "Mattress Item Generator",
			"type": "DocType",
			"icon": "manufacturing",
		},
		{
			"label": "Mattress Brand Policy",
			"link_to": "Mattress Brand Policy",
			"type": "DocType",
			"icon": "shuffle",
		},
		{"label": "Quilting Record", "link_to": "Quilting Record", "type": "DocType", "icon": "list"},
		{"label": "Mattress Production Entry", "link_to": "Mattress Production Entry", "type": "DocType", "icon": "manufacturing"},
		{"label": "Sales Invoice", "link_to": "Sales Invoice", "type": "DocType", "icon": "receipt"},
	]

	links = [
		{"label": "Configurations / Management", "is_header": 1},
		{"label": "Pufm Manufacturing Settings", "link_to": "Pufm Manufacturing Settings", "link_type": "DocType", "type": "Link"},
		{"label": "Density Configuration", "link_to": "Density Configuration", "link_type": "DocType", "type": "Link"},
		{"label": "Rebate Tier", "link_to": "Rebate Tier", "link_type": "DocType", "type": "Link"},
		{"label": "Rebound Configuration", "link_to": "Rebound Configuration", "link_type": "DocType", "type": "Link"},
		{"label": "Virgin PU Production", "is_header": 1},
		{"label": "Pufm Production Batch", "link_to": "Pufm Production Batch", "link_type": "DocType", "type": "Link"},
		{"label": "Pufm Density Run", "link_to": "Pufm Density Run", "link_type": "DocType", "type": "Link"},
		{"label": "Production Variance Report", "link_to": "Production Variance Report", "link_type": "Report", "is_query_report": 1, "type": "Link"},
		{"label": "Pufm Stock Matrix", "link_to": "Pufm Stock Matrix", "link_type": "Report", "is_query_report": 1, "type": "Link"},
		{"label": "PUFM Production Cost Inquiry", "link_to": "PUFM Production Cost Inquiry", "link_type": "Report", "is_query_report": 1, "type": "Link"},
		{"label": "Rebound Production", "is_header": 1},
		{"label": "Rebound Configuration", "link_to": "Rebound Configuration", "link_type": "DocType", "type": "Link"},
		{"label": "Pufm Rebond Item Generator", "link_to": "Pufm Rebond Item Generator", "link_type": "DocType", "type": "Link"},
		{"label": "Rebound Production Entry", "link_to": "Rebound Production Entry", "link_type": "DocType", "type": "Link"},
		{"label": "Scrap Costing Calculator", "link_to": "Scrap Costing Calculator", "link_type": "DocType", "type": "Link"},
		{"label": "Manufacturing Logic", "is_header": 1},
		{"label": "Standard Mattress Size", "link_to": "Standard Mattress Size", "link_type": "DocType", "type": "Link"},
		{"label": "Mattress Item Generator", "link_to": "Mattress Item Generator", "link_type": "DocType", "type": "Link"},
		{"label": "Mattress Brand Policy", "link_to": "Mattress Brand Policy", "link_type": "DocType", "type": "Link"},
		{"label": "Mattress Production Operations", "is_header": 1},
		{"label": "Pufm Job Order", "link_to": "Pufm Job Order", "link_type": "DocType", "type": "Link"},
		{"label": "Mattress Core Conversion", "link_to": "Mattress Core Conversion", "link_type": "DocType", "type": "Link"},
		{"label": "Pufm Sheeting Conversion", "link_to": "Pufm Sheeting Conversion", "link_type": "DocType", "type": "Link"},
		{"label": "Quilting Record", "link_to": "Quilting Record", "link_type": "DocType", "type": "Link"},
		{"label": "Mattress Production Entry", "link_to": "Mattress Production Entry", "link_type": "DocType", "type": "Link"},
		{"label": "Financials & Rebates", "is_header": 1},
		{"label": "Pufm Price Engine", "link_to": "Pufm Price Engine", "link_type": "DocType", "type": "Link"},
		{"label": "Rebate Settlement Tool", "link_to": "Rebate Settlement Tool", "link_type": "DocType", "type": "Link"},
		{"label": "Rebate Balance Transfer", "link_to": "Rebate Balance Transfer", "link_type": "DocType", "type": "Link"},
		{"label": "PUFM Create Customer", "link_to": "PUFM Create Customer", "link_type": "DocType", "type": "Link"},
		{"label": "Sales Invoice", "link_to": "Sales Invoice", "link_type": "DocType", "type": "Link"},
	]

	content = (
		'['
		'{"id":"hcfg","type":"header","data":{"text":"Configurations / Management","col":12}},'
		'{"id":"scfg1","type":"shortcut","data":{"shortcut_name":"Pufm Manufacturing Settings","col":3}},'
		'{"id":"scfg2","type":"shortcut","data":{"shortcut_name":"Density Configuration","col":3}},'
		'{"id":"scfg3","type":"shortcut","data":{"shortcut_name":"Rebate Tier","col":3}},'
		'{"id":"scfg4","type":"shortcut","data":{"shortcut_name":"Rebound Configuration","col":3}},'
		'{"id":"h0","type":"header","data":{"text":"Virgin PU Production","col":12}},'
		'{"id":"s0b","type":"shortcut","data":{"shortcut_name":"Pufm Production Batch","col":3}},'
		'{"id":"s0c","type":"shortcut","data":{"shortcut_name":"Pufm Density Run","col":3}},'
		'{"id":"s0e","type":"shortcut","data":{"shortcut_name":"Production Variance Report","col":3}},'
		'{"id":"s0m","type":"shortcut","data":{"shortcut_name":"Pufm Stock Matrix","col":3}},'
		'{"id":"s0pci","type":"shortcut","data":{"shortcut_name":"PUFM Production Cost Inquiry","col":3}},'
		'{"id":"h1","type":"header","data":{"text":"Rebound Production","col":12}},'
		'{"id":"s2","type":"shortcut","data":{"shortcut_name":"Rebound Configuration","col":3}},'
		'{"id":"s2b","type":"shortcut","data":{"shortcut_name":"Pufm Rebond Item Generator","col":3}},'
		'{"id":"s3","type":"shortcut","data":{"shortcut_name":"Rebound Production Entry","col":3}},'
		'{"id":"s4","type":"shortcut","data":{"shortcut_name":"Scrap Costing Calculator","col":3}},'
		'{"id":"h2","type":"header","data":{"text":"Financials & Rebates","col":12}},'
		'{"id":"spe","type":"shortcut","data":{"shortcut_name":"Pufm Price Engine","col":4}},'
		'{"id":"s5","type":"shortcut","data":{"shortcut_name":"Rebate Settlement Tool","col":4}},'
		'{"id":"s5b","type":"shortcut","data":{"shortcut_name":"Rebate Balance Transfer","col":4}},'
		'{"id":"spcc","type":"shortcut","data":{"shortcut_name":"PUFM Create Customer","col":4}},'
		'{"id":"s6","type":"shortcut","data":{"shortcut_name":"Sales Invoice","col":4}},'
		'{"id":"h3","type":"header","data":{"text":"Mattress Production","col":12}},'
		'{"id":"s7a","type":"shortcut","data":{"shortcut_name":"Standard Mattress Size","col":3}},'
		'{"id":"s7b","type":"shortcut","data":{"shortcut_name":"Mattress Item Generator","col":3}},'
		'{"id":"s7c","type":"shortcut","data":{"shortcut_name":"Mattress Brand Policy","col":3}},'
		'{"id":"s0j","type":"shortcut","data":{"shortcut_name":"Pufm Job Order","col":3}},'
		'{"id":"s0d","type":"shortcut","data":{"shortcut_name":"Mattress Core Conversion","col":3}},'
		'{"id":"s0sh","type":"shortcut","data":{"shortcut_name":"Pufm Sheeting Conversion","col":3}},'
		'{"id":"s7","type":"shortcut","data":{"shortcut_name":"Quilting Record","col":3}},'
		'{"id":"s8","type":"shortcut","data":{"shortcut_name":"Mattress Production Entry","col":3}},'
		'{"id":"s8pci","type":"shortcut","data":{"shortcut_name":"PUFM Production Cost Inquiry","col":3}}'
		']'
	)

	schema = {
		"doctype": "Workspace",
		"name": workspace_name,
		"label": workspace_name,
		"title": workspace_name,
		"module": "pufm_manufacturing",
		"public": 1,
		"is_standard": 1,
		"content": content,
	}

	if frappe.db.exists("Workspace", workspace_name):
		doc = frappe.get_doc("Workspace", workspace_name)
	else:
		doc = frappe.new_doc("Workspace")
		doc.name = workspace_name

	doc.update(schema)
	doc.set("shortcuts", [])
	doc.set("links", [])

	for s in shortcuts:
		doc.append("shortcuts", s)
	for link in links:
		doc.append("links", link)

	doc.save(ignore_permissions=True)
	print(f"[setup_workspace] Successfully synced '{workspace_name}' workspace.")
	sync_accounting_workspace_pufm_create_customer()
	frappe.db.commit()


def _workspace_has_link(links, link_to: str) -> bool:
	return any(
		(row.get("type") if isinstance(row, dict) else row.type) == "Link"
		and (row.get("link_to") if isinstance(row, dict) else row.link_to) == link_to
		for row in links
	)


def sync_accounting_workspace_pufm_create_customer():
	"""Add PUFM Create Customer to ERPNext Accounting workspace (after Customer link)."""
	for ws_name in ACCOUNTING_WORKSPACE_CANDIDATES:
		if not frappe.db.exists("Workspace", ws_name):
			continue
		doc = frappe.get_doc("Workspace", ws_name)
		if _workspace_has_link(doc.links, PUFM_CREATE_CUSTOMER_DOCTYPE):
			print(f"[setup_workspace] '{PUFM_CREATE_CUSTOMER_LABEL}' already on '{ws_name}'.")
			return

		new_links = []
		inserted = False
		for row in doc.links:
			new_links.append(row.as_dict())
			if row.type == "Link" and row.link_to == "Customer" and not inserted:
				new_links.append(dict(PUFM_CREATE_CUSTOMER_LINK))
				inserted = True

		if not inserted:
			new_links.append(
				{
					"type": "Card Break",
					"label": "Customer Onboarding",
					"link_type": "DocType",
					"onboard": 0,
				}
			)
			new_links.append(dict(PUFM_CREATE_CUSTOMER_LINK))

		doc.set("links", [])
		for link in new_links:
			doc.append("links", link)

		_add_pufm_create_customer_shortcut_to_content(doc)
		doc.save(ignore_permissions=True)
		print(f"[setup_workspace] Added '{PUFM_CREATE_CUSTOMER_LABEL}' to '{ws_name}' workspace.")
		return

	print("[setup_workspace] No Accounting workspace found; skipped PUFM Create Customer link.")


def _add_pufm_create_customer_shortcut_to_content(doc):
	"""Append a dashboard shortcut block if missing (Accounting workspace content JSON)."""
	if not doc.content:
		return
	try:
		blocks = json.loads(doc.content)
	except (TypeError, json.JSONDecodeError):
		return
	if any(
		b.get("type") == "shortcut"
		and (b.get("data") or {}).get("shortcut_name") == PUFM_CREATE_CUSTOMER_LABEL
		for b in blocks
	):
		return
	blocks.append(
		{
			"id": "pufm_sp_create_customer",
			"type": "shortcut",
			"data": {"shortcut_name": PUFM_CREATE_CUSTOMER_LABEL, "col": 3},
		}
	)
	doc.content = json.dumps(blocks)


def sync_pufm_create_customer_workspaces():
	"""Idempotent sync for PU Foam Master + Accounting workspaces."""
	try:
		create_workspace()
	except Exception:
		frappe.log_error(title="sync_pufm_create_customer_workspaces PU Foam Master")
	try:
		sync_accounting_workspace_pufm_create_customer()
	except Exception:
		frappe.log_error(title="sync_pufm_create_customer_workspaces Accounting")


def create_workspace_safe():
	"""Workspace sync that never raises during install."""
	try:
		create_workspace()
	except Exception:
		frappe.log_error(title="pu_foam_master create_workspace failed")
		print("[setup_workspace] Workspace sync skipped (non-fatal).")


if __name__ == "__main__":
	create_workspace()
