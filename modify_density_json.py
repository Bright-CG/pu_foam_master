import json
import os

filepath = '/Users/bright/Development/PU_Foam/pu_foam_master/pu_foam_master/pufm_manufacturing/doctype/density_configuration/density_configuration.json'

with open(filepath, 'r') as f:
    data = json.load(f)

# Add blow_index, calibration_factor, and bom_operations to fields
fields = data.get('fields', [])

# Check if fields already exist
blow_index_exists = any(f.get('fieldname') == 'blow_index' for f in fields)
calibration_factor_exists = any(f.get('fieldname') == 'calibration_factor' for f in fields)
bom_operations_exists = any(f.get('fieldname') == 'bom_operations' for f in fields)

new_fields = []
for field in fields:
    new_fields.append(field)
    if field.get('fieldname') == 'conveyor_speed' and not calibration_factor_exists:
        new_fields.append({
            "fieldname": "calibration_factor",
            "fieldtype": "Float",
            "label": "Calibration Factor",
            "default": "1.0"
        })
        new_fields.append({
            "fieldname": "blow_index",
            "fieldtype": "Float",
            "label": "Blow Index"
        })
    if field.get('fieldname') == 'output_rate_m3_per_min':
        field['label'] = 'Output Rate m3 per Min'

    if field.get('fieldname') == 'production_inputs' and not bom_operations_exists:
        # After production inputs, we add bom_operations table and its section break
        new_fields.append({
            "fieldname": "operations_sb",
            "fieldtype": "Section Break",
            "label": "Operations"
        })
        new_fields.append({
            "fieldname": "bom_operations",
            "fieldtype": "Table",
            "label": "BOM Operations",
            "options": "PUFM BOM Operation"
        })

data['fields'] = new_fields
data['field_order'] = [f.get('fieldname') for f in new_fields if f.get('fieldname')]

with open(filepath, 'w') as f:
    json.dump(data, f, indent=1)
print("Updated density_configuration.json")
