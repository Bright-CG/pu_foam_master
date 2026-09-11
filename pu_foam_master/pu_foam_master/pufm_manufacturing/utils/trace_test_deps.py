# Copyright (c) 2026, PU Foam Master and contributors
"""Trace why Mattress Core Conversion tests pull Payment Gateway."""

from __future__ import annotations

from collections import deque

import frappe
from frappe.test_runner import get_dependencies


def run(start_doctype: str = "Mattress Core Conversion"):
	apps = frappe.get_installed_apps()
	has_payments = "payments" in apps
	has_pg = frappe.db.exists("DocType", "Payment Gateway")

	seen = set()
	parent = {}
	q = deque([start_doctype])
	fail_at = None
	fail_err = None

	while q:
		dt = q.popleft()
		if dt in seen:
			continue
		seen.add(dt)
		try:
			deps = get_dependencies(dt) or []
		except Exception as exc:
			fail_at = dt
			fail_err = "{0}: {1}".format(type(exc).__name__, exc)
			break
		for dep in deps:
			if dep not in seen and dep not in parent:
				parent[dep] = dt
			if dep not in seen:
				q.append(dep)

	path = []
	if fail_at and "Payment Gateway" in str(fail_err):
		# reconstruct path to the doctype whose dependency list includes Payment Gateway
		# get_dependencies fails inside get_modules(Payment Gateway)
		# find who listed Payment Gateway
		for dt in list(seen):
			try:
				deps = get_dependencies(dt) or []
			except Exception:
				continue
			if "Payment Gateway" in deps:
				cur = dt
				chain = [cur]
				while cur in parent:
					cur = parent[cur]
					chain.append(cur)
				path = list(reversed(chain)) + ["Payment Gateway"]
				break

	# Also find Link fields to Payment Gateway in ERPNext if doctype missing
	linkers = []
	if not has_pg:
		linkers = frappe.db.sql(
			"""
			SELECT parent, fieldname, options
			FROM `tabDocField`
			WHERE options = 'Payment Gateway'
			ORDER BY parent, fieldname
			""",
			as_dict=True,
		)

	result = {
		"installed_apps": apps,
		"payments_app_installed": has_payments,
		"payment_gateway_doctype_exists": bool(has_pg),
		"fail_at": fail_at,
		"fail_err": fail_err,
		"dependency_path": path,
		"docfields_linking_payment_gateway": linkers[:30],
		"deps_visited": len(seen),
	}
	print(result)
	return result
