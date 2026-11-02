# ERPNext territory migration (Regions → Zones → States)

Source: `REGIONS AND ZONES.docx`  
Target hierarchy:

```text
All Territories
└── Nigeria
    ├── Northern Region → Zone N1…N6 → states
    ├── Central Region → Zone C1…C4 → states
    ├── South West Region → Zone SW1…SW3 → states
    └── South East, South South Region → Zone SES1…SES5 → states
```

State names match your original import (`LAGOS`, `FCT`, `CROSS RIVER`, etc.).

---

## Can Data Import rename territories?

**Mostly no.**

| Change | Data Import |
|--------|-------------|
| **New** group (e.g. `Zone N1`) | **Insert** works |
| **Same name**, new **Parent Territory** (e.g. `LAGOS` parent `South West` → `Zone SW1`) | **Update** works if `Zone SW1` already exists |
| **Rename** (`South West` → `South West Region`, `North East` → delete) | Import does **not** rename; old doc names stay until you **Rename** in desk or **delete** unused nodes |
| **Delete** old groups | Not via CSV; use **Territory** list or Tree → delete empty groups |

If **Customers**, **Addresses**, or **Sales** already use old territories, do **not** bulk-delete states—only **update parent** on state rows.

---

## Recommended path (live site, you already imported `Territory.csv`)

### Step 1 — Insert new groups only

**Data Import → Territory → Insert**

File: **`Territory_New_Groups_Insert_Only.csv`**

Creates zones + `South West Region` + `South East, South South Region`.  
(`Northern Region` and `Central Region` already exist on your file.)

### Step 2 — Move states under zones

**Data Import → Territory → Update** (tick “Do not create new records” / update only)

File: **`Territory_States_Parent_Update_Only.csv`**

Maps each state to the correct zone parent.

### Step 3 — Remove obsolete **empty** groups

After Step 2, these should have **no children** (confirm in **Territory Tree**):

- `South E & S South`
- `South East`
- `South South`
- `North East`
- `North West`
- `South West` (old name—not `South West Region`)

Delete them manually (Setup → Selling → Territory → tree).  
If ERPNext blocks delete (“linked”), check **Customer Territory** / **Address** links first.

### Step 4 — Optional cleanup

- **`Rest Of The World`**: kept in full CSV under `All Territories`; leave as-is if you use it.
- Typo in doc (“NORTHER REGION”): import uses **`Northern Region`** (correct spelling).

---

## Fresh import (empty territory tree under Nigeria)

If nothing is linked yet, you can delete all custom territories under **Nigeria** (and old region groups), then:

**Data Import → Territory → Insert**

File: **`Territory_Regions_Zones_Import.csv`** (complete tree in one file).

---

## Files in Downloads

| File | Use |
|------|-----|
| `Territory_Regions_Zones_Import.csv` | Full tree (new site or after cleanup) |
| `Territory_New_Groups_Insert_Only.csv` | Step 1 on existing site |
| `Territory_States_Parent_Update_Only.csv` | Step 2 update parents |
| `TERRITORY_MIGRATION_ERPNext.md` | This guide |

Import columns: **Territory Name**, **Parent Territory**, **Is Group** (`1` = group, `0` = leaf state).
