# Configuration decisions — round 6 (assignment, data quality, pricing, documents)

**Captured 2026-04-23**

| Topic | Decision |
|--------|----------|
| **Lead assignment** | **Line first** — lead is tagged **Production**, **MPS**, or **Radiology**, then **routed within** that pool (territory can still narrow **which** rep in that line). |
| **Duplicates** | **Both** — rules on **duplicate email** and **duplicate company** (block or warn per Zoho duplicate settings). |
| **Price books** | **One** price book (**IQD**) for **v1** — segment-specific books later if needed. |
| **Partners** | **Direct sales only** — no partner/dealer tracking in CRM for now. |
| **Documents** | **SharePoint / OneDrive** is system of record — CRM holds **links** (URL fields or notes), not large contract storage. |

## 1. Line-first assignment

1. **Lead** (and **Deal**) must carry **Line of business** = Production | MPS | Radiology (see [`LEADS-AND-DEALS.md`](./LEADS-AND-DEALS.md)).  
2. **Assignment:** within each line, use **territory** + **active user in that line** (workflow, assignment rule, or manual handoff).  
3. Document for managers: *tag line first, then assign owner inside that specialty.*

## 2. Duplicate rules

1. **Setup → Data Administration → Duplicate Management** (or **Duplicate Check** — label varies).  
2. Enable checks for **Leads** and **Contacts** on **Email**; **Accounts** (or Leads) on **Company / Account Name** as Zoho allows.  
3. Choose **Alert** vs **Block** per module — start with **alert** if reps fear blocking legitimate siblings.

## 3. Single price book

- Create **one** IQD **Price Book**; attach products to it.  
- When you add dealer/end-customer splits later, add **second** book without breaking v1 quotes.

## 4. SharePoint / OneDrive links

- Add **URL** or **custom link** fields on **Deal** / **Quote** / **Account** as needed, e.g. `Contract_Folder_URL`.  
- Train reps: **upload contract to SharePoint**, paste **link** in CRM.  
- Align with IT on **folder structure** and permissions.

## Related

- [`CONFIGURATION-ROUND5.md`](./CONFIGURATION-ROUND5.md) — territories, line discounts.  
- [`LEADS-AND-DEALS.md`](./LEADS-AND-DEALS.md) — line-of-business on Leads.  
- [`PROJECT-STATUS.md`](../PROJECT-STATUS.md)
