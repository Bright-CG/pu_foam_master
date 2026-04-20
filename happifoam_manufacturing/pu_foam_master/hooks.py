app_name = "pu_foam_master"
app_title = "PU Foam Master"
app_publisher = "Bright"
app_description = "Foam Manufacturing Management"
app_email = "bright@example.com"
app_license = "mit"

# ── Module to App Mapping ─────────────────────────────────────────────────────
# Tells Frappe which modules belong to this app so DocType routing works
app_include_css = []
app_include_js = []

# ── Fixtures ────────────────────────────────────────────────────────────────
# Export these to ensure custom fields on 'Item' move with the app
fixtures = [
    {
        "dt": "Custom Field",
        "filters": [
            ["name", "in", [
                "Item-custom_width",
                "Item-custom_height",
                "Item-custom_length",
                "Item-custom_cbm_value"
            ]]
        ]
    }
]

# ── Post Install / After Migrate Hooks ───────────────────────────────────────
after_migrate = [
    "pu_foam_master.custom_fields.ensure_item_custom_fields",
    "pu_foam_master.setup_workspace.create_workspace",
]

after_install = [
    "pu_foam_master.custom_fields.ensure_item_custom_fields",
]
