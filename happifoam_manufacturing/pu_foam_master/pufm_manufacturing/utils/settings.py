import frappe
from frappe import _
from frappe.utils import cint, flt

SETTINGS_DOCTYPE = "Pufm Manufacturing Settings"

# Baseline fallbacks (mirrored by FACTORY_FORMULA_DEFAULTS on Settings DocType)
CBM_DIVISOR = 61023.74
INCHES_PER_METER = 39.37
INCHES_TO_METERS = 0.0254

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


def get_factory_formula_defaults():
	from pu_foam_master.pufm_manufacturing.doctype.pufm_manufacturing_settings.pufm_manufacturing_settings import (
		FACTORY_FORMULA_DEFAULTS,
	)

	return FACTORY_FORMULA_DEFAULTS


def get_formula_factor(fieldname, settings=None):
	"""Return a Settings formula factor, falling back to factory default if empty/zero."""
	defaults = get_factory_formula_defaults()
	baseline = defaults.get(fieldname)
	settings = settings or get_settings()
	value = getattr(settings, fieldname, None)
	if baseline is None:
		return value
	if isinstance(baseline, int) and not isinstance(baseline, bool):
		return cint(value) or cint(baseline)
	return flt(value) or flt(baseline)


def get_cbm_factor(settings=None):
	return get_formula_factor("cbm_factor", settings)


def get_scrap_output_rate(settings=None):
	"""Rate used when scrap is received (pour, conversion, furniture sheeting). Zero is valid."""
	settings = settings or get_settings()
	return flt(getattr(settings, "scrap_output_rate", 0))


def get_scrap_input_rate(settings=None):
	"""Rate used when scrap is consumed in Rebound. Zero is valid."""
	settings = settings or get_settings()
	return flt(getattr(settings, "scrap_input_rate", 0))


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


def calculate_cbm(length_inches, width_inches, height_inches, quantity=1, settings=None):
	divisor = get_cbm_factor(settings)
	return flt(length_inches) * flt(width_inches) * flt(height_inches) * flt(quantity) / divisor
