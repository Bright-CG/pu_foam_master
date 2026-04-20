import frappe
from frappe.model.document import Document
from frappe.utils import flt

class DensityConfiguration(Document):
    def validate(self):
        self.calculate_values()
        self.sync_existing_generated_items()

    def calculate_values(self):
        # Parent Calculations
        self.width_meters = flt(self.width_inches) * 0.0254
        self.height_meters = flt(self.height_inches) * 0.0254
        
        # New formula including calibration_factor
        self.output_rate_m3_per_min = (
            flt(self.conveyor_speed) * 
            flt(self.calibration_factor or 1.0) * 
            self.width_meters * 
            self.height_meters
        )

        # Child Table 1: Production Inputs
        for row in self.get("production_inputs"):
            row.flow_min = flt(row.flow_factor) * flt(row.set_at)
            if self.output_rate_m3_per_min:
                row.qty_per_m3 = row.flow_min / self.output_rate_m3_per_min
            else:
                row.qty_per_m3 = 0

        # Child Table 2: BOM Operations
        for row in self.get("bom_operations"):
            # operating_cost = (time / 60) * hour_rate
            row.operating_cost = (flt(row.time) / 60.0) * flt(row.hour_rate)

    @frappe.whitelist()
    def generate_variants(self):
        if not self.density_name:
            frappe.throw("Please set Density Name first.")
        
        if not self.standard_lengths:
            frappe.throw("Please enter Target Lengths (Inches).")

        lengths = [l.strip() for l in self.standard_lengths.split(",") if l.strip()]
        if not lengths:
            frappe.throw("No valid lengths found. Use commas to separate values.")

        created_count, updated_count, skipped_count = self._sync_items_for_lengths(
            lengths=lengths,
            create_missing=True,
        )

        frappe.db.commit()
        return {
            "created": created_count,
            "updated": updated_count,
            "skipped": skipped_count,
            "total_lengths": len(lengths),
        }

    def sync_existing_generated_items(self):
        if not self.density_name or not self.standard_lengths:
            return
        self._sync_items_for_lengths(
            lengths=[l.strip() for l in self.standard_lengths.split(",") if l.strip()],
            create_missing=False,
        )

    def _sync_items_for_lengths(self, lengths, create_missing):
        cbm_factor = _get_cbm_factor()
        item_group = _get_block_item_group()

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for length in _parse_lengths(lengths):
            item_name = _build_block_item_name(self.density_name, length)
            cbm = (flt(self.width_inches) * flt(self.height_inches) * length) / cbm_factor
            existing_item = frappe.db.exists("Item", item_name)

            if existing_item:
                item = frappe.get_doc("Item", item_name)
                changed = False
                desired_values = {
                    "custom_width": flt(self.width_inches),
                    "custom_height": flt(self.height_inches),
                    "custom_length": length,
                    "custom_cbm_value": cbm,
                }
                for fieldname, desired in desired_values.items():
                    if flt(item.get(fieldname)) != flt(desired):
                        item.set(fieldname, desired)
                        changed = True

                if changed:
                    item.save(ignore_permissions=True)
                    updated_count += 1
                else:
                    skipped_count += 1
                continue

            if not create_missing:
                skipped_count += 1
                continue

            item = frappe.new_doc("Item")
            item.item_code = item_name
            item.item_name = item_name
            item.item_group = item_group
            item.is_stock_item = 1
            item.stock_uom = "Nos"
            item.custom_width = flt(self.width_inches)
            item.custom_height = flt(self.height_inches)
            item.custom_length = length
            item.custom_cbm_value = cbm
            item.insert(ignore_permissions=True)
            created_count += 1

        return created_count, updated_count, skipped_count


def _format_length(length):
    return str(int(length)) if float(length).is_integer() else str(length)


def _build_block_item_name(density_name, length):
    return f"{density_name.strip()} by {_format_length(length)} Block"


def _parse_lengths(lengths):
    parsed = []
    for value in lengths:
        try:
            length = flt(value)
        except (TypeError, ValueError):
            continue
        if length > 0:
            parsed.append(length)
    return parsed


def _get_cbm_factor():
    cbm_factor = flt(frappe.db.get_single_value("Pufm Manufacturing Settings", "cbm_factor") or 61023.7)
    return cbm_factor if cbm_factor > 0 else 61023.7


def _get_block_item_group():
    return (
        frappe.db.get_single_value("Pufm Manufacturing Settings", "block_item_group")
        or "Products"
    )
