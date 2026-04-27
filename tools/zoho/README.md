# `tools/zoho` — Zoho CRM API automation

Add **small, focused** scripts here: OAuth test, bulk import, health checks, webhooks, or one-off data fixes.

**End-to-end automation (OAuth, Zoho MCP, what cannot be full API)**: [`../../docs/zoho/AUTOMATION-STACK.md`](../../docs/zoho/AUTOMATION-STACK.md).

**Scope + connectivity check** (run after any new grant or when APIs return empty or 401):

```bash
./venv/bin/python zoho_doctor.py
# or: make zoho-doctor
```

**Efficient metadata context (recommended before Zoho work):** use the local metadata cache so agents/scripts read one compact summary instead of repeatedly calling metadata APIs or loading huge payloads.

```bash
make zoho-cache-summary   # auto-refreshes if stale, then prints cache paths
make zoho-cache-refresh   # force-refresh after metadata changes
make zoho-cache-status    # no API call; just shows cache age/path
```

The cache lives under `.cache/zoho/` and is gitignored. It stores metadata only (fields, layouts, pipelines, map dependencies), not customer records.

## Setup

From repo root (installs Homebrew **Node**/`npx` for Zoho MCP’s `mcp-remote` bridge, then Python venv + deps):

```bash
make zoho-setup
```

Or only Python:

```bash
cd tools/zoho
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

### Easiest: one interactive command (recommended)

Run this in **Terminal** (not in Cursor chat). The script asks for Client ID, Client Secret, and grant code **locally** and writes `tools/zoho/.env` for you.

```bash
cd tools/zoho
./venv/bin/python connect_zoho.py
```

Get **Client ID**, **Client Secret**, and a fresh **grant code** from [Zoho API Console](https://api-console.zoho.com/) → **Self Client** (same flow as before). If you are not on US Zoho, type the right **Accounts URL** when prompted (e.g. `https://accounts.zoho.eu`).

**Scopes (Generate Code):** For API smoke tests we call **Leads**, so include at least **`ZohoCRM.modules.ALL`** (comma-separated if you add more). To use the **Users** API later, add **`ZohoCRM.users.ALL`** and generate a **new** grant + refresh token (scopes are fixed per refresh token).

**Pipelines automation:** To run `provision_pipelines.py`, include **`ZohoCRM.settings.ALL`** (or equivalent settings scopes) in the grant and refresh `ZOHO_REFRESH_TOKEN`. Then:

```bash
./venv/bin/python provision_pipelines.py --dry-run
./venv/bin/python provision_pipelines.py
```

Edit `pipelines_seed.json` so stage names match your org’s **Deals → Stage** picklist labels.

**Activate only the seed stages and rename their display labels:** many orgs need layout-level picklist rows updated first. This also moves omitted stages (for example, old decision-maker/lost-to-competition values) to Unused so they do not show in Stage View.

```bash
./venv/bin/python provision_deal_stage_picklist.py
# or: make zoho-deal-stage-labels
```

**After you change stage lists** for existing pipelines, push updates to Zoho:

```bash
./venv/bin/python provision_pipelines.py --sync
# or: make zoho-sync-pipelines
```

**Unified model:** `pipelines_seed.json` now defines only **Standard (Standard)**; sector is **Line of business** on Lead/Deal (see `provision_phase2_fields.py`). A legacy radiology pipeline seed is in **`archive/pipelines_seed.radiology.json`** (Radiology = picklist value, not a separate pipeline; use `--seed` only for reference or recovery).

**Teamspace (Next Gen sidebar):** To create the **Direct department** workspace and attach core modules, use `provision_teamspace.py` with `../../artifacts/zoho/teamspace/direct_department.json` (see `../../artifacts/zoho/teamspace/README.md`). Requires settings scopes (e.g. `ZohoCRM.settings.ALL`). If the API rejects `access_type`, create the teamspace in the Zoho UI and keep the manifest as the source of truth.

**Canon five-machine line:** `build_canon_five_machines_csv.py` merges the flat EN spec CSV into **five** Zoho products with SKUs (`canon_products_five_machines_en.csv`). See `../../artifacts/zoho/import/canon_product_line/README.md`. To **delete** the legacy 23 Wave-A product names in Zoho and **re-import** the five, run `sync_canon_five_products_zoho.py` or `make zoho-sync-canon-five-products`.

**Quote line:** `provision_quote_line_extensions.py` syncs product **Compatible finishers / POD** text from `../../artifacts/zoho/product_extensions/extensions_by_product_code.json` (`make zoho-quote-line-extensions`). **`provision_quoted_line_dependencies.py`** adds **Machine SKU**, **Model / speed**, renames line picklists to **Configuration 1/2**, and sets **map dependency** so options follow the chosen SKU (`make zoho-quoted-line-deps`; see `../../docs/zoho/QUOTE-LINE-EXTENSIONS.md`). **`provision_quoted_line_product_first_layout.py`** (`make zoho-quote-line-product-first-layout`) renames **Machine SKU** to **Product (Machine)**, moves **Product Name** off the used layout when Zoho allows (otherwise sets **Product Name** read-only on the layout), and re-syncs picklist options to the layout (required for `map_dependency`). Re-paste Deluge from `../../artifacts/zoho/deluge/quoted_items_sync_machine_sku.deluge` into **Quote lines — sync Machine SKU** after that: that file also rebuilds each line **Description** (no second Zoho function required). Optional: `provision_quote_line_description_workflow.py` / `../../artifacts/zoho/deluge/quoted_items_build_line_description.deluge` if you use a **separate** function for descriptions.

**Quote header — Reference (system field `Subject`):** `provision_quote_reference_field.py` (`make zoho-quote-reference-field`) renames the label to **Reference**. `provision_quote_client_script.py` (`make zoho-quote-client-script` or `make zoho-quote-reference-full`) tries to **GET/PUT** the script from `../../artifacts/zoho/client_scripts/quote_reference_autofill.js` via `GET /settings/client_scripts/Quotes`; that endpoint often needs **`ZohoCRM.settings.client_scripts.ALL`** in addition to `settings` scopes (see `.env.example`). Re-ordering the field in the form is **UI-only**; the Layouts API cannot move system-mandatory **Subject** out of a section.

**Quote PDF — Aljazeera Quotation (inventory / Quotes template):** `provision_quote_template.py` syncs the HTML from this repo to Zoho via **Settings → inventory_templates**. **Design invariants** (50/50 meta + address, no grey panel, date-only clip) are documented in `../../docs/zoho/QUOTE-TEMPLATE-LEARNINGS.md`. Requires settings scopes (same family as other template APIs — use `zoho-doctor` if create fails).

```bash
# Dry-run: print API payload only
./venv/bin/python provision_quote_template.py --dry-run

# Create if missing (skip if a template with the same name already exists)
./venv/bin/python provision_quote_template.py
# or: make zoho-quote-template

# After editing build_html() — delete and recreate (template ID will change)
./venv/bin/python provision_quote_template.py --replace
# or: make zoho-quote-template-replace
```

**CPQ Product Configurator (experimental):** `provision_cpq_product_configurator_pilot.py` (`make zoho-cpq-product-configurator-pilot`, `--dry-run` to print the resolved JSON only) calls the undocumented `POST /crm/v8/settings/cpq/product_configurators` endpoint. If Zoho returns 500, finish the same pilot in **Setup → Developer Hub → CPQ → Product Configurator**. To push the Deluge and workflow to Zoho via API, use **`provision_quoted_line_machine_sku_workflow.py`** (`make zoho-quote-line-machine-sku-wf`) with settings scopes, or follow `../../docs/zoho/QUOTE-LINE-AUTOMATION.md`. Optional: **`provision_quoted_line_hide_machine_sku_layout.py`** if you want the picklist hidden again (then `map_dependency` cannot apply — not compatible with the product-first layout).

**Canon product descriptions:** Short catalog copy is in `build_canon_five_machines_csv.py` (`CURATED_DESCRIPTIONS`). Rebuild CSV + push to Zoho: `make zoho-build-canon-five-machines` then `make zoho-sync-canon-product-descriptions` (or `sync_canon_product_descriptions.py`). The **PDF** shows each line’s `Description` — if product copy in CRM changed but a quote line looks stale, re-save lines or see `../../docs/zoho/QUOTE-TEMPLATE-LEARNINGS.md`.

**Canon PDFs on Products:** `upload_canon_product_pdfs.py` posts `*.pdf` from `~/Dropbox/Work/Canon/Canon machine specs for SAP` subfolders to the matching product’s **Attachments** (`make zoho-upload-canon-product-pdfs`). Needs attachment create scope; re-run may duplicate files if Zoho allows.

### Phase 2 fields (Line of business, Lost Reason, Competitor)

Requires **`ZohoCRM.settings.ALL`** (or `settings.fields.CREATE`) on your refresh token.

```bash
./venv/bin/python provision_phase2_fields.py --dry-run
./venv/bin/python provision_phase2_fields.py
```

Then run **layout + map dependencies** (needs `settings.layouts` + `settings.map_dependency` scopes, or `settings.ALL`):

```bash
./venv/bin/python provision_phase2_layouts.py --dry-run
./venv/bin/python provision_phase2_layouts.py
# or: make zoho-phase2-layouts
```

Finish any remaining **UI** steps in [`../../docs/zoho/PHASE2-AUTOMATED.md`](../../docs/zoho/PHASE2-AUTOMATED.md) (conversion mapping, stage–probability %).

**Do not paste those secrets into AI chat** — only into this Terminal wizard.

### Manual path (`.env` by hand)

```bash
cp .env.example .env
chmod 600 .env
# fill .env, then:
./venv/bin/python exchange_grant.py
./venv/bin/python zoho_ping.py
```

## Running

```bash
./venv/bin/python zoho_ping.py
# Add your own scripts alongside these helpers.
```

## Documentation

- `../../docs/zoho/DEVELOPER.md` — repo workflow
- `../../docs/zoho/GETTING-STARTED.md` — Zoho API Console and scopes

Zoho’s official **CRM API v2** docs: use the current URL for your data center (`.com` / `.eu` / etc.) from [Zoho’s developer site](https://www.zoho.com/crm/developer/docs/api/v2/).
