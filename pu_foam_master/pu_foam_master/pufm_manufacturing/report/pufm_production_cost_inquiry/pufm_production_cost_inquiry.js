// Copyright (c) 2026, PU Foam Master and contributors

frappe.query_reports["PUFM Production Cost Inquiry"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "item_code",
			label: __("Finished Item"),
			fieldtype: "Link",
			options: "Item",
		},
		{
			fieldname: "item_group",
			label: __("Item Group"),
			fieldtype: "Link",
			options: "Item Group",
		},
		{
			fieldname: "production_doctype",
			label: __("Production Source"),
			fieldtype: "Select",
			options: [
				"",
				"Pufm Production Batch",
				"Mattress Core Conversion",
				"Quilting Record",
				"Mattress Production Entry",
				"Rebound Production Entry",
			],
		},
		{
			fieldname: "stock_entry",
			label: __("Stock Entry"),
			fieldtype: "Link",
			options: "Stock Entry",
		},
	],
	tree: true,
	initial_depth: 1,
	formatter(value, row, column, data, default_formatter) {
		if (column.fieldname === "integrity_flag" && data.indent === 0 && value === "Check") {
			value = `<span class="text-danger" title="${__(
				"Component lines do not sum to finished line cost"
			)}">${value}</span>`;
		}
		return default_formatter(value, row, column, data);
	},
};
