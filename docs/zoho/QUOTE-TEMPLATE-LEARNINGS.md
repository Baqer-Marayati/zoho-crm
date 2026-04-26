# Quote PDF template — operational learnings

Notes from rolling out and iterating the **Aljazeera Quotation** inventory (quote) PDF template and related automation.

## Canonical design (agreed 2026-04) — do not drift without a conscious decision

This is the **target** when editing HTML in `build_html()`. The PDF engine is not CSS3-flex; table + inline styles + explicit column widths are intentional.

- **No grey fill** behind Company Details / Bill To. White page, optional **one** thin vertical line between the two columns (same line as the meta block).
- **Lockstep 50% / 50% columns** for both:
  1. **Meta** (Quote #, Payment Terms, Reference | Date, Valid Until, Sales Person)
  2. **Address** (Company Details | Bill To)  
  So the left stack aligns: **Quote #** with **COMPANY DETAILS** and the **#** column of the line table; the right stack aligns: **Date** with **BILL TO**.
- **Meta layout:** outer row = two cells (50% each); **nested** label/value tables with **fixed** label column widths (left block ~92px, right block ~96px) and matching **outer** cell padding so labels do not “float” vs the address headers below.
- **Company address** is **hardcoded** in the template (Erbil block + phone + email) for consistent customer-facing output; **Bill To** uses merge fields.
- **Date only on PDF:** wrap `${!Quotes.Created_Time}` in a **narrow** `display:inline-block` with `white-space:nowrap;overflow:hidden` so the renderer does not show time (Zoho may emit full datetime; there is no date-only merge in all builds).
- **Valid Until** may show a **static phrase** (e.g. `14 Days`) if the org does not drive `${!Quotes.Valid_Till}` reliably; keep business truth on the **record** via workflow/Deluge if needed.
- **Header “SALES QUOTATION” (right):** A **spacer row** above the title (`<td height="N">` in the inner table) positions the text vertically vs the logo. **2026-04-26:** spacer **72px** (was 52px) so the title sits a bit **lower and closer to the first divider** under the header. If the PDF title looks too high or too low, adjust **only** this value — avoid changing outer header padding or the divider row unless the whole block needs to move.
- **Line items:** avoid repeating **Product_Name** in the **Description**; omit a redundant **Product_Code** line under the name if the catalog/SKU is obvious elsewhere (policy can change — keep one source of truth in the script).
- **Product descriptions:** PDF line text comes from the **line**; updating **Products** in CRM does not always refresh old quote lines — re-save lines or script updates if you need a refresh.

## Source of truth in repo

- **Template HTML:** `tools/zoho/provision_quote_template.py` → `build_html()`.
- **Provision / replace in Zoho:**  
  `make zoho-quote-template-replace` or  
  `cd tools/zoho && ./venv/bin/python provision_quote_template.py --replace`  
  Uses CRM **inventory_templates** API (`Quotes` module). **`--replace` deletes the prior template and creates a new one**, so the Zoho template **ID changes** each time; bookmarks or screenshots that reference an old ID go stale.
- **First-time / no overwrite:** `make zoho-quote-template` (runs without `--replace`; skips if the name already exists) or `--dry-run` to print payload only.
- **Logo:** Script embeds a resized logo from `LOGO_PATH` (local path in script). If the file is missing, the template falls back to text. Adjust `LOGO_PATH` / `FOLDER_ID` per org or machine.

## Layout and merge-field quirks

- **Rich-text inventory templates** are table-based HTML with inline styles. Zoho’s PDF renderer is picky: prefer simple structures (nested tables, explicit widths) over flex/grid.
- **`Created_Time` on PDF:** The merge field may render as datetime or with extra characters at the edge of the cell. A **fixed-width, `overflow:hidden`** span around `${!Quotes.Created_Time}` is a practical way to show **date-only** without server-side formatting. Tune `width`/`max-width` if a trailing digit or punctuation still peeks through.
- **Valid Until:** If the org does not populate `Valid_Till` reliably, the PDF can show a **static phrase** (e.g. `14 Days`) instead of `${!Quotes.Valid_Till}`. Keeping the real date on the record is still best done via **workflow / function** or **client script** (see below).
- **Avoid ad-hoc column math** (e.g. 40% + 10% gap + 50%): that **breaks vertical alignment** with a simple 50/50 meta row. Prefer one outer **50% | 50%** table; use **padding** and **border-left** on the right cell, not a dead spacer column, unless a design explicitly needs it.

## Automation: Valid Until and client scripts

- **Client script API** (`GET/PUT .../settings/client_scripts/Quotes`) can return **500 INTERNAL_ERROR** in some orgs or builds; scope and endpoint shape matter. The repo script is `tools/zoho/provision_quote_client_script.py`; source file is `artifacts/zoho/client_scripts/quote_reference_autofill.js`.
- **Custom function updates** for workflow-attached Deluge: creating new functions via `POST .../settings/automation/functions` with a raw `function` string often returns **INVALID_DATA** on `arguments.function`. **Updating an existing function** may succeed with a body shaped like:  
  `{"functions":[{"metadata":{...},"code":"<deluge source>"}]}`  
  (exact shape depends on Zoho API version; verify against current docs if this starts failing.)
- **Quote line sync function** `artifacts/zoho/deluge/quoted_items_sync_machine_sku.deluge` can also enforce **Valid_Till = Created_Time + 14 days** on save, alongside Machine SKU / product alignment. Workflow must run on **Quotes** create/edit and pass the quote id into the function.

## Operational checklist after template edits

1. Run `provision_quote_template.py --dry-run` (sanity).
2. Run with `--replace` to publish.
3. Note the **new template ID** from the script output.
4. In CRM: **Print / Export PDF** → confirm **Aljazeera Quotation** is selected; spot-check date, Bill To balance, footer, totals block.

## Related docs

- [`PRODUCTS-AND-QUOTES.md`](./PRODUCTS-AND-QUOTES.md) — screen vs PDF, training.
- [`QUOTE-LINE-AUTOMATION.md`](./QUOTE-LINE-AUTOMATION.md) — Deluge + workflow patterns.
