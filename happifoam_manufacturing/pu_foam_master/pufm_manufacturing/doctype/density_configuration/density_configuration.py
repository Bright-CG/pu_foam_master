import frappe
from frappe.model.document import Document
from frappe.utils import flt

class DensityConfiguration(Document):
    def validate(self):
        self.calculate_values()

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
            frappe.throw("Please select a Density Name (Item Template) first.")
        
        if not self.standard_lengths:
            frappe.throw("Please enter Target Lengths (Inches).")

        lengths = [l.strip() for l in self.standard_lengths.split(",") if l.strip()]
        if not lengths:
            frappe.throw("No valid lengths found. Use commas to separate values.")

        template = frappe.get_doc("Item", self.density_name)
        if not template.has_variants:
            frappe.throw(f"Item {self.density_name} must be a Template (Has Variants must be checked).")

        count = 0
        for length_str in lengths:
            try:
                length = flt(length_str)
            except ValueError:
                continue

            # Naming: {Density}-{Width}x{Height}x{Length}
            w = int(flt(self.width_inches))
            h = int(flt(self.height_inches))
            l = int(length)
            
            variant_code = f"{template.item_code}-{w}x{h}x{l}"
            
            # Calculate CBM: (Width * Height * Length) / 61023.74
            cbm = (flt(self.width_inches) * flt(self.height_inches) * length) / 61023.74

            if frappe.db.exists("Item", variant_code):
                # Update existing
                item = frappe.get_doc("Item", variant_code)
                item.update({
                    "width": flt(self.width_inches),
                    "height": flt(self.height_inches),
                    "length": length,
                    "cbm_value": cbm
                })
                item.save(ignore_permissions=True)
            else:
                # Create new
                item = frappe.new_doc("Item")
                item.item_code = variant_code
                item.item_name = variant_code
                item.variant_of = self.density_name
                item.is_stock_item = 1
                item.stock_uom = template.stock_uom or "Nos"
                item.item_group = template.item_group
                item.width = flt(self.width_inches)
                item.height = flt(self.height_inches)
                item.length = length
                item.cbm_value = cbm
                
                item.insert(ignore_permissions=True)
            
            count += 1

        frappe.db.commit()
        return count
