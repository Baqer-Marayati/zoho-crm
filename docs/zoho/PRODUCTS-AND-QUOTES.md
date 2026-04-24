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

## 6. How quotes “look”: screen vs customer PDF

Zoho separates **(A) what reps edit**, **(B) what appears on the generated PDF/email**, and **(C) what lives only on the Product record**.

### A. Quote record + line items (CRM screen)

- **Quote header** — standard fields (Customer, Deal, Valid Until, Terms, Owner) plus any custom fields you add (e.g. **Payment Terms**, **Contract Folder URL** from Phase 3).
- **Product Details / line items** — when someone picks a **Product**, Zoho fills **list price**, **quantity**, and often a **line-level Description**. Whether the **full Product `Description`** copies to the line depends on **org/product-line settings** and edition; very long consolidated specs (like the five-machine text) are usually **too heavy** for every PDF line.
- **Practical pattern for your catalog**  
  - Keep the **Product `Description`** as a **short, stable** blurb (same for every quote that uses that product). **Do not** change the product record when the rep picks a speed or finisher; put those on the **quote line** (picklists + optional line description) so the PDF reflects the **configuration** without rewriting master data.  
  - Deep spec stays in **attachments** and **Compatible finishers / POD** text on the product (see `QUOTE-LINE-EXTENSIONS.md`).  
  - Optional: a separate **“Line summary”** formula or text on the line if you need a one-line PDF snippet built from product + picks.

### B. Quote PDF / print template (customer-facing)

- Built under **Setup → Templates** (or **Print/Web Templates** / **Quote templates**, depending on your CRM edition and Next Gen vs Classic).
- The template controls **logo, fonts, footer, and which merge fields** appear — e.g. `${Quotes.Product Details}` style tables, individual line columns, subtotals, IQD formatting.
- **Design levers:** add/remove **columns** on the product table (product name, qty, rate, amount, **line description**, your custom variant fields); add a **Terms** block; optional **second page** for legal text.
- **Product description on PDF:** map the field you want (short summary vs full `Description`). If the PDF becomes cluttered, prefer **short line text** + **“see attached datasheet”** or link to **Contract Folder URL**.

### C. Product record (not automatically the whole PDF)

- **Attachments** (brochures, datasheets) stay on **Products** unless you attach copies to the **Quote** for this deal. Train reps: attach PDF to the quote when the customer must receive it with the official quote.

### Suggested design pass (checklist)

1. **Layouts** — **Quotes** header section + **Product Details** subform: show variant fields and a concise line description column.  
2. **Products** — add **Short description for quotes** (or trim `Description`) so PDFs stay professional.  
3. **Template** — one branded PDF; preview with a real line using **Canon varioPRINT 6000 TITAN** + variant fields filled.  
4. **Training** — when to paste extra text on the line vs attach spec PDF.

## Related

- [`QUOTE-LINE-EXTENSIONS.md`](./QUOTE-LINE-EXTENSIONS.md) — finishers & POD/paper on quote lines + product reference fields  
- [`LEADS-AND-DEALS.md`](./LEADS-AND-DEALS.md)  
- [`SALES-PIPELINE-AND-STAGES.md`](./SALES-PIPELINE-AND-STAGES.md)  
- [`PROJECT-STATUS.md`](../PROJECT-STATUS.md)
