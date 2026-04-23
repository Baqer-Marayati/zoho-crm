# Configuration decisions — round 8 (activities, close date, finance handoff, quotes, reviews)

**Captured 2026-04-23**

| Topic | Decision |
|--------|----------|
| **Activities** | **Strict** — reps must **log** calls / meetings (and use **tasks** as needed); consider **blocking** or **warning** key stage moves without a recent activity (blueprint / validation per edition). |
| **Close date** | **Required** on every **Deal**; **update** when stage or reality changes. |
| **Zoho Books** | **No** Books integration for **v1** — finance stays **outside** Zoho CRM for now. |
| **Payment terms** | **Yes** — **picklist** on **Quote** (and on **Deal** if useful for reporting). |
| **Pipeline review** | **Weekly** manager/rep pipeline review. |

## 1. Strict activity logging

1. Train: **every meaningful customer touch** → **log** Call or Meeting (or Task with outcome).  
2. Optional enforcement: **Blueprint** on Deals — e.g. cannot leave **Qualification** without **Call logged** (if your edition supports it).  
3. Managers use **Last Activity** / **Open Activities** in **weekly** review.

## 2. Close date discipline

- Set **Closing Date** **mandatory** on Deal layout.  
- Workflow or habit: when **Stage** moves to late stages, **refresh** close date if the quarter slipped.

## 3. No Books v1

- **Closed Won** in CRM does **not** auto-create invoice.  
- Handoff to finance via **your current process** (email, export, ERP).  
- Revisit **Zoho Books** or ERP connector in a later phase.

## 4. Payment terms picklist

- **Quote:** add **Payment_Terms** picklist (e.g. *Cash on delivery*, *Net 30*, *Milestones*, *Letter of credit* — tune to your business).  
- Optionally mirror on **Deal** for pipeline reporting before quote exists.

## 5. Weekly pipeline review

- Fixed **calendar** slot; review **stage**, **amount**, **close date**, **next step**, **last activity**.  
- Use Zoho **pipeline** view or dashboard filtered by **team / territory / line**.

## Related

- [`CONFIGURATION-ROUND7.md`](./CONFIGURATION-ROUND7.md) — pilot, MFA.  
- [`LEADS-AND-DEALS.md`](./LEADS-AND-DEALS.md)  
- [`PRODUCTS-AND-QUOTES.md`](./PRODUCTS-AND-QUOTES.md)  
- [`PROJECT-STATUS.md`](../PROJECT-STATUS.md)
