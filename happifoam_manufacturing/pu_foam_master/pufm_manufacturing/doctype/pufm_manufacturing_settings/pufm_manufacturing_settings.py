import frappe
from frappe import _
from frappe.model.document import Document

from pu_foam_master.pufm_manufacturing.utils.settings import validate_account_type


class PufmManufacturingSettings(Document):
	def validate(self):
		for fieldname, label in (
			("power_absorption_account", "Power Absorption Account"),
			("diesel_absorption_account", "Diesel Absorption Account"),
			("labour_absorption_account", "Labour Absorption Account"),
			("depreciation_absorption_account", "Depreciation Absorption Account"),
			("conversion_absorption_account", "Conversion (Slicing) Absorption Account"),
		):
			validate_account_type(self.get(fieldname), "Expense", label)

		validate_account_type(self.rebate_expense_account, "Expense", "Rebate Expense Account")
		if self.rebate_income_account:
			validate_account_type(self.rebate_income_account, "Income", "Rebate Income Account")
