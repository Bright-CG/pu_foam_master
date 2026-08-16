import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


PUFM_ROLES = (
	"PUFM Manager",
	"PUFM Block Production",
	"PUFM Conversion",
	"PUFM Quilting",
	"PUFM Assembly",
	"PUFM Rebound",
	"PUFM Brand Policy",
)


def ensure_pufm_roles():
	"""Create desk roles for department RBAC (idempotent; not master-data)."""
	created = 0
	for role_name in PUFM_ROLES:
		if frappe.db.exists("Role", role_name):
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Role",
				"role_name": role_name,
				"desk_access": 1,
				"is_custom": 1,
			}
		)
		doc.insert(ignore_permissions=True)
		created += 1
	if created:
		frappe.db.commit()
		print(f"[setup_defaults] Created {created} PUFM role(s).")


def ensure_default_item_groups():
	"""Manual helper only — not wired into install/migrate hooks."""
	if not frappe.db.exists("Item Group", "All Item Groups"):
		frappe.get_doc(
			{
				"doctype": "Item Group",
				"item_group_name": "All Item Groups",
				"is_group": 1,
			}
		).insert(ignore_permissions=True, ignore_if_duplicate=True)

	if not frappe.db.exists("Item Group", "Products"):
		item_group = frappe.get_doc(
			{
				"doctype": "Item Group",
				"item_group_name": "Products",
				"parent_item_group": "All Item Groups",
				"is_group": 1,
			}
		)
		item_group.insert(ignore_permissions=True, ignore_if_duplicate=True)

	frappe.db.commit()


def ensure_labels_item_group():
	"""Create the Labels Item Group used by mattress assembly label selection."""
	from pu_foam_master.setup_migrations import ensure_labels_item_group as _ensure

	_ensure()


def ensure_standard_mattress_sizes():
	"""Manual helper only — prefer pu_foam_master.utils.demo_data.seed_standard_mattress_sizes."""
	from pu_foam_master.utils.demo_data import seed_standard_mattress_sizes

	seed_standard_mattress_sizes()


def migrate_rebate_expense_account():
	income_account = frappe.db.get_single_value(
		"Pufm Manufacturing Settings", "rebate_income_account"
	)
	expense_account = frappe.db.get_single_value(
		"Pufm Manufacturing Settings", "rebate_expense_account"
	)
	if income_account and not expense_account:
		frappe.db.set_single_value(
			"Pufm Manufacturing Settings",
			"rebate_expense_account",
			income_account,
		)
		frappe.db.commit()


def ensure_customer_rebate_fields():
	# Frappe blocks Select -> Link fieldtype changes; recreate the field when needed.
	_recreate_customer_rebate_tier_link_field()

	custom_fields = {
		"Customer": [
			{
				"fieldname": "custom_rebate_configuration_section",
				"label": "Rebate Configuration",
				"fieldtype": "Section Break",
				"insert_after": "customer_group",
				"permlevel": 1,
			},
			{
				"fieldname": "custom_is_distributor",
				"label": "Is Distributor",
				"fieldtype": "Check",
				"insert_after": "custom_rebate_configuration_section",
				"permlevel": 1,
			},
			{
				"fieldname": "custom_rebate_tier",
				"label": "Rebate Tier",
				"fieldtype": "Link",
				"options": "Rebate Tier",
				"insert_after": "custom_is_distributor",
				"permlevel": 1,
			},
			{
				"fieldname": "custom_use_rebate_override",
				"label": "Use Rebate Override",
				"fieldtype": "Check",
				"insert_after": "custom_rebate_tier",
				"permlevel": 1,
			},
			{
				"fieldname": "custom_rebate_override_percentage",
				"label": "Rebate Override Percentage",
				"fieldtype": "Float",
				"depends_on": "eval:doc.custom_use_rebate_override",
				"insert_after": "custom_use_rebate_override",
				"permlevel": 1,
			},
			{
				"fieldname": "custom_freight_rebate_percentage",
				"label": "Freight Rebate Percentage",
				"fieldtype": "Float",
				"insert_after": "custom_rebate_override_percentage",
				"permlevel": 1,
			},
			{
				"fieldname": "custom_rebate_percentage",
				"label": "Rebate Percentage (Legacy)",
				"fieldtype": "Percent",
				"insert_after": "custom_freight_rebate_percentage",
				"permlevel": 1,
				"read_only": 1,
			},
		]
	}
	create_custom_fields(custom_fields, update=True)
	frappe.db.commit()


def _recreate_customer_rebate_tier_link_field():
	"""Replace legacy Select custom_rebate_tier with a Link to Rebate Tier."""
	cf_name = frappe.db.get_value(
		"Custom Field", {"dt": "Customer", "fieldname": "custom_rebate_tier"}, "name"
	)
	if not cf_name:
		return

	fieldtype = frappe.db.get_value("Custom Field", cf_name, "fieldtype")
	options = frappe.db.get_value("Custom Field", cf_name, "options")
	if fieldtype == "Link" and options == "Rebate Tier":
		return

	# Preserve values while rebuilding the Custom Field definition
	frappe.delete_doc("Custom Field", cf_name, force=1)
	frappe.db.commit()
	frappe.clear_cache(doctype="Customer")
	print(
		"[setup_defaults] Recreated Customer.custom_rebate_tier as Link -> Rebate Tier "
		f"(was {fieldtype})."
	)

DEFAULT_REBATE_TIERS = (
	{
		"tier_name": "0-50M (10%)",
		"min_turnover_ngn": 0,
		"max_turnover_ngn": 50_000_000,
		"rebate_percentage": 10,
		"description": "Baseline distributor tier for turnover up to ₦50M.",
	},
	{
		"tier_name": "50M-100M (11%)",
		"min_turnover_ngn": 50_000_001,
		"max_turnover_ngn": 100_000_000,
		"rebate_percentage": 11,
		"description": "Baseline distributor tier for turnover from ₦50M to ₦100M.",
	},
)


def ensure_default_rebate_tiers():
	"""Seed baseline Rebate Tier masters (idempotent configuration, not Items)."""
	if not frappe.db.exists("DocType", "Rebate Tier"):
		return

	created = 0
	for row in DEFAULT_REBATE_TIERS:
		if frappe.db.exists("Rebate Tier", row["tier_name"]):
			continue
		doc = frappe.get_doc({"doctype": "Rebate Tier", **row})
		doc.insert(ignore_permissions=True)
		created += 1

	if created:
		frappe.db.commit()
		print(f"[setup_defaults] Created {created} default Rebate Tier(s).")


def migrate_customer_rebate_tier_links():
	"""Map legacy Select values on Customer.custom_rebate_tier to Rebate Tier Links."""
	if not frappe.db.has_column("Customer", "custom_rebate_tier"):
		return
	if not frappe.db.exists("DocType", "Rebate Tier"):
		return

	ensure_default_rebate_tiers()

	# Old Select option -> new Link name (or clear)
	legacy_map = {
		"None": "",
		"0-50m (10%)": "0-50M (10%)",
		"50-100m (11%)": "50M-100M (11%)",
		"Override": "",
	}

	if frappe.db.has_column("Customer", "custom_use_rebate_override"):
		frappe.db.sql(
			"""
			UPDATE `tabCustomer`
			SET custom_use_rebate_override = 1
			WHERE custom_rebate_tier = 'Override'
			"""
		)

	for old_value, new_value in legacy_map.items():
		frappe.db.sql(
			"""
			UPDATE `tabCustomer`
			SET custom_rebate_tier = %s
			WHERE custom_rebate_tier = %s
			""",
			(new_value, old_value),
		)

	frappe.db.commit()
	print("[setup_defaults] Migrated Customer custom_rebate_tier Select values to Links.")


def ensure_customer_rebate_field():
	ensure_customer_rebate_fields()