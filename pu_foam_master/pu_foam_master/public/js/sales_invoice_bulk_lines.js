// Copyright (c) 2026, PU Foam Master and contributors

frappe.provide("pu_foam_master.bulk_invoice_lines");

pu_foam_master.bulk_invoice_lines.open_dialog = function (frm) {
	if (frm.doc.docstatus !== 0) {
		frappe.msgprint(__("Bulk add is only available on draft invoices."));
		return;
	}
	if (!frm.doc.company) {
		frappe.msgprint(__("Set Company on the invoice before bulk add."));
		return;
	}

	const state = { rows: [] };

	const d = new frappe.ui.Dialog({
		title: __("Bulk add items"),
		size: "extra-large",
		fields: [
			{
				fieldname: "item_group",
				label: __("Item Group"),
				fieldtype: "Link",
				options: "Item Group",
				reqd: 1,
				onchange() {
					load_items();
				},
			},
			{
				fieldname: "search",
				label: __("Search"),
				fieldtype: "Data",
				description: __("Filter by item code or name (e.g. D18 or brand text)."),
			},
			{
				fieldname: "results_html",
				fieldtype: "HTML",
				options: `<p class="text-muted">${__(
					"Select an Item Group, then search. Enter quantity on each row and click Add to invoice."
				)}</p>`,
			},
		],
		primary_action_label: __("Add to invoice"),
		primary_action() {
			add_selected_to_invoice(frm, d, state);
		},
	});

	d.show();

	const $search = d.fields_dict.search.$input;
	$search.on(
		"input",
		frappe.utils.debounce(() => load_items(), 400)
	);

	function capture_qty_from_dom() {
		state.qty_map = state.qty_map || {};
		d.fields_dict.results_html.$wrapper.find(".pufm-bulk-qty").each(function () {
			const code = $(this).attr("data-item-code");
			if (code) {
				state.qty_map[code] = $(this).val();
			}
		});
	}

	function load_items() {
		capture_qty_from_dom();
		const item_group = d.get_value("item_group");
		if (!item_group) {
			render_table(d, [], state);
			return;
		}
		frappe.call({
			method: "pu_foam_master.selling.bulk_invoice_lines.search_items_for_bulk_invoice",
			args: {
				item_group,
				txt: d.get_value("search") || "",
				limit: 80,
			},
			freeze: true,
			freeze_message: __("Loading items…"),
			callback(r) {
				state.rows = r.message || [];
				render_table(d, state.rows, state);
			},
		});
	}

	// Default groups common on floor (user can change Link)
	const common_groups = ["Products", "Finished Mattresses", "Foam Cores"];
	if (!d.get_value("item_group")) {
		frappe.db.get_value("Item Group", "Products", "name").then((r) => {
			if (r && r.message && r.message.name) {
				d.set_value("item_group", r.message.name);
			} else {
				d.set_value("item_group", common_groups[0]);
			}
			load_items();
		});
	}
};

function render_table(dialog, rows, state) {
	const $wrapper = dialog.fields_dict.results_html.$wrapper;
	if (!rows.length) {
		$wrapper.html(`<p class="text-muted">${__("No items found. Try another group or search.")}</p>`);
		return;
	}

	const qty_map = state.qty_map || {};
	const header = `
		<table class="table table-bordered pufm-bulk-invoice-table" style="margin-top:8px;font-size:12px;">
			<thead>
				<tr>
					<th>${__("Item")}</th>
					<th>${__("Details")}</th>
					<th style="width:90px;">${__("UOM")}</th>
					<th style="width:110px;">${__("Qty")}</th>
				</tr>
			</thead>
			<tbody>
	`;

	const body = rows
		.map((row) => {
			const code = frappe.utils.escape_html(row.item_code);
			const name = frappe.utils.escape_html(row.item_name || row.item_code);
			const details = frappe.utils.escape_html(row.details || "");
			const uom = frappe.utils.escape_html(row.stock_uom || "");
			const qty = qty_map[row.item_code] != null ? qty_map[row.item_code] : "";
			return `<tr data-item-code="${code}">
				<td><strong>${code}</strong><br><span class="text-muted">${name}</span></td>
				<td>${details}</td>
				<td>${uom}</td>
				<td><input type="number" class="form-control input-sm pufm-bulk-qty" min="0" step="any"
					data-item-code="${code}" value="${qty}" /></td>
			</tr>`;
		})
		.join("");

	$wrapper.html(header + body + "</tbody></table>");

	$wrapper.find(".pufm-bulk-qty").on("change", function () {
		const code = $(this).attr("data-item-code");
		qty_map[code] = $(this).val();
		state.qty_map = qty_map;
	});
}

function add_selected_to_invoice(frm, dialog, state) {
	const qty_map = state.qty_map || {};
	const $inputs = dialog.fields_dict.results_html.$wrapper.find(".pufm-bulk-qty");
	const selected = [];

	$inputs.each(function () {
		const code = $(this).attr("data-item-code");
		const qty = flt($(this).val());
		if (code && qty > 0) {
			selected.push({ item_code: code, qty });
		}
	});

	if (!selected.length) {
		frappe.msgprint(__("Enter a quantity greater than zero on at least one row."));
		return;
	}

	let pending = selected.length;
	selected.forEach(({ item_code, qty }) => {
		const existing = (frm.doc.items || []).find((row) => row.item_code === item_code);
		if (existing) {
			frappe.model.set_value(
				existing.doctype,
				existing.name,
				"qty",
				flt(existing.qty) + qty
			);
			pending -= 1;
			if (pending <= 0) {
				finish_bulk_add(frm, dialog, selected.length);
			}
			return;
		}

		const child = frm.add_child("items");
		frappe.model
			.set_value(child.doctype, child.name, "item_code", item_code)
			.then(() => frappe.model.set_value(child.doctype, child.name, "qty", qty))
			.then(() => {
				pending -= 1;
				if (pending <= 0) {
					finish_bulk_add(frm, dialog, selected.length);
				}
			});
	});
}

function finish_bulk_add(frm, dialog, count) {
	frm.refresh_field("items");
	dialog.hide();
	frappe.show_alert({
		message: __("Added {0} line(s) to the invoice.", [count]),
		indicator: "green",
	});
}
