import frappe


OLD_WORKSPACE_NAME = "Happifoam Manufacturing"


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
			"label": "Foam Block Conversion",
			"link_to": "Foam Block Conversion",
			"type": "DocType",
			"icon": "shuffle",
		},
		{
			"label": "Rebound Configuration",
			"link_to": "Rebound Configuration",
			"type": "DocType",
			"icon": "settings",
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
		{"label": "Virgin PU Production", "is_header": 1},
		{"label": "Density Configuration", "link_to": "Density Configuration", "link_type": "DocType", "type": "Link"},
		{"label": "Pufm Production Batch", "link_to": "Pufm Production Batch", "link_type": "DocType", "type": "Link"},
		{"label": "Pufm Density Run", "link_to": "Pufm Density Run", "link_type": "DocType", "type": "Link"},
		{"label": "Foam Block Conversion", "link_to": "Foam Block Conversion", "link_type": "DocType", "type": "Link"},
		{"label": "Rebound Production", "is_header": 1},
		{"label": "Pufm Manufacturing Settings", "link_to": "Pufm Manufacturing Settings", "link_type": "DocType", "type": "Link"},
		{"label": "Rebound Configuration", "link_to": "Rebound Configuration", "link_type": "DocType", "type": "Link"},
		{"label": "Rebound Production Entry", "link_to": "Rebound Production Entry", "link_type": "DocType", "type": "Link"},
		{"label": "Scrap Costing Calculator", "link_to": "Scrap Costing Calculator", "link_type": "DocType", "type": "Link"},
		{"label": "Manufacturing Logic", "is_header": 1},
		{"label": "Standard Mattress Size", "link_to": "Standard Mattress Size", "link_type": "DocType", "type": "Link"},
		{"label": "Mattress Item Generator", "link_to": "Mattress Item Generator", "link_type": "DocType", "type": "Link"},
		{"label": "Mattress Brand Policy", "link_to": "Mattress Brand Policy", "link_type": "DocType", "type": "Link"},
		{"label": "Mattress Production Operations", "is_header": 1},
		{"label": "Quilting Record", "link_to": "Quilting Record", "link_type": "DocType", "type": "Link"},
		{"label": "Mattress Production Entry", "link_to": "Mattress Production Entry", "link_type": "DocType", "type": "Link"},
		{"label": "Financials & Rebates", "is_header": 1},
		{"label": "Rebate Settlement Tool", "link_to": "Rebate Settlement Tool", "link_type": "DocType", "type": "Link"},
		{"label": "Sales Invoice", "link_to": "Sales Invoice", "link_type": "DocType", "type": "Link"},
	]

	content = (
		'['
		'{"id":"h0","type":"header","data":{"text":"Virgin PU Production","col":12}},'
		'{"id":"s0","type":"shortcut","data":{"shortcut_name":"Density Configuration","col":3}},'
		'{"id":"s0b","type":"shortcut","data":{"shortcut_name":"Pufm Production Batch","col":3}},'
		'{"id":"s0c","type":"shortcut","data":{"shortcut_name":"Pufm Density Run","col":3}},'
		'{"id":"s0d","type":"shortcut","data":{"shortcut_name":"Foam Block Conversion","col":3}},'
		'{"id":"h1","type":"header","data":{"text":"Rebound Production","col":12}},'
		'{"id":"s1","type":"shortcut","data":{"shortcut_name":"Pufm Manufacturing Settings","col":3}},'
		'{"id":"s2","type":"shortcut","data":{"shortcut_name":"Rebound Configuration","col":3}},'
		'{"id":"s3","type":"shortcut","data":{"shortcut_name":"Rebound Production Entry","col":3}},'
		'{"id":"s4","type":"shortcut","data":{"shortcut_name":"Scrap Costing Calculator","col":3}},'
		'{"id":"h2","type":"header","data":{"text":"Financials & Rebates","col":12}},'
		'{"id":"s5","type":"shortcut","data":{"shortcut_name":"Rebate Settlement Tool","col":6}},'
		'{"id":"s6","type":"shortcut","data":{"shortcut_name":"Sales Invoice","col":6}},'
		'{"id":"h3","type":"header","data":{"text":"Mattress Production","col":12}},'
		'{"id":"s7","type":"shortcut","data":{"shortcut_name":"Quilting Record","col":6}},'
		'{"id":"s8","type":"shortcut","data":{"shortcut_name":"Mattress Production Entry","col":6}}'
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
	frappe.db.commit()


if __name__ == "__main__":
	create_workspace()
