# Staff guide: Adjustment items (customer, supplier, rebate)

Use these **non-stock Service items** when the amount is a round figure (e.g. ₦5,000,000) and not tied to a physical product. Create them **once** on the live site, then reuse.

---

## Before you start

- You need **Item Manager** or **Stock Manager** rights (or System Manager).
- Get account names from your **Chart of Accounts** (company abbreviation, e.g. SF).
- **Rebate settlement** also needs **Rebate Expense Account** on **Pufm Manufacturing Settings** (PUFM Manager / System Manager).

---

## Item 1 — Rebate Settlement (required for automated quarterly rebate)

Used by **Rebate Settlement Tool** when you submit a period settlement. The system looks for an item named **`Rebate Settlement`** first.

| Field | What to set |
|-------|-------------|
| **Item Code** | `Rebate Settlement` (exact spelling) |
| **Item Name** | Rebate Settlement |
| **Item Group** | Services (or a group you use for non-stock) |
| **Is Stock Item** | **No** |
| **Is Sales Item** | **Yes** |
| **Is Purchase Item** | No |
| **Maintain Stock** | No |
| **Default Income Account** | Can be any sales account; settlement **overrides** with **Rebate Expense** from PUFM Settings |
| **Disabled** | No |
| **Product Bundle** | Must **not** exist with this same name |

**Steps:** Stock → Item → New → fill as above → Save.

---

## Item 2 — Customer credit note (manual adjustments)

For **customer credit** not tied to a specific return of goods — reduce what they owe or give account credit.

| Field | What to set |
|-------|-------------|
| **Item Code** | `Customer Account Credit` (or company standard name) |
| **Item Name** | Customer Account Credit |
| **Item Group** | Services |
| **Is Stock Item** | **No** |
| **Is Sales Item** | **Yes** |
| **Default Income Account** | Your policy account (e.g. sales deduction / commercial adjustment — ask Accounts Manager) |

**How to use in ERPNext**

1. **Selling → Sales Invoice → New**
2. Customer = the customer  
3. **Is Return** = Yes (credit note)  
4. One line: item **Customer Account Credit**, **Qty -1**, **Rate** = credit amount (e.g. 5000000)  
5. Check **Income Account** on the line matches policy  
6. Save → Submit  

**Note:** Quarterly **rebate** should use **Rebate Settlement Tool**, not this item, unless Accounts deliberately posts a manual rebate.

---

## Item 3 — Customer debit note (customer owes more)

For extra charge to customer without a normal product sale.

| Field | What to set |
|-------|-------------|
| **Item Code** | `Customer Account Debit` |
| **Item Name** | Customer Account Debit |
| **Item Group** | Services |
| **Is Stock Item** | **No** |
| **Is Sales Item** | **Yes** |
| **Default Income Account** | Appropriate income or charge account (Accounts Manager) |

**How to use**

1. **Sales Invoice** — **Is Return** = **No**  
2. One line: item **Customer Account Debit**, **Qty 1**, **Rate** = amount  
3. Submit  

---

## Item 4 — Supplier credit note (you owe supplier less / they credited you)

| Field | What to set |
|-------|-------------|
| **Item Code** | `Supplier Account Credit` |
| **Item Name** | Supplier Account Credit |
| **Item Group** | Services |
| **Is Stock Item** | **No** |
| **Is Purchase Item** | **Yes** |
| **Is Sales Item** | No |
| **Default Expense Account** | Adjustment or default purchase expense (Accounts Manager) |

**How to use**

1. **Buying → Purchase Invoice → New**  
2. Supplier = supplier  
3. **Is Return** = **Yes**  
4. One line: **Supplier Account Credit**, **Qty -1**, **Rate** = credit amount  
5. Submit  

---

## Item 5 — Supplier debit note (supplier bill / you owe more)

| Field | What to set |
|-------|-------------|
| **Item Code** | `Supplier Account Debit` |
| **Item Name** | Supplier Account Debit |
| **Item Group** | Services |
| **Is Stock Item** | **No** |
| **Is Purchase Item** | **Yes** |

**How to use**

1. **Purchase Invoice** — **Is Return** = **No**  
2. One line: **Supplier Account Debit**, **Qty 1**, **Rate** = amount  
3. Submit  

---

## Rebate settlement — staff process (end to end)

### Prerequisites on live server

1. **pu_foam_master** installed and migrated (rebate fields on Customer and Sales Invoice).  
2. **Pufm Manufacturing Settings** → **Rebate Expense Account** = valid **Expense** account.  
3. **Default VAT Rate (%)** set if invoices have no VAT tax rows (for ex-VAT rebate base).  
4. Item **`Rebate Settlement`** exists (see Item 1).  
5. Each distributor: **main + rebate wallet** customers set up per **STAFF_REBATE_CUSTOMER_SETUP.md**.  
6. Users have **PUFM Rebate Settlement User** (draft) / **Manager** (submit) as needed.

### Each quarter

1. Open **Rebate Settlement Tool** → set company, **From Date**, **To Date**.  
2. **Refresh eligible customers** — review turnover and %; adjust amounts if policy allows.  
3. Submit settlement (workflow if enabled).  
4. System creates **submitted credit note** sales invoices on each **rebate wallet** customer; links show on settlement rows.  
5. Qualifying sales invoices get **Rebate Settlement** tag so they are not settled twice.

### When customer wants rebate on main account

1. **Rebate Balance Transfer** → main customer, amount ≤ available rebate credit.  
2. Submit → **Journal Entry** moves balance rebate wallet → main trade receivable.  
3. Apply credit against sales using normal payment reconciliation / collection process.

---

## Quick reference table

| Purpose | Document | Return? | Item code (suggested) |
|---------|----------|---------|------------------------|
| Automated quarterly rebate | Done by Settlement Tool | Yes (SI) | Rebate Settlement |
| Manual customer credit | Sales Invoice | Yes | Customer Account Credit |
| Manual customer debit | Sales Invoice | No | Customer Account Debit |
| Manual supplier credit | Purchase Invoice | Yes | Supplier Account Credit |
| Manual supplier debit | Purchase Invoice | No | Supplier Account Debit |

---

## Governance

- Always enter a clear **remarks** / reason on manual credits and debits.  
- Manual adjustment items should not replace **Rebate Settlement Tool** for distributor quarter rebate.  
- Accounts Manager approves which **income/expense** accounts are used on manual items.