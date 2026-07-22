import frappe
from frappe.utils import flt

TIER_RATES = {
	"None": 0,
	"0-50m (10%)": 10,
	"50-100m (11%)": 11,
}


def get_customer_rebate_rate(customer):
	data = frappe.db.get_value(
		"Customer",
		customer,
		[
			"custom_rebate_tier",
			"custom_rebate_override_percentage",
			"custom_freight_rebate_percentage",
			"custom_rebate_percentage",
		],
		as_dict=True,
	) or {}

	tier = data.get("custom_rebate_tier") or "None"
	if tier == "Override":
		rebate_percentage = flt(data.get("custom_rebate_override_percentage"))
	elif tier in TIER_RATES:
		rebate_percentage = TIER_RATES[tier]
	else:
		rebate_percentage = flt(data.get("custom_rebate_percentage"))

	return rebate_percentage, flt(data.get("custom_freight_rebate_percentage"))
