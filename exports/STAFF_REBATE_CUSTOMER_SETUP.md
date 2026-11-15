# Staff guide: Main customer and rebate wallet (ERPNext)

Plain steps for Solar Foam / PU Foam. Each **distributor** who earns quarterly rebate needs **two Customer records** and **two receivable accounts** in the chart of accounts.

---

## What you are setting up

| Record | Meaning |
|--------|--------|
| **Main customer** | Normal buyer — sales invoices, trade debtors balance (they owe you, or they have advance credit). |
| **Rebate wallet customer** | Same business partner, separate customer code — only for **rebate balance** (money the company owes them from rebate). |
| **Rebate Wallet Receivable** (GL account) | Ledger account for rebate wallet balances — **not** the same as Trade Debtors. |

The system does **not** use one customer for both. It uses two Customers linked to each other, each with its own receivable account on the **Accounting** tab.

---

## One-time: chart of accounts

1. Ask IT or Accounts to confirm **Rebate Wallet Receivable** exists (e.g. account number **200-18** under the same group as Trade Debtors).
2. If it is missing, IT can run on the server:
   ```bash
   bench --site <your-site> execute pu_foam_master.rebate.coa_setup.ensure_rebate_wallet_receivable_account
   ```

---

## For each new distributor with rebate

### Step 1 — Create or open the **main** customer

1. Go to **Selling → Customer → New** (or open existing main account).
2. Fill normal details (name, territory, customer group, etc.).
3. On **PUFM / Rebate** fields (or Rebate section):
   - **Is Distributor** = Yes  
   - Do **not** mark as Rebate Wallet Account.
4. **Accounting** tab → **Accounts** → add row:
   - **Company** = your company  
   - **Account** = **Trade Debtors** (or company default receivable for sales)  
5. Set **Rebate Tier** or rebate percentages as your policy requires.
6. **Save** (do not set Linked Rebate Customer until the wallet customer exists).

### Step 2 — Create the **rebate wallet** customer

1. **Selling → Customer → New**.
2. **Customer name** — make it clear it is rebate, e.g. `BRIGHTER PRESS LTD - Rebate` or code like main customer with `-REB` suffix.
3. Rebate fields:
   - **Rebate Wallet Account** (or Is Rebate Account) = Yes  
   - **Is Distributor** = No (system may clear this)  
   - **Linked Main Customer** = select the **main** customer from Step 1  
4. **Accounting** tab → **Accounts** → add row:
   - **Company** = your company  
   - **Account** = **Rebate Wallet Receivable** (not Trade Debtors)  
5. **Save**.

### Step 3 — Link back on the main customer

1. Open the **main** customer again.
2. **Linked Rebate Customer** = select the rebate wallet customer from Step 2.
3. **Save**.

### Step 4 — Checklist (both must pass)

| Check | Main customer | Rebate wallet customer |
|-------|----------------|-------------------------|
| Receivable account | Trade Debtors | Rebate Wallet Receivable |
| Link | Has Linked Rebate Customer | Has Linked Main Customer |
| Flags | Is Distributor | Rebate Wallet Account |

If both customers use the **same** receivable account, **Rebate Settlement** will stop with an error. Fix the Accounting tab before settling.

---

## What happens in the system (short)

1. **Quarter** — **Rebate Settlement Tool** calculates from sales, then on submit posts a **credit note** to the **rebate wallet customer** (adds rebate credit there).
2. **Later** — **Rebate Balance Transfer** moves credit from rebate wallet to **main** customer so they can use it against normal invoices.

Main customer sales invoices are **not** credited at settlement; only the **rebate wallet** customer is.

---

## Common mistakes

- Only one customer record for both trade and rebate.  
- Rebate wallet customer using Trade Debtors on Accounting tab.  
- Main customer missing **Linked Rebate Customer**.  
- Rebate wallet missing **Linked Main Customer**.

---

## Who to contact

- **Customer master / links** — Sales admin + Accounts Manager.  
- **Rebate Wallet Receivable account** — Accounts Manager / IT.  
- **Rebate % and settlement** — Finance (Rebate Settlement Tool roles).