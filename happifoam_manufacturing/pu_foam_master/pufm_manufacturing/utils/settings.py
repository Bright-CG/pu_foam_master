import frappe
from frappe import _
from frappe.utils import flt

CBM_DIVISOR = 61023.74

SETTINGS_DOCTYPE = "Pufm Manufacturing Settings"

ABSORPTION_FIELDS = (
	("power_absorption_account", "Power Absorption Account"),
	("diesel_absorption_account", "Diesel Absorption Account"),
	("labour_absorption_account", "Labour Absorption Account"),
	("depreciation_absorption_account", "Depreciation Absorption Account"),
)

REBOUND_USD_FIELDS = (
	("power_cost_usd_per_hour", "Power Cost USD per Hour"),
	("diesel_cost_usd_per_hour", "Diesel Cost USD per Hour"),
	("labour_cost_usd_per_hour", "Labour Cost USD per Hour"),
	("depreciation_cost_usd_per_hour", "Depreciation Cost USD per Hour"),
)


def get_settings():
	return frappe.get_single(SETTINGS_DOCTYPE)


def get_rebound_settings():
	settings = get_settings()
	require_absorption_accounts(settings)
	if not flt(settings.rebound_exchange_rate):
		frappe.throw(_("Please set Rebound Exchange Rate in Pufm Manufacturing Settings."))
	return settings


def require_absorption_accounts(settings=None):
	settings = settings or get_settings()
	missing = []

	for fieldname, label in ABSORPTION_FIELDS:
		if not settings.get(fieldname):
			missing.append(label)

	for fieldname, label in REBOUND_USD_FIELDS:
		if flt(settings.get(fieldname)) <= 0:
			missing.append(label)

	if not flt(settings.rebound_exchange_rate):
		missing.append(_("Rebound Exchange Rate"))

	if missing:
		frappe.throw(
			_("Missing Rebound Production settings in Pufm Manufacturing Settings: {0}").format(
				", ".join(missing)
			)
		)

	return settings


def get_rebate_expense_account():
	account = frappe.db.get_single_value(SETTINGS_DOCTYPE, "rebate_expense_account")
	if not account:
		frappe.throw(_("Please set Rebate Expense Account in Pufm Manufacturing Settings."))

	root_type = frappe.db.get_value("Account", account, "root_type")
	if root_type != "Expense":
		frappe.throw(_("Rebate Expense Account must be an Expense account."))

	return account


def validate_account_type(account, expected_root_type, label):
	if not account:
		return

	root_type = frappe.db.get_value("Account", account, "root_type")
	if root_type != expected_root_type:
		frappe.throw(_("{0} must be a {1} account.").format(label, expected_root_type))


def calculate_cbm(length_inches, width_inches, height_inches, quantity=1):
	return flt(length_inches) * flt(width_inches) * flt(height_inches) * flt(quantity) / CBM_DIVISOR
