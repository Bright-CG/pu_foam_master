# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

"""Sales Order → factory routing for stock shortfalls."""

from __future__ import annotations

from math import ceil

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate


@frappe.whitelist()
def request_production(sales_order):
	"""Create Material Requests / Job Orders for Sales Order stock shortfalls."""
	if not sales_order:
		frappe.throw(_("Sales Order is required."))

	so = frappe.get_doc("Sales Order", sales_order)
	if so.docstatus == 2:
		frappe.throw(_("Cannot request production for a cancelled Sales Order."))

	settings = frappe.get_single("Pufm Manufacturing Settings")
	job_group = (settings.route_to_job_order_group or "").strip()
	mr_group = (settings.route_to_material_request_group or "").strip()
	if not job_group and not mr_group:
		frappe.throw(
			_(
				"Set Route to Job Order Group and/or Route to Material Request Group "
				"in Pufm Manufacturing Settings."
			)
		)

	job_shortfalls = []
	mr_shortfalls = []
	unrouted = []

	for row in so.get("items") or []:
		if not row.item_code or flt(row.qty) <= 0:
			continue
		if cint(frappe.db.get_value("Item", row.item_code, "is_stock_item")) != 1:
			continue

		warehouse = row.warehouse or so.set_warehouse
		available = _get_available_qty(row.item_code, warehouse)
		shortfall = flt(row.qty) - available
		if shortfall <= 0:
			continue

		short_qty = cint(ceil(shortfall))
		payload = {
			"item_code": row.item_code,
			"qty": short_qty,
			"warehouse": warehouse,
			"sales_order": so.name,
			"sales_order_item": row.name,
			"schedule_date": getdate(row.delivery_date or so.delivery_date or nowdate()),
			"uom": row.uom,
			"conversion_factor": row.conversion_factor or 1,
		}

		item_group = frappe.db.get_value("Item", row.item_code, "item_group")
		routed = False
		if job_group and _is_under_item_group(item_group, job_group):
			job_shortfalls.append(payload)
			routed = True
		elif mr_group and _is_under_item_group(item_group, mr_group):
			mr_shortfalls.append(payload)
			routed = True

		if not routed:
			unrouted.append(row.item_code)

	created = []
	if mr_shortfalls:
		mr_name = _create_material_request(so, mr_shortfalls)
		created.append(_("Material Request {0}").format(mr_name))
	if job_shortfalls:
		jo_name = _create_job_order(so, job_shortfalls)
		created.append(_("Job Order {0}").format(jo_name))

	if not created:
		if unrouted:
			frappe.throw(
				_(
					"Shortfall items were found but none matched the configured routing "
					"Item Groups: {0}"
				).format(", ".join(unrouted))
			)
		return {
			"message": _("No stock shortfalls found on {0}.").format(so.name),
			"created": [],
		}

	message = _("Created {0}").format(" and ".join(created))
	if unrouted:
		message += ". " + _(
			"Skipped (no matching route group): {0}"
		).format(", ".join(sorted(set(unrouted))))

	return {"message": message, "created": created}


def _get_available_qty(item_code, warehouse=None):
	if warehouse:
		return flt(
			frappe.db.get_value(
				"Bin",
				{"item_code": item_code, "warehouse": warehouse},
				"actual_qty",
			)
		)
	total = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(actual_qty), 0)
		FROM `tabBin`
		WHERE item_code = %s
		""",
		(item_code,),
	)
	return flt(total[0][0]) if total else 0.0


def _is_under_item_group(item_group, root_group):
	"""True when item_group is root_group or a NestedSet descendant."""
	if not item_group or not root_group:
		return False
	if item_group == root_group:
		return True
	if not frappe.db.exists("Item Group", item_group):
		return False
	if not frappe.db.exists("Item Group", root_group):
		return False

	root = frappe.db.get_value("Item Group", root_group, ["lft", "rgt"], as_dict=True)
	node = frappe.db.get_value("Item Group", item_group, ["lft", "rgt"], as_dict=True)
	if not root or not node:
		return False
	return cint(root.lft) <= cint(node.lft) and cint(root.rgt) >= cint(node.rgt)


def _create_material_request(so, rows):
	mr = frappe.new_doc("Material Request")
	mr.company = so.company
	mr.material_request_type = "Manufacture"
	mr.transaction_date = nowdate()
	mr.schedule_date = rows[0]["schedule_date"]
	if hasattr(mr, "sales_order"):
		mr.sales_order = so.name

	for row in rows:
		mr.append(
			"items",
			{
				"item_code": row["item_code"],
				"qty": row["qty"],
				"schedule_date": row["schedule_date"],
				"warehouse": row["warehouse"],
				"uom": row.get("uom"),
				"conversion_factor": row.get("conversion_factor") or 1,
				"sales_order": so.name,
			},
		)

	mr.insert(ignore_permissions=True)
	return mr.name


def _create_job_order(so, rows):
	jo = frappe.new_doc("Pufm Job Order")
	jo.customer = so.customer
	jo.order_type = "Mattress"
	jo.source_doctype = "Sales Order"
	jo.source_document = so.name

	for row in rows:
		jo.append(
			"mattress_instructions",
			{
				"item_code": row["item_code"],
				"quantity": row["qty"],
			},
		)

	jo.insert(ignore_permissions=True)
	return jo.name
