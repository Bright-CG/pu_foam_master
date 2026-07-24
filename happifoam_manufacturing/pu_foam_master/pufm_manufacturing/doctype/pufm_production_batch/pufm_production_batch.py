import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import cint, flt

from pu_foam_master.pufm_manufacturing.utils.density_bom import (
	PRECISION,
	assert_user_can_access_company,
	get_active_bom,
	get_preferred_company,
	get_user_allowed_companies,
	resolve_warehouse_for_company,
	warehouse_belongs_to_company,
)


# workflow_state -> roles allowed to enter that state
WORKFLOW_TRANSITION_ROLES = {
	"Pending MD Approval": {"Manufacturing Manager", "System Manager"},
	"Pending Store Confirmation": {"Manufacturing Manager", "CEO/MD", "System Manager"},
	"Completed": {"Store Manager", "System Manager"},
}


class PufmProductionBatch(Document):
	def autoname(self):
		self.name = make_autoname(self.naming_series or "PB-.YYYY.-.MM.-.###")
		self.batch_id = self.name

	def validate(self):
		if self.name:
			self.batch_id = self.name
		self._ensure_company()
		assert_user_can_access_company(self.company, action="save Production Batch for")
		self._enforce_workflow_transition_security()

	def before_save(self):
		if self.is_new():
			return

		previous_state = frappe.db.get_value(self.doctype, self.name, "workflow_state")
		if previous_state == self.workflow_state:
			return

		# Scrap by-product + chemical consumption + FG are booked together on Completed
		# so cost apportionment balances in a single Stock Entry.
		if self.workflow_state == "Completed":
			self.create_manufacture_cost_entry()

	def _ensure_company(self):
		if not self.company:
			self.company = get_preferred_company()
		if not self.company:
			frappe.throw(_("Company is required."))

	def _enforce_workflow_transition_security(self):
		"""Block unauthorized workflow_state transitions (Python state machine)."""
		before = self.get_doc_before_save()
		old_state = before.workflow_state if before else None
		new_state = self.workflow_state

		if new_state == old_state:
			return

		if not new_state or new_state == "Draft":
			return

		required_roles = WORKFLOW_TRANSITION_ROLES.get(new_state)
		if not required_roles:
			return

		if self._user_has_any_role(required_roles):
			return

		roles_label = " or ".join(sorted(required_roles))
		raise frappe.PermissionError(
			_(
				"You cannot move Production Batch to '{0}'. "
				"Required role: {1}."
			).format(new_state, roles_label)
		)

	@staticmethod
	def _user_has_any_role(required_roles):
		user = frappe.session.user
		if user == "Administrator":
			return True
		user_roles = set(frappe.get_roles(user))
		return bool(user_roles.intersection(required_roles))

	def _get_linked_runs(self):
		return frappe.get_all(
			"Pufm Density Run",
			filters={"parent_batch": self.name},
			fields=[
				"name",
				"density_config",
				"minutes_run",
				"scrap_weight_kg",
				"actual_cbm",
				"expected_cbm",
				"target_warehouse",
			],
		)

	def update_totals(self):
		"""Aggregates totals from all linked Density Runs."""
		runs = self._get_linked_runs()

		self.total_actual_cbm = 0
		self.total_scrap_weight = 0
		self.total_produced_qty = 0

		run_names = [run.name for run in runs]
		if not run_names:
			self.save(ignore_permissions=True)
			return

		for run in runs:
			self.total_actual_cbm += flt(run.actual_cbm)
			self.total_scrap_weight += flt(run.scrap_weight_kg)

		produced_blocks = frappe.get_all(
			"Pufm Produced Block",
			filters={"parent": ["in", run_names], "parenttype": "Pufm Density Run"},
			fields=["quantity"],
		)
		self.total_produced_qty = sum(flt(b.quantity) for b in produced_blocks)

		self.save(ignore_permissions=True)
		frappe.db.commit()

	def _get_settings(self):
		return frappe.get_single("Pufm Manufacturing Settings")

	def _require_company(self):
		self._ensure_company()
		assert_user_can_access_company(
			self.company, action="post stock for Production Batch against"
		)
		return self.company

	def _company_warehouse(self, preferred, name_contains, label):
		company = self._require_company()
		warehouse = resolve_warehouse_for_company(preferred, company, name_contains=name_contains)
		if not warehouse:
			frappe.throw(
				_(
					"Could not resolve {0} warehouse for company {1}. "
					"Set it in Pufm Manufacturing Settings or create a matching warehouse."
				).format(label, company)
			)
		if not warehouse_belongs_to_company(warehouse, company):
			frappe.throw(
				_("Warehouse {0} does not belong to company {1}.").format(warehouse, company)
			)
		return warehouse

	def _resolve_wip_warehouse(self, settings):
		company = self._require_company()
		wip_warehouse = (
			resolve_warehouse_for_company(
				settings.default_wip_warehouse, company, name_contains="Goods In Transit"
			)
			or resolve_warehouse_for_company(
				settings.default_wip_warehouse, company, name_contains="Work In Progress"
			)
			or resolve_warehouse_for_company(
				settings.default_wip_warehouse, company, name_contains="WIP"
			)
		)
		if not wip_warehouse or not warehouse_belongs_to_company(wip_warehouse, company):
			frappe.throw(
				_(
					"Could not resolve WIP warehouse for company {0}. "
					"Set Default WIP Warehouse in Pufm Manufacturing Settings."
				).format(company)
			)
		return wip_warehouse

	def create_manufacture_cost_entry(self):
		"""
		Single Repack Stock Entry with by-product cost apportionment:
		  Sum(Source RM) + Sum(Additional Op Costs) = Sum(Scrap) + Sum(Block FG)
		"""
		if self.chemical_consumption_entry or self.fg_receipt_entry:
			return

		runs = self._get_linked_runs()
		if not runs:
			frappe.throw(_("No Density Runs linked to this Production Batch."))

		company = self._require_company()
		settings = self._get_settings()

		scrap_output_rate = flt(getattr(settings, "scrap_output_rate", 0) or 0)
		scrap_item = getattr(settings, "scrap_item", None) or frappe.db.get_single_value(
			"Stock Settings", "scrap_item"
		)
		labour_account = getattr(settings, "labour_absorption_account", None)
		default_brand = getattr(settings, "default_brand", None)

		wip_warehouse = self._resolve_wip_warehouse(settings)
		default_fg = self._company_warehouse(
			settings.default_fg_warehouse, "Finished Goods", "Finished Goods"
		)
		scrap_warehouse = self._company_warehouse(
			settings.default_scrap_warehouse, "Scrap", "Scrap"
		)

		entry = frappe.new_doc("Stock Entry")
		entry.company = self.company
		entry.stock_entry_type = "Repack"
		entry.purpose = "Repack"
		entry.posting_date = self.posting_date
		entry.set_posting_time = 1

		total_source_amount = 0.0
		total_additional = 0.0
		total_target_amount = 0.0

		for run in runs:
			run_doc = frappe.get_doc("Pufm Density Run", run.name)
			costing = self._calculate_run_costing(
				run_doc=run_doc,
				wip_warehouse=wip_warehouse,
				scrap_output_rate=scrap_output_rate,
			)

			# --- Source chemicals ---
			for chem in costing["chemicals"]:
				qty = flt(chem["qty"], PRECISION)
				rate = flt(chem["rate"], PRECISION)
				amount = flt(qty * rate, PRECISION)
				if qty <= 0:
					continue
				entry.append(
					"items",
					{
						"item_code": chem["item_code"],
						"qty": qty,
						"s_warehouse": wip_warehouse,
						"uom": chem["uom"],
						"stock_uom": chem["uom"],
						"conversion_factor": 1,
						"basic_rate": rate,
						"valuation_rate": rate,
						"allow_zero_valuation_rate": 0,
						"set_basic_rate_manually": 1,
					},
				)
				total_source_amount = flt(total_source_amount + amount, PRECISION)

			# --- Additional operating cost ---
			run_op_cost = flt(costing["run_op_cost"], PRECISION)
			if run_op_cost > 0:
				if not labour_account:
					frappe.throw(
						_(
							"Set Labour Absorption Account in Pufm Manufacturing Settings "
							"to absorb operating costs."
						)
					)
				entry.append(
					"additional_costs",
					{
						"expense_account": labour_account,
						"description": _("Operating Costs for {0}").format(run.density_config),
						"amount": run_op_cost,
					},
				)
				total_additional = flt(total_additional + run_op_cost, PRECISION)

			# --- Target scrap (by-product) ---
			scrap_qty = flt(costing["scrap_qty"], PRECISION)
			if scrap_qty > 0:
				if not scrap_item:
					frappe.throw(
						_("Set Scrap Item in Pufm Manufacturing Settings to receive scrap by-product.")
					)
				scrap_amount = flt(scrap_qty * scrap_output_rate, PRECISION)
				entry.append(
					"items",
					{
						"item_code": scrap_item,
						"qty": scrap_qty,
						"t_warehouse": scrap_warehouse,
						"basic_rate": scrap_output_rate,
						"valuation_rate": scrap_output_rate,
						"allow_zero_valuation_rate": 1 if scrap_output_rate <= 0 else 0,
						"set_basic_rate_manually": 1,
					},
				)
				total_target_amount = flt(total_target_amount + scrap_amount, PRECISION)

			# --- Target finished blocks ---
			target_wh = (run.target_warehouse or default_fg or "").strip()
			if target_wh and not warehouse_belongs_to_company(target_wh, company):
				target_wh = (
					resolve_warehouse_for_company(
						target_wh, company, name_contains="Finished Goods"
					)
					or default_fg
				)
			if not target_wh or not warehouse_belongs_to_company(target_wh, company):
				frappe.throw(
					_(
						"Target warehouse on Density Run {0} does not belong to company {1}."
					).format(run.name, company)
				)

			cost_per_cbm = flt(costing["cost_per_cbm"], PRECISION)
			for block in costing["blocks"]:
				qty = flt(block["quantity"], PRECISION)
				if qty <= 0:
					continue
				serial_qty = cint(qty)
				if serial_qty <= 0 or abs(qty - serial_qty) > 0.0001:
					frappe.throw(
						_(
							"Finished block quantity for {0} must be a whole number "
							"to generate serial numbers (got {1})."
						).format(block["block_item"], qty)
					)

				item_code = block["block_item"]
				self._ensure_block_item_traceability(item_code, default_brand)
				batch_no = self._ensure_block_batch(item_code)
				serial_string = self._build_block_serials(item_code, batch_no, serial_qty)

				unit_cbm = flt(block["unit_cbm"], PRECISION)
				block_unit_cost = flt(cost_per_cbm * unit_cbm, PRECISION)
				block_amount = flt(block_unit_cost * qty, PRECISION)
				row = {
					"item_code": item_code,
					"qty": qty,
					"t_warehouse": target_wh,
					"basic_rate": block_unit_cost,
					"valuation_rate": block_unit_cost,
					"amount": block_amount,
					"allow_zero_valuation_rate": 1 if block_unit_cost <= 0 else 0,
					"set_basic_rate_manually": 1,
					# v15: required so batch_no / serial_no are applied on submit
					"use_serial_batch_fields": 1,
					"batch_no": batch_no,
					"serial_no": serial_string,
				}
				entry.append("items", row)
				total_target_amount = flt(total_target_amount + block_amount, PRECISION)

		if not entry.get("items"):
			frappe.throw(_("Nothing to post — no chemicals or finished blocks found on Density Runs."))

		# Enforce double-entry balance (within rounding tolerance)
		left = flt(total_source_amount + total_additional, PRECISION)
		right = flt(total_target_amount, PRECISION)
		if abs(left - right) > 0.05:
			# Absorb residual into last FG target row so ERPNext accepts the voucher
			residual = flt(left - right, PRECISION)
			for row in reversed(entry.items):
				if row.t_warehouse and row.qty:
					# Prefer block rows over scrap for residual
					if scrap_item and row.item_code == scrap_item:
						continue
					new_amount = flt(flt(row.basic_rate) * flt(row.qty) + residual, PRECISION)
					new_rate = flt(new_amount / flt(row.qty), PRECISION) if flt(row.qty) else 0
					row.basic_rate = new_rate
					row.valuation_rate = new_rate
					row.amount = new_amount
					total_target_amount = flt(total_target_amount + residual, PRECISION)
					break

		entry.insert(ignore_permissions=True)
		entry.submit()

		self.chemical_consumption_entry = entry.name
		self.fg_receipt_entry = entry.name
		if scrap_item and any(
			flt(r.scrap_weight_kg) > 0 for r in runs
		):
			self.scrap_stock_entry = entry.name

	def _ensure_block_item_traceability(self, item_code, default_brand=None):
		"""Ensure FG block Item accepts batch + serial (and optional brand)."""
		if not item_code or not frappe.db.exists("Item", item_code):
			frappe.throw(_("Block Item {0} does not exist.").format(item_code))

		item = frappe.get_doc("Item", item_code)
		changed = False
		for fieldname, value in (
			("has_batch_no", 1),
			("create_new_batch", 1),
			("has_serial_no", 1),
			("serial_no_series", ""),
		):
			if item.get(fieldname) != value:
				item.set(fieldname, value)
				changed = True
		if default_brand and item.brand != default_brand:
			item.brand = default_brand
			changed = True
		if changed:
			item.save(ignore_permissions=True)

	def _ensure_block_batch(self, item_code):
		"""
		Create/return a Batch for this Production Batch + block Item.

		ERPNext Batch.batch_id is globally unique and linked to one Item, so the
		Production Batch name is used when free; otherwise `{PB}-{item_code}`.
		"""
		preferred = self.name
		existing_item = frappe.db.get_value("Batch", preferred, "item")
		if existing_item == item_code:
			return preferred
		if existing_item and existing_item != item_code:
			batch_id = f"{self.name}-{item_code}"
		else:
			batch_id = preferred

		if frappe.db.exists("Batch", batch_id):
			batch_item = frappe.db.get_value("Batch", batch_id, "item")
			if batch_item and batch_item != item_code:
				batch_id = f"{self.name}-{item_code}"
			else:
				return batch_id

		if not frappe.db.exists("Batch", batch_id):
			new_batch = frappe.new_doc("Batch")
			new_batch.batch_id = batch_id
			new_batch.item = item_code
			new_batch.reference_doctype = "Pufm Production Batch"
			new_batch.reference_name = self.name
			new_batch.insert(ignore_permissions=True)

		return batch_id

	@staticmethod
	def _build_block_serials(item_code, batch_id, qty):
		"""Newline-separated serials: {item_code}-{batch_id}-{n}."""
		serial_nos = [f"{item_code}-{batch_id}-{i}" for i in range(1, cint(qty) + 1)]
		return "\n".join(serial_nos)

	def _calculate_run_costing(self, run_doc, wip_warehouse, scrap_output_rate):
		"""Per-density-run RM + Op - Scrap → Cost_Per_CBM."""
		if not run_doc.density_config:
			frappe.throw(_("Density Run {0} has no Density Configuration.").format(run_doc.name))

		density_company = frappe.db.get_value(
			"Density Configuration", run_doc.density_config, "company"
		)
		if density_company and density_company != self.company:
			frappe.throw(
				_(
					"Density Configuration {0} belongs to company {1}, "
					"but this Production Batch is for {2}."
				).format(run_doc.density_config, density_company, self.company)
			)

		active_bom = get_active_bom(density_config=run_doc.density_config)
		basis_cbm = flt(run_doc.actual_cbm) or flt(run_doc.expected_cbm)
		if basis_cbm <= 0:
			frappe.throw(
				_("Density Run {0} has no Actual/Expected CBM for chemical consumption.").format(
					run_doc.name
				)
			)

		# 1) Raw material cost from Active BOM qtys × WIP valuation
		chemicals = []
		run_rm_cost = 0.0
		for bom_item in active_bom.items:
			if not bom_item.item_code:
				continue
			qty = flt(flt(bom_item.qty) * basis_cbm, PRECISION)
			if qty <= 0:
				continue
			rate = _get_warehouse_valuation_rate(bom_item.item_code, wip_warehouse)
			if rate <= 0:
				frappe.throw(
					_(
						"Valuation Rate missing for {0} in warehouse {1}. "
						"Inject WIP stock before completing the batch."
					).format(bom_item.item_code, wip_warehouse)
				)
			uom = (
				bom_item.uom
				or frappe.db.get_value("Item", bom_item.item_code, "stock_uom")
				or "Nos"
			)
			amount = flt(qty * rate, PRECISION)
			run_rm_cost = flt(run_rm_cost + amount, PRECISION)
			chemicals.append(
				{"item_code": bom_item.item_code, "qty": qty, "rate": rate, "uom": uom}
			)

		# 2) Operating cost from Active BOM operations (fallback: Density bom_operations)
		operations = list(active_bom.get("operations") or [])
		if not operations:
			density_doc = frappe.get_doc("Density Configuration", run_doc.density_config)
			operations = list(density_doc.get("bom_operations") or [])

		minutes_run = flt(run_doc.minutes_run)
		run_op_cost = 0.0
		for op in operations:
			hour_rate = flt(op.get("hour_rate") if isinstance(op, dict) else getattr(op, "hour_rate", 0))
			run_op_cost = flt(run_op_cost + (minutes_run / 60.0) * hour_rate, PRECISION)

		# 3) Scrap value (by-product credit)
		scrap_qty = flt(run_doc.scrap_weight_kg)
		run_scrap_value = flt(scrap_qty * flt(scrap_output_rate), PRECISION)

		# 4) Net cost to allocate to foam blocks
		net_run_cost = flt(run_rm_cost + run_op_cost - run_scrap_value, PRECISION)

		# 5) Produced blocks / total CBM
		blocks = []
		run_total_cbm = 0.0
		for block in run_doc.get("produced_blocks_table") or []:
			if not block.block_item:
				continue
			unit_cbm = flt(block.unit_cbm)
			if unit_cbm <= 0:
				unit_cbm = flt(
					frappe.db.get_value("Item", block.block_item, "custom_cbm_value")
				)
			qty = flt(block.quantity)
			total_cbm = flt(block.total_cbm) or flt(unit_cbm * qty, PRECISION)
			run_total_cbm = flt(run_total_cbm + total_cbm, PRECISION)
			blocks.append(
				{
					"block_item": block.block_item,
					"quantity": qty,
					"unit_cbm": unit_cbm,
					"total_cbm": total_cbm,
				}
			)

		if run_total_cbm <= 0:
			frappe.throw(
				_("Density Run {0} has no produced block CBM to absorb net cost.").format(
					run_doc.name
				)
			)

		cost_per_cbm = flt(net_run_cost / run_total_cbm, PRECISION)

		return {
			"chemicals": chemicals,
			"run_rm_cost": run_rm_cost,
			"run_op_cost": run_op_cost,
			"scrap_qty": scrap_qty,
			"run_scrap_value": run_scrap_value,
			"net_run_cost": net_run_cost,
			"run_total_cbm": run_total_cbm,
			"cost_per_cbm": cost_per_cbm,
			"blocks": blocks,
		}


def _get_warehouse_valuation_rate(item_code, warehouse):
	rate = flt(
		frappe.db.get_value(
			"Bin", {"item_code": item_code, "warehouse": warehouse}, "valuation_rate"
		)
	)
	if rate > 0:
		return rate
	return flt(frappe.db.get_value("Item", item_code, "valuation_rate"))


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def company_query(doctype, txt, searchfield, start, page_len, filters):
	"""Link query: only companies the current user is allowed to use."""
	allowed = get_user_allowed_companies()
	if not allowed:
		return []

	placeholders = ", ".join(["%s"] * len(allowed))
	return frappe.db.sql(
		f"""
		SELECT name
		FROM `tabCompany`
		WHERE name IN ({placeholders})
			AND name LIKE %s
		ORDER BY name
		LIMIT %s, %s
		""",
		tuple(allowed) + (f"%{txt}%", start, page_len),
	)


@frappe.whitelist()
def get_allowed_companies_for_user():
	"""Frontend helper: companies the current user may select on Production Batch."""
	return get_user_allowed_companies()
