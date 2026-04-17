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
                "Item-width",
                "Item-height",
                "Item-length",
                "Item-cbm_value"
            ]]
        ]
    }
]

# ── Post Install / After Migrate Hooks ───────────────────────────────────────
after_migrate = [
    "pu_foam_master.setup_workspace.create_workspace"
]
