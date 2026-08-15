import frappe


def migrate_rebate_settlement_tool():
	if frappe.db.table_exists("tabRebate Processing Batch") and not frappe.db.table_exists(
		"tabRebate Settlement Tool"
	):
		frappe.db.sql(
			"""
			RENAME TABLE `tabRebate Processing Batch` TO `tabRebate Settlement Tool`
			"""
		)

	if frappe.db.exists("DocType", "Rebate Processing Batch") and not frappe.db.exists(
		"DocType", "Rebate Settlement Tool"
	):
		frappe.rename_doc(
			"DocType",
			"Rebate Processing Batch",
			"Rebate Settlement Tool",
			force=True,
			merge=False,
		)

	if frappe.db.has_column("Rebate Calculation", "journal_entry") and not frappe.db.has_column(
		"Rebate Calculation", "credit_note"
	):
		frappe.db.sql(
			"""
			ALTER TABLE `tabRebate Calculation`
			CHANGE `journal_entry` `credit_note` varchar(140)
			"""
		)

	if frappe.db.has_column("Rebate Calculation", "total_purchase_amount") and not frappe.db.has_column(
		"Rebate Calculation", "total_turnover"
	):
		frappe.db.sql(
			"""
			ALTER TABLE `tabRebate Calculation`
			CHANGE `total_purchase_amount` `total_turnover` decimal(21,9) NOT NULL DEFAULT 0
			"""
		)

	frappe.db.commit()
	frappe.clear_cache(doctype="Rebate Settlement Tool")


def cleanup_output_item_variant():
	"""Remove legacy Output Item Variant DocType left over from old density UI."""
	if frappe.db.exists("DocType", "Output Item Variant"):
		frappe.delete_doc("DocType", "Output Item Variant", force=1)
		frappe.db.commit()
		print("[setup_migrations] Deleted DocType 'Output Item Variant'.")

	# Copy legacy standard_lengths values into target_block_lengths when present
	if frappe.db.has_column("Density Configuration", "standard_lengths") and frappe.db.has_column(
		"Density Configuration", "target_block_lengths"
	):
		frappe.db.sql(
			"""
			UPDATE `tabDensity Configuration`
			SET target_block_lengths = standard_lengths
			WHERE IFNULL(target_block_lengths, '') = ''
				AND IFNULL(standard_lengths, '') != ''
			"""
		)
		frappe.db.commit()


def backfill_density_configuration_company():
	"""
	Set Company on Density Configurations (from get_preferred_company) and rebuild
	active BOMs when they belong to a different company.

	BOM cancel/rebuild is gated behind developer_mode so live customer migrates
	never destroy Active BOMs unexpectedly.
	"""
	if not frappe.db.has_column("Density Configuration", "company"):
		return

	from pu_foam_master.pufm_manufacturing.utils.density_bom import (
		get_preferred_company,
		sync_bom_for_density_config,
	)

	company = get_preferred_company()
	if not company:
		print("[setup_migrations] No company found; skip density company backfill.")
		return

	frappe.db.sql(
		"""
		UPDATE `tabDensity Configuration`
		SET company = %s
		WHERE IFNULL(company, '') = ''
		""",
		(company,),
	)
	frappe.db.commit()

	if not frappe.conf.get("developer_mode"):
		print(
			f"[setup_migrations] Density company backfill -> {company}. "
			"BOM rebuild skipped (developer_mode is off)."
		)
		return

	rebuilt = []
	for name in frappe.get_all(
		"Density Configuration",
		filters={"docstatus": 1},
		pluck="name",
	):
		doc = frappe.get_doc("Density Configuration", name)
		if not doc.company:
			doc.db_set("company", company, update_modified=False)

		bom_company = None
		if doc.active_bom:
			active = frappe.get_all(
				"BOM",
				filters={"name": doc.active_bom, "docstatus": 1, "is_active": 1},
				fields=["company"],
				limit=1,
			)
			bom_company = active[0].company if active else None

		if bom_company == doc.company:
			continue

		try:
			sync_bom_for_density_config(doc, cancel_existing=True)
			rebuilt.append({"density": name, "bom": doc.active_bom, "company": doc.company})
			frappe.db.commit()
		except Exception as exc:
			frappe.db.rollback()
			print(f"[setup_migrations] BOM rebuild failed for {name}: {exc}")

	print(
		f"[setup_migrations] Density company backfill -> {company}. "
		f"BOM rebuilt for {len(rebuilt)} density config(s)."
	)


def backfill_production_batch_company():
	"""Set Company on existing Production Batches via get_preferred_company()."""
	if not frappe.db.has_column("Pufm Production Batch", "company"):
		return

	from pu_foam_master.pufm_manufacturing.utils.density_bom import get_preferred_company

	company = get_preferred_company()
	if not company:
		print("[setup_migrations] No company found; skip production batch company backfill.")
		return

	frappe.db.sql(
		"""
		UPDATE `tabPufm Production Batch`
		SET company = %s
		WHERE IFNULL(company, '') = ''
		""",
		(company,),
	)
	frappe.db.commit()
	print(f"[setup_migrations] Production Batch company backfill -> {company}.")


def disable_foam_block_serials():
	"""Foam blocks are Batch-only. Clear Has Serial No on generated block Items."""
	from frappe.utils import cint

	from pu_foam_master.pufm_manufacturing.utils.item_traceability import (
		DEFAULT_BATCH_NUMBER_SERIES,
		list_foam_block_item_codes,
	)

	updated = []
	for item_code in list_foam_block_item_codes():
		has_serial = cint(frappe.db.get_value("Item", item_code, "has_serial_no"))
		has_batch = cint(frappe.db.get_value("Item", item_code, "has_batch_no"))
		create_new = cint(frappe.db.get_value("Item", item_code, "create_new_batch"))
		series = frappe.db.get_value("Item", item_code, "batch_number_series") or ""
		if not has_serial and has_batch and create_new and series.strip():
			continue
		values = {
			"has_serial_no": 0,
			"has_batch_no": 1,
			"create_new_batch": 1,
		}
		if not str(series).strip():
			values["batch_number_series"] = DEFAULT_BATCH_NUMBER_SERIES
		frappe.db.set_value("Item", item_code, values, update_modified=False)
		updated.append(item_code)

	if updated:
		frappe.db.commit()
		print(
			f"[setup_migrations] Disabled serials on {len(updated)} foam block Item(s): "
			+ ", ".join(updated)
		)
	else:
		print("[setup_migrations] Foam block Items already Batch-only.")
