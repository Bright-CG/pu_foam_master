// Copyright (c) 2026, PU Foam Master and contributors
// For license information, please see license.txt

frappe.query_reports["Pufm Stock Matrix"] = {
	filters: [
		{
			fieldname: "item_group",
			label: __("Item Group"),
			fieldtype: "Link",
			options: "Item Group",
		},
		{
			fieldname: "item_code",
			label: __("Item"),
			fieldtype: "Link",
			options: "Item",
			get_query() {
				return { filters: { disabled: 0, is_stock_item: 1 } };
			},
		},
	],
};
