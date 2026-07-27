import frappe
from frappe.utils import cint, flt


def get_customer_rebate_rate(customer):
	"""
	Resolve distributor rebate % from linked Rebate Tier (or explicit override).

	Priority:
	1. custom_use_rebate_override + custom_rebate_override_percentage
	2. Linked Rebate Tier.rebate_percentage
	3. Legacy custom_rebate_percentage
	"""
	data = frappe.db.get_value(
		"Customer",
		customer,
		[
			"custom_rebate_tier",
			"custom_use_rebate_override",
			"custom_rebate_override_percentage",
			"custom_freight_rebate_percentage",
			"custom_rebate_percentage",
		],
		as_dict=True,
	) or {}

	if cint(data.get("custom_use_rebate_override")):
		rebate_percentage = flt(data.get("custom_rebate_override_percentage"))
	else:
		tier = data.get("custom_rebate_tier")
		if tier and frappe.db.exists("Rebate Tier", tier):
			rebate_percentage = flt(
				frappe.db.get_value("Rebate Tier", tier, "rebate_percentage")
			)
		else:
			# Legacy Select values / percentage fallback during migration
			rebate_percentage = flt(data.get("custom_rebate_percentage"))

	return rebate_percentage, flt(data.get("custom_freight_rebate_percentage"))
