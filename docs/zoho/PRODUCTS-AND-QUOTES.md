# Products, quotes, and currency — decisions (round 2)

**Captured 2026-04-23**

| Topic | Decision |
|--------|----------|
| **Currency** | **IQD only** for pricing deals and quotes (set org base currency accordingly in Zoho). |
| **Product catalog** | **Messy** source (e.g. spreadsheets) — **clean up before or during import**; phased load. |
| **Quote attachments** | **Sometimes** — enable attachments on quotes; train reps when to attach specs/T&Cs. |
| **Lead source** | **Nice to have** — keep field available; **do not** block conversion if empty. |
| **Approvals** | **None for v1** — no mandatory manager approval on quotes or deal changes (revisit later). |

## 1. Currency (IQD)

1. **Setup → Company Settings → Currencies** (or equivalent) — confirm **base currency IQD**.  
2. **Deals** and **Quotes** — amounts display in IQD; train reps not to mix currencies unless you add USD later.  
3. If you already have **USD** amounts in old data, plan a **one-time conversion** or a custom “Amount USD” field — only if needed.

## 2. Messy catalog → practical rollout

**Do not** try to perfect the catalog before go-live. Use **three waves**:

| Wave | Goal |
|------|------|
| **A — Skeleton** | Top **20–50** SKUs or families you quote **most** (price + description + unit). |
| **B — Hygiene** | One owner cleans the spreadsheet (dedupe, consistent names, IQD price column). |
| **C — Import** | **Products** module: import CSV or manual bulk; fix errors in Zoho. |

Until Wave A is stable, allow **custom line items** on quotes (Zoho supports adding rows not only from catalog — confirm in your edition).

## 3. Quotes + attachments (sometimes)

1. **Setup → Customization → Modules and Fields → Quotes** — ensure **Attachments** / **Notes** are available to sales profiles.  
2. Optional: **Quote** checklist in training — *attach drawing when SKU is custom*.  
3. **No approval v1** — when you add approval later, use **Blueprint** or **Review process** on Quotes.

## 4. Lead source (light touch)

- Keep **Lead Source** (or channel) on the layout.  
- Optional **reports** by source; no validation rule requiring it.

## 5. Order of work (after Leads → Deals)

1. Finish **LEADS-AND-DEALS.md** checklist (conversion, lost reasons).  
2. **Wave A** product list + **Quotes** layout linked to **Deals**.  
3. Train reps on **one** quote template (PDF) and when to attach files.

## Related

- [`LEADS-AND-DEALS.md`](./LEADS-AND-DEALS.md)  
- [`SALES-PIPELINE-AND-STAGES.md`](./SALES-PIPELINE-AND-STAGES.md)  
- [`PROJECT-STATUS.md`](../PROJECT-STATUS.md)
