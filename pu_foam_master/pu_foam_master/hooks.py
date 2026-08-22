app_name = "pu_foam_master"
app_title = "PU Foam Master"
app_publisher = "PU Foam Master"
app_description = "Foam Manufacturing Management"
app_email = "support@example.com"
app_license = "mit"

app_include_css = []
app_include_js = []

fixtures = [
	{
		"dt": "Custom Field",
		"filters": [
			[
				"name",
				"in",
				[
					"Item-custom_width",
					"Item-custom_height",
					"Item-custom_length",
					"Item-custom_cbm_value",
					"Item-custom_finish_type",
					"Customer-custom_rebate_configuration_section",
					"Customer-custom_is_distributor",
					"Customer-custom_rebate_tier",
					"Customer-custom_use_rebate_override",
					"Customer-custom_rebate_override_percentage",
					"Customer-custom_freight_rebate_percentage",
					"Customer-custom_rebate_percentage",
					"Sales Invoice-custom_rebate_section",
					"Sales Invoice-custom_apply_instant_rebate",
					"Sales Invoice-custom_instant_rebate_percentage",
					"Sales Invoice-custom_instant_rebate_amount",
					"Sales Invoice-custom_rebate_settlement",
				],
			]
		],
	},
	{
		"dt": "Role",
		"filters": [
			[
				"name",
				"in",
				[
					"PUFM Manager",
					"PUFM Block Production",
					"PUFM Conversion",
					"PUFM Quilting",
					"PUFM Assembly",
					"PUFM Rebound",
					"PUFM Brand Policy",
				],
			]
		],
	},
]

# No master-data seeding on install/migrate (Items, Warehouses, Companies, etc.).
# Use: bench --site <site> execute pu_foam_master.utils.demo_data.seed_test_items

before_install = [
	"pu_foam_master.setup_defaults.before_install",
]

after_migrate = [
	"pu_foam_master.setup_migrations.migrate_rebate_settlement_tool",
	"pu_foam_master.setup_migrations.cleanup_output_item_variant",
	"pu_foam_master.setup_migrations.backfill_density_configuration_company",
	"pu_foam_master.setup_migrations.backfill_production_batch_company",
	"pu_foam_master.setup_migrations.disable_foam_block_serials",
	"pu_foam_master.setup_migrations.disable_foam_core_serials",
	"pu_foam_master.setup_defaults.migrate_rebate_expense_account",
	"pu_foam_master.setup_defaults.ensure_pufm_roles",
	"pu_foam_master.custom_fields.ensure_item_custom_fields",
	"pu_foam_master.setup_migrations.backfill_mattress_item_brand_and_finish",
	"pu_foam_master.setup_migrations.ensure_labels_item_group",
	"pu_foam_master.setup_migrations.repair_job_order_workflow_statuses",
	"pu_foam_master.setup_migrations.migrate_quilting_record_parent_materials",
	"pu_foam_master.custom_fields.ensure_sales_invoice_rebate_fields",
	"pu_foam_master.setup_defaults.ensure_customer_rebate_fields",
	"pu_foam_master.setup_defaults.ensure_default_rebate_tiers",
	"pu_foam_master.setup_defaults.migrate_customer_rebate_tier_links",
	"pu_foam_master.setup_workspace.create_workspace",
]

after_install = [
	# Single safe runner — each step is isolated so one failure cannot abort install
	"pu_foam_master.install.run_after_install",
]

doctype_js = {
	"Sales Invoice": "public/js/sales_invoice.js",
	"Sales Order": "public/js/sales_order.js",
	"Item": "public/js/item.js",
}

doc_events = {
	"Sales Invoice": {
		"validate": "pu_foam_master.rebate.sales_invoice.apply_instant_rebate",
		"before_submit": "pu_foam_master.rebate.sales_invoice.ensure_rebate_tax_row",
	},
	"Item": {
		"validate": "pu_foam_master.pufm_manufacturing.utils.item_cbm.on_item_validate",
	},
	"Stock Entry": {
		"before_submit": (
			"pu_foam_master.pufm_manufacturing.utils.stock_entry_hooks.balance_pufm_stock_entry_before_submit"
		),
	},
}
