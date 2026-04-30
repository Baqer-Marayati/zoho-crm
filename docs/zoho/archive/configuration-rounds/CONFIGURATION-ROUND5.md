# Configuration decisions — round 5

**Captured 2026-04-23**

| Topic | Decision |
|--------|----------|
| **Discounts** | **Line-level** — **% or amount** per quote line (standard Zoho quote line behavior). |
| **Territories** | **Yes** — assign leads/deals by **geography** (regions, governorates, etc.). |
| **Forecasting** | Decide **after go-live** — use basic pipeline views first; formal forecast later. |
| **Mobile** | **Rare** — **no** special mobile rollout (desktop-first). |
| **Data retention** | **Keep** records — **no** purge/anonymization policy for now. |

## 1. Line-level discounts

- Enable/configure **discount** on **Quote line items** (per product line).  
- Train reps: discount **per line**, not only in free text.  
- Align with **IQD** rounding rules if Zoho shows decimals you care about.

## 2. Territories

1. **Setup → Security Control → Territory Management** (labels vary slightly by edition / UI revision).  
2. Define hierarchy (e.g. **Country → Region → City** or your real structure).  
3. Assign **users** to territories; set rules for **Lead/Assignment** (round-robin vs manual).  
4. **Important:** This sits **alongside** **Production vs MPS** specialty — a rep can be in a territory **and** specialized by line; confirm whether **assignment** is by territory, by specialty, or **both** (may need **workflows** or clear manual owner rules).

*If Territory Management is not in your edition, use **custom picklist** “Region” + reports until you upgrade.*

## 3. Forecasting (later)

- For v1: **pipeline by stage**, **amount**, **close date**.  
- Revisit **forecast categories** and manager **commit** after reps use CRM for a few weeks.

## 4. Mobile

- No extra **mobile** training or policies required for v1.

## 5. Retention

- **Do not** bulk-delete historical Leads/Contacts without a future policy.  
- When legal/IT defines retention, add a playbook row — until then, **keep all**.

## Related

- [`CONFIGURATION-ROUND4.md`](./CONFIGURATION-ROUND4.md)  
- [`LEADS-AND-DEALS.md`](./LEADS-AND-DEALS.md)  
- [`PROJECT-STATUS.md`](../PROJECT-STATUS.md)
