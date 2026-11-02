# Nigeria territory import (Regions → Zones → States)

ERPNext **Data Import → Territory** files for Happifoam / Solar Foam structure from REGIONS AND ZONES.

Use **three Insert imports in order** on live (see `TERRITORY_MIGRATION_ERPNext.md`):

1. `Territory_Import_Pass1_Regions.csv`
2. `Territory_Import_Pass2_Zones.csv`
3. `Territory_Import_Pass3_States.csv`

`Territory_Regions_Zones_Import.csv` is the full tree for reference or greenfield (single import fails link validation unless parents already exist).
