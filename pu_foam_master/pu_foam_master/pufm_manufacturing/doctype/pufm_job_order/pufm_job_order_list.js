// Copyright (c) 2026, PU Foam Master and contributors
// For license information, please see license.txt

frappe.listview_settings["Pufm Job Order"] = {
	add_fields: ["workflow_status", "order_type"],
	get_indicator(doc) {
		if (cint(doc.docstatus) === 0) {
			return [__("Draft"), "red"];
		}
		if (cint(doc.docstatus) === 2) {
			return [__("Cancelled"), "gray"];
		}

		const colors = {
			"Pending Slicing": "orange",
			"Pending Quilting": "purple",
			"Pending Assembly": "blue",
			Completed: "green",
		};
		const status = doc.workflow_status || "Pending Slicing";
		const color = colors[status] || "gray";
		return [__(status), color];
	},
};
