# Staff guide: PUFM Create Customer

Use **PUFM Create Customer** (PU Foam workspace) instead of **Customer → New** when you need a controlled **numeric main ID** and optional **REBATE{ID}** wallet.

## Before first use

1. **Pufm Manufacturing Settings** → set **Rebate Wallet Receivable Account** (e.g. `300-135 - Rebate Wallet Receivable - SF`).
2. Assign role **PUFM Customer Creator** to staff who onboard customers (PUFM Manager / System Manager also have access).

## Where to open it

- **PU Foam Master** workspace → **Financials & Rebates** → **PUFM Create Customer**
- **Accounting** workspace → link under **Customer** (added by migrate)

The link only shows for users who have **read** on **PUFM Create Customer** (same roles as create).

## Apply the role on a user

1. **User** → open the user (or **User List**).
2. **Roles** table → **Add Row** → **PUFM Customer Creator** → **Save**.
3. User **logs out and back in** (or hard refresh Desk).
4. Confirm **PU Foam Master** and **Accounting** show **PUFM Create Customer**; users without the role should not see it in workspace links or Awesome Bar search.

**Selling Settings:** ERPNext v15 only shows **Customer Name**, **Naming Series**, and **Auto Name** — there is no “Prompt” option. Staff should **not** use **Customer → New** for numeric / `REBATE` IDs; use **PUFM Create Customer** (it assigns IDs on submit regardless of that setting).

Optional: if someone must use **Customer → New**, set **Customer Naming By** to **Naming Series** and maintain a numeric-only series — still prefer **PUFM Create Customer**.

## Registration types

| Type | Creates |
|------|--------|
| **Trade Customer Only** | One main customer (numeric ID). No rebate wallet. |
| **Main and Rebate Wallet** | Main ID **N** and **REBATE{N}**, linked, distributor flag on. |
| **Rebate Wallet for Existing Main** | Only **REBATE{N}** for an existing main customer whose **name** is already **N** (numeric). |

## IDs

- Main: positive integer, no leading zeros (e.g. `330`, `921`).
- Rebate: always **REBATE** + same number (main `330` → `REBATE330`).
- If either ID already exists, save/submit shows an error; change the number and try again.

## After submit

- Open **Customer** masters for contacts, credit limit, territory, etc.
- This document **cannot be cancelled**; to change or delete customers, use normal **Customer** (if your role allows).

## Workflow

You can attach a standard ERPNext **Workflow** to **PUFM Create Customer** later for approval before submit; default is single-step **Submit** creates customers immediately.