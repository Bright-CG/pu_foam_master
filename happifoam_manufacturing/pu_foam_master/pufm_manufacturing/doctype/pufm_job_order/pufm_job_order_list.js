// Copyright (c) 2026, PU Foam Master and contributors
// For license information, please see license.txt

frappe.listview_settings["Pufm Job Order"] = {
	add_fields: ["workflow_status", "order_type"],
	get_indicator(doc) {
		if (cint(doc.docstatus) === 0) {
			// No third-arg filter: values with spaces break list filters when clicked.
			return [__("Draft"), "red"];
		}
		if (cint(doc.docstatus) === 2) {
			return [__("Cancelled"), "gray"];
		}

		const colors = {
			"Pending Slicing": "orange",
			"Pending Assembly": "blue",
			Completed: "green",
		};
		const status = doc.workflow_status || "Pending Slicing";
		const color = colors[status] || "gray";
		// Color only — use the standard filter bar for workflow_status (avoids empty lists).
		return [__(status), color];
	},
};
