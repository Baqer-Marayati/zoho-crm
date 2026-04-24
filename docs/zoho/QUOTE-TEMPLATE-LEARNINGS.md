# Quote PDF template — operational learnings

Notes from rolling out and iterating the **Aljazeera Quotation** inventory (quote) PDF template and related automation.

## Source of truth in repo

- **Template HTML:** `tools/zoho/provision_quote_template.py` → `build_html()`.
- **Provision / replace in Zoho:**  
  `cd tools/zoho && ./venv/bin/python provision_quote_template.py --replace`  
  Uses CRM **inventory_templates** API (`Quotes` module). **`--replace` deletes the prior template and creates a new one**, so the Zoho template **ID changes** each time; bookmarks or screenshots that reference an old ID go stale.
- **Logo:** Script embeds a resized logo from `LOGO_PATH` (local path in script). If the file is missing, the template falls back to text. Adjust `LOGO_PATH` / `FOLDER_ID` per org or machine.

## Layout and merge-field quirks

- **Rich-text inventory templates** are table-based HTML with inline styles. Zoho’s PDF renderer is picky: prefer simple structures (nested tables, explicit widths) over flex/grid.
- **`Created_Time` on PDF:** The merge field may render as datetime or with extra characters at the edge of the cell. A **fixed-width, `overflow:hidden`** span around `${!Quotes.Created_Time}` is a practical way to show **date-only** without server-side formatting. Tune `width`/`max-width` if a trailing digit or punctuation still peeks through.
- **Valid Until:** If the org does not populate `Valid_Till` reliably, the PDF can show a **static phrase** (e.g. `14 Days`) instead of `${!Quotes.Valid_Till}`. Keeping the real date on the record is still best done via **workflow / function** or **client script** (see below).
- **Removing unused blocks:** Dropping **Ship To** (or payment blocks) avoids empty columns; reclaim space by **one full-width customer panel** with two columns (company vs bill-to) and a **spacer column** to push Bill To right for balance.

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
