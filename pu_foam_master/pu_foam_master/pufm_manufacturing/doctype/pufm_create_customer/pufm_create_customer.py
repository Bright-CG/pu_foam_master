# Copyright (c) 2026, PU Foam Master and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from pu_foam_master.pufm_manufacturing.utils.customer_creation import (
	create_rebate_wallet_customer,
	create_trade_customer,
	get_rebate_wallet_receivable_account,
	get_trade_receivable_account,
	link_main_to_rebate,
	normalize_main_customer_id,
	rebate_id_for_main,
	sync_customer_naming_series_counter,
	validate_customer_id_available,
)
from pu_foam_master.pufm_manufacturing.utils.density_bom import get_preferred_company


class PUFMCreateCustomer(Document):
	def validate(self):
		if not self.company:
			self.company = get_preferred_company()
		if not self.company:
			frappe.throw(_("Company is required."))

		if self.registration_type != "Rebate Wallet for Existing Main" and not (
			self.customer_name or ""
		).strip():
			frappe.throw(_("Customer Name is required."))

		self._set_preview_accounts()
		self._resolve_registration_fields()
		self._validate_ids()
		self._validate_existing_main_for_rebate_only()

	def on_submit(self):
		if self.created_main_customer or self.created_rebate_customer:
			frappe.throw(_("Customer records were already created for this document."))

		reg_type = self.registration_type
		main_id = self.main_customer_id
		rebate_id = (self.rebate_customer_id or "").strip() or None

		try:
			if reg_type == "Trade Customer Only":
				self.created_main_customer = create_trade_customer(
					main_id=main_id,
					customer_name=self.customer_name,
					company=self.company,
					customer_type=self.customer_type,
					customer_group=self.customer_group,
					is_distributor=cint(self.is_distributor),
					rebate_tier=self.rebate_tier,
				)
				sync_customer_naming_series_counter(main_id)

			elif reg_type == "Main and Rebate Wallet":
				rebate_name = self._rebate_display_name()
				self.created_main_customer = create_trade_customer(
					main_id=main_id,
					customer_name=self.customer_name,
					company=self.company,
					customer_type=self.customer_type,
					customer_group=self.customer_group,
					is_distributor=1,
					rebate_tier=self.rebate_tier,
				)
				self.created_rebate_customer = create_rebate_wallet_customer(
					rebate_id=rebate_id,
					rebate_customer_name=rebate_name,
					main_id=main_id,
					company=self.company,
					customer_type=self.customer_type,
					customer_group=self.customer_group,
				)
				link_main_to_rebate(main_id, rebate_id)
				sync_customer_naming_series_counter(main_id)

			elif reg_type == "Rebate Wallet for Existing Main":
				rebate_name = self._rebate_display_name()
				self.created_main_customer = main_id
				self.created_rebate_customer = create_rebate_wallet_customer(
					rebate_id=rebate_id,
					rebate_customer_name=rebate_name,
					main_id=main_id,
					company=self.company,
					customer_type=self.customer_type
					or frappe.db.get_value("Customer", main_id, "customer_type"),
					customer_group=self.customer_group
					or frappe.db.get_value("Customer", main_id, "customer_group"),
				)
				link_main_to_rebate(main_id, rebate_id)
			else:
				frappe.throw(_("Unknown registration type: {0}").format(reg_type))

			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			raise

		self.db_set("created_main_customer", self.created_main_customer, update_modified=False)
		if self.created_rebate_customer:
			self.db_set(
				"created_rebate_customer", self.created_rebate_customer, update_modified=False
			)

	def _set_preview_accounts(self):
		try:
			self.trade_receivable_account = get_trade_receivable_account(self.company)
		except frappe.ValidationError:
			self.trade_receivable_account = None
		try:
			self.rebate_receivable_account = get_rebate_wallet_receivable_account()
		except frappe.ValidationError:
			self.rebate_receivable_account = None

	def _resolve_registration_fields(self):
		reg_type = self.registration_type

		if reg_type == "Rebate Wallet for Existing Main":
			if not self.existing_main_customer:
				frappe.throw(_("Select Existing Main Customer."))
			self.main_customer_id = normalize_main_customer_id(self.existing_main_customer)
		elif reg_type in ("Trade Customer Only", "Main and Rebate Wallet"):
			if not self.main_customer_id:
				frappe.throw(_("Enter Main Customer ID."))
			self.main_customer_id = normalize_main_customer_id(self.main_customer_id)
		else:
			frappe.throw(_("Unknown registration type."))

		if reg_type == "Main and Rebate Wallet":
			self.is_distributor = 1

		if reg_type in ("Main and Rebate Wallet", "Rebate Wallet for Existing Main"):
			self.rebate_customer_id = rebate_id_for_main(self.main_customer_id)
			# Always derive rebate display name from full main name (avoid stale JS on first keystroke).
			self.rebate_customer_name = self._rebate_display_name()

	def _validate_ids(self):
		reg_type = self.registration_type
		main_id = self.main_customer_id

		if reg_type in ("Trade Customer Only", "Main and Rebate Wallet"):
			validate_customer_id_available(main_id, _("Main Customer ID"))

		if reg_type in ("Main and Rebate Wallet", "Rebate Wallet for Existing Main"):
			rebate_id = rebate_id_for_main(main_id)
			if (self.rebate_customer_id or "").strip().upper() != rebate_id:
				frappe.throw(
					_("Rebate Customer ID must be {0} for main ID {1}.").format(rebate_id, main_id)
				)
			validate_customer_id_available(rebate_id, _("Rebate Customer ID"))
			if not self.rebate_receivable_account:
				frappe.throw(_("Configure Rebate Wallet Receivable Account in Pufm Manufacturing Settings."))

	def _validate_existing_main_for_rebate_only(self):
		if self.registration_type != "Rebate Wallet for Existing Main":
			return
		main = self.existing_main_customer
		if cint(frappe.db.get_value("Customer", main, "custom_is_rebate_account")):
			frappe.throw(_("Existing customer {0} is a rebate wallet, not a main account.").format(main))
		if frappe.db.get_value("Customer", main, "custom_linked_rebate_customer"):
			frappe.throw(
				_("Main customer {0} already has Linked Rebate Customer. Use Customer master to review.").format(
					main
				)
			)
		if cint(frappe.db.get_value("Customer", main, "custom_is_distributor")) != 1:
			frappe.throw(
				_("Main customer {0} must be marked Is Distributor before adding a rebate wallet.").format(
					main
				)
			)

	def _rebate_display_name(self) -> str:
		if self.registration_type == "Rebate Wallet for Existing Main":
			base = (
				frappe.db.get_value("Customer", self.existing_main_customer, "customer_name") or ""
			).strip()
		else:
			base = (self.customer_name or "").strip()
		if not base:
			return (self.rebate_customer_name or "").strip() or _("Rebate Wallet")
		return f"{base} - Rebate"