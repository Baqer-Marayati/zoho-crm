# Configuration decisions — round 3

**Captured 2026-04-23**

| Topic | Decision |
|--------|----------|
| **Tax** | **Manual** on each quote for now — automate with tax rules / Books later when finance defines them. |
| **Inventory** | **No** stock or availability in CRM **v1** — quotes are **not** inventory-constrained. |
| **Email** | **Microsoft 365** / Outlook — sync CRM with **Outlook** (or Zoho’s Microsoft integration path your admin prefers). |
| **Data migration** | **Small** import (**under ~500** rows) — plan a **controlled CSV import** (Leads and/or Accounts/Contacts). |
| **Power BI** | **Later** / not a near-term priority — **Zoho** views & reports first. |

## 1. Tax (manual)

- On **Quote** layout, keep **tax** fields visible; reps enter per quote or line as your process requires.  
- Document in internal training: *“v1 = manual tax; finance will define rules later.”*  
- When ready: **Zoho Books** integration or CRM **tax preferences** / line-level tax — revisit with finance.

## 2. Inventory (out of scope v1)

- Do **not** block quotes on stock in CRM for the first release.  
- If you add **Zoho Inventory** or ERP later, define whether CRM stays **non-binding** or becomes **ATP-aware**.

## 3. Microsoft 365 email

1. **Setup → Channels → Email** (wording may vary) — configure **Microsoft** / **Outlook** integration.  
2. Use an **admin-consented** app registration if your IT requires it (tenant policy).  
3. Confirm **sync direction** (emails to/from Leads/Contacts/Deals) per privacy policy.  
4. Train reps: **log customer email** from CRM where possible so history attaches to records.

*Exact clicks change with Zoho UI; search Setup for **Microsoft** or **Outlook**.*

## 4. Small migration (~500 rows)

1. **Freeze** a **CSV** per module (Leads, Accounts, Contacts — not all at once if messy).  
2. Map columns to **API names** or use Zoho import wizard mapping.  
3. Run **dry run** / small batch first (e.g. 10 rows), fix, then full file.  
4. Optional: one-off scripts under `tools/zoho/` for validation — add when you have the CSV schema.  
5. **Duplicates:** decide rule (email, company name) before import.

## 5. Power BI (deferred)

- No dataset work until CRM objects and fields stabilize.  
- When you return to it: see [`POWER-BI-AND-LICENSING.md`](./POWER-BI-AND-LICENSING.md).  
- Until then: **Zoho** dashboards + **pipeline** views for managers.

## Related

- [`PRODUCTS-AND-QUOTES.md`](./PRODUCTS-AND-QUOTES.md) — IQD, catalog, quotes.  
- [`LEADS-AND-DEALS.md`](./LEADS-AND-DEALS.md) — conversion, lost reasons.  
- [`PROJECT-STATUS.md`](../PROJECT-STATUS.md)
