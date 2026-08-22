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


def disable_foam_core_serials():
	"""Mattress cores are Batch-only WIP. Clear Has Serial No; keep finished mattress serials."""
	from frappe.utils import cint

	from pu_foam_master.pufm_manufacturing.utils.item_traceability import (
		DEFAULT_BATCH_NUMBER_SERIES,
		list_foam_core_item_codes,
	)

	updated = []
	for item_code in list_foam_core_item_codes():
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
		# Orphan Serial No masters from earlier conversion tests; stock stays on the batch.
		for item_code in updated:
			frappe.db.sql(
				"""
				UPDATE `tabSerial No`
				SET status = 'Inactive'
				WHERE item_code = %s
					AND IFNULL(status, '') != 'Inactive'
				""",
				(item_code,),
			)
		frappe.db.commit()
		print(
			f"[setup_migrations] Disabled serials on {len(updated)} mattress core Item(s): "
			+ ", ".join(updated)
		)
	else:
		print("[setup_migrations] Mattress core Items already Batch-only.")


def backfill_mattress_item_brand_and_finish():
	"""Stamp Item.brand and custom_finish_type from current names (one-time / idempotent)."""
	import re

	from pu_foam_master.custom_fields import ensure_item_custom_fields

	ensure_item_custom_fields()
	frappe.clear_cache()

	size_re = re.compile(
		r"^(.+?)-(\d+(?:\.\d+)?x\d+(?:\.\d+)?x\d+(?:\.\d+)?)(.*)$",
		re.IGNORECASE,
	)
	suffix_map = (
		("-PLAIN", "Plain"),
		("-SQ", "Side Quilted"),
		("-FQ", "Fully Quilted"),
	)

	def infer_finish(name):
		upper = (name or "").upper()
		for suffix, label in suffix_map:
			if upper.endswith(suffix):
				return label
		return None

	def infer_brand(name):
		match = size_re.match(name or "")
		token = match.group(1) if match else None
		if not token and (name or "").upper().startswith("MAT-"):
			parts = name.split("-")
			token = parts[1] if len(parts) >= 3 else None
		if not token:
			return None
		if frappe.db.exists("Brand", token):
			return token
		spaced = token.replace("-", " ")
		if frappe.db.exists("Brand", spaced):
			return spaced
		return None

	updated = 0
	items = frappe.get_all(
		"Item",
		filters={"disabled": 0},
		fields=["name", "brand", "custom_finish_type", "item_group"],
	)
	for item in items:
		values = {}
		finish = infer_finish(item.name)
		if finish and not (item.custom_finish_type or "").strip():
			values["custom_finish_type"] = finish
		if not item.brand:
			brand = infer_brand(item.name)
			if brand:
				values["brand"] = brand
		if not values:
			continue
		frappe.db.set_value("Item", item.name, values, update_modified=False)
		updated += 1

	if updated:
		frappe.db.commit()
		print(
			f"[setup_migrations] Stamped brand/finish type on {updated} Item(s)."
		)
	else:
		print("[setup_migrations] Mattress Item brand/finish type already populated.")


def ensure_labels_item_group():
	"""Ensure Item Group 'Labels' exists; move Settings default label Item into it if set."""
	parent = "All Item Groups"
	if not frappe.db.exists("Item Group", parent):
		frappe.get_doc(
			{
				"doctype": "Item Group",
				"item_group_name": parent,
				"is_group": 1,
			}
		).insert(ignore_permissions=True)

	if not frappe.db.exists("Item Group", "Labels"):
		frappe.get_doc(
			{
				"doctype": "Item Group",
				"item_group_name": "Labels",
				"parent_item_group": parent,
				"is_group": 0,
			}
		).insert(ignore_permissions=True)
		print("[setup_migrations] Created Item Group 'Labels'.")
	else:
		print("[setup_migrations] Item Group 'Labels' already exists.")

	default_label = frappe.db.get_single_value(
		"Pufm Manufacturing Settings", "default_label_item"
	)
	if default_label and frappe.db.exists("Item", default_label):
		current_group = frappe.db.get_value("Item", default_label, "item_group")
		if current_group != "Labels":
			frappe.db.set_value(
				"Item", default_label, "item_group", "Labels", update_modified=False
			)
			print(
				f"[setup_migrations] Moved default label Item '{default_label}' "
				f"from '{current_group}' to 'Labels'."
			)

	frappe.db.commit()


def migrate_quilting_record_parent_materials():
	"""Copy legacy Quilting Input child rows onto fabric/sheeting parent fields."""
	if not frappe.db.has_column("Quilting Record", "fabric_item"):
		return
	if not frappe.db.table_exists("tabQuilting Input"):
		return

	parents = frappe.db.sql(
		"""
		SELECT parent
		FROM `tabQuilting Input`
		GROUP BY parent
		HAVING COUNT(*) >= 1
		""",
		as_dict=True,
	)
	updated = 0
	for row in parents:
		name = row.parent
		if not name or not frappe.db.exists("Quilting Record", name):
			continue
		if frappe.db.get_value("Quilting Record", name, "fabric_item"):
			continue
		inputs = frappe.get_all(
			"Quilting Input",
			filters={"parent": name},
			fields=["item_code", "source_warehouse", "batch_no", "qty", "idx"],
			order_by="idx asc",
		)
		if not inputs:
			continue
		fabric = inputs[0]
		sheeting = inputs[1] if len(inputs) > 1 else frappe._dict()
		frappe.db.set_value(
			"Quilting Record",
			name,
			{
				"fabric_item": fabric.item_code,
				"fabric_warehouse": fabric.source_warehouse,
				"fabric_batch": fabric.batch_no,
				"fabric_qty_meters": fabric.qty,
				"sheeting_roll_item": sheeting.item_code,
				"sheeting_warehouse": sheeting.source_warehouse,
				"sheeting_batch": sheeting.batch_no,
				"sheeting_qty_meters": sheeting.qty,
			},
			update_modified=False,
		)
		updated += 1

	if updated:
		frappe.db.commit()
		print(
			"[setup_migrations] Migrated {0} Quilting Record(s) from child inputs to parent material fields.".format(
				updated
			)
		)
	else:
		print("[setup_migrations] No Quilting Record child-input migrations needed.")


def repair_job_order_workflow_statuses():
	"""Recompute Job Order workflow_status from linked conversion/assembly docs."""
	from pu_foam_master.pufm_manufacturing.doctype.pufm_job_order.pufm_job_order import (
		repair_job_order_workflow_status,
	)

	drop_legacy_quilting_status_column()
	repair_job_order_workflow_status()


def drop_legacy_quilting_status_column():
	"""Remove deprecated quilting_status from Pufm Job Order (replaced by progress section)."""
	if frappe.db.has_column("Pufm Job Order", "quilting_status"):
		frappe.db.sql("ALTER TABLE `tabPufm Job Order` DROP COLUMN `quilting_status`")
		frappe.db.commit()
		frappe.clear_cache(doctype="Pufm Job Order")
		print("[setup_migrations] Dropped legacy quilting_status from Pufm Job Order.")
