# Agent and assistant notes (Zoho-CRM)

This repository automates and documents a **Zoho CRM Professional** rollout plus **Power BI** (see `docs/PROJECT-STATUS.md`).

- **Docs entrypoint:** `docs/zoho/INDEX.md` — open this first to navigate active vs archived content. **Folder map:** `docs/zoho/REPO-LAYOUT.md`.
- **Quote PDF template:** `docs/zoho/QUOTE-TEMPLATE-LEARNINGS.md` — canonical layout (50/50 meta + address, no grey panel, date clipping). HTML source: `tools/zoho/provision_quote_template.py`.
- **Build order:** `docs/zoho/IMPLEMENTATION-CHECKLIST.md` — do not improvise phase order.
- **Developer setup:** `docs/zoho/DEVELOPER.md`, `docs/zoho/GETTING-STARTED.md`; scripts live in `tools/zoho/`; secrets only in `tools/zoho/.env` (gitignored).
- **Automation index:** `tools/zoho/README.md` and `make help` from the repo root.
- **Deals + Quotes workflows + Deluge:** `docs/zoho/DEALS-QUOTES-PROCESS-PROVISIONING.md` — `make zoho-deals-quotes-process`; long agent prompts live under `docs/zoho/handoffs/` (including Needs Analysis guidance + Proposal/Quote gates: `docs/zoho/handoffs/AGENT-PROMPT-NEEDS-ANALYSIS-GUIDANCE-AND-GATES.md`).
- **MCP vs scripts:** `docs/zoho/AUTOMATION-STACK.md` — hosted Zoho CRM MCP bundles (workflows, fields, layouts, CRUD, COQL) plus what still belongs in `tools/zoho` Python (function catalog, `/settings/functions` source, automation wrappers).
- **Client Script automation:** Public REST/MCP does not reliably create **Developer Hub → Client Script** rows. Use the Safari admin-session method documented in `.cursor/rules/zoho-crm-api-automation.mdc` / `docs/zoho/AUTOMATION-STACK.md`: internal `/crm/v2.2/settings/cscript_pages` + `/cscript_snippets`, browser CSRF headers, Zoho `compile_script(...)`, and required static resources. Do not fall back to manual paste before trying this path.
- **Efficient Zoho context:** before broad Zoho metadata work, prefer the compact cache summary at `.cache/zoho/metadata.summary.md`. If it is missing/stale, run `make zoho-cache-summary` (auto-refresh) or `make zoho-cache-refresh` after metadata changes. This reduces Zoho API credits and AI context usage; cache files are local/gitignored and contain metadata only.
- **Workshop context (archive):** `docs/zoho/archive/configuration-rounds/`.
- **Cursor rule:** `.cursor/rules/zoho-crm-api-automation.mdc` — run scripts in-terminal when the task is clearly Zoho API work; confirm before bulk-destructive or org-wide security changes.

Never commit or paste real OAuth refresh tokens, client secrets, or customer PII.

## Leads — Standard layout (live org snapshot, 2026-04-27)

Source: `GET /crm/v8/settings/layouts/{layout_id}` and `.../settings/fields?module=Leads` (only **Standard** is active for Leads; `layout_id=7353692000000091055`).

**Sections (in order):** Record Image → Lead Information → Address Information → Description Information. The API did not return a separate **Unused** section on this layout (fields not listed below may still be hidden via `view_type` or not placed on the layout).

**Layout-required (required on the Standard create/edit form — `required: true` on the layout field row, 10 fields):**

| API name            | Label (UI)                 | Section            |
| ------------------- | -------------------------- | ------------------ |
| `Company`           | Company                    | Lead Information   |
| `First_Name`        | First Name                 | Lead Information   |
| `Last_Name`         | Last Name                  | Lead Information   |
| `Phone`             | Phone                      | Lead Information   |
| `Sector`            | Sector                     | Lead Information   |
| `Industry`          | Industry                   | Lead Information   |
| `Line_of_business`  | Line of business           | Lead Information   |
| `City`              | Address - City             | Address Information |
| `Country`           | Address - Country / Region | Address Information |
| `State`             | Address - State / Province | Address Information |

**`Full Name` (`Full_Name`) — important:** A **double-check** on `GET /crm/v8/settings/layouts/7353692000000091055?module=Leads` (2026-04-27) shows **`required: false`** for `Full_Name`, and **`view_type` has `create: false` and `edit: false`**, so in metadata this field is **not** on the Create/Edit form at all (Zoho Leads usually builds the display name from **First** + **Last**). The API therefore **does not** list it among the 10 layout-mandatory fields. If the Zoho **UI** shows **Full Name** as mandatory, that can be: an unsaved layout, a different layout/tab, a browser cache, or a UI state the REST layout payload has not picked up yet — **re-open the layout in Setup → Leads → Standard → mark required → Save** and re-run a layout GET, or confirm you are on **Standard** (only one Leads layout is active in this org).

**All other non-mandatory on this layout (API `required` not `true` — 30 field rows), including** `Owner`, `Salutation`, `Designation` (Title), `Email`, `Website`, `Description`, `Full_Name`, address subfields `Street`, `Zip_Code`, `Flat_House_*`, `Latitude` / `Longitude`, plus system/reporting fields often hidden on the form (`Tag`, `id`, conversion fields, etc.). See `view_type` in the layout response for on-form vs hidden.

**System mandatory (field definition, not the same as layout):** `Last_Name` is the only Leads field flagged `system_mandatory` in the fields API; other “required on save” behavior comes from the **layout** `required` flags above.

**Read-only on layout (typical system / reporting):** e.g. compound `Address` row `read_only: true` while subfields are editable; `Unsubscribed_*`, conversion fields, `id`, `Converted__s`, `Change_Log_Time__s`, `Locked__s`, enrichment flags — mostly `read_only: true` in metadata.

**Automation context:** Country is forced to **Iraq** via a workflow field update on create/edit; a Client Script on Create/Edit can set the **Country / Region** control in the browser (do not wrap the whole script in `function onLoad()` when the event is already **Page → onLoad**). Source: `artifacts/zoho/client_scripts/lead_country_iraq_lock.js`.

## Deals — Standard layout when Stage = Qualification (live org snapshot, 2026-04-30)

Confirmed in **Create Deal** with **Stage** set to **Qualification**: **Deal Information** shows the fields below; in the Zoho UI, the **red vertical bar** beside a control means **mandatory on the layout** (same idea as layout `required: true` in API layout payloads).

**Layout-mandatory in Qualification (6 fields — red bar in UI):**

| API name (typical) | Label (UI)    | Notes                                      |
| ------------------ | ------------- | ------------------------------------------ |
| `Deal_Name`        | Deal Name     |                                            |
| `Account_Name`     | Account Name  | Lookup                                     |
| `Contact_Name`     | Contact Name  | Lookup                                     |
| `Line_of_business` | Line of business |                                         |
| `Pipeline`         | Pipeline      | e.g. Standard (Standard)                   |
| `Stage`            | Stage         | Qualification while on this snapshot       |

**On the same form but not mandatory:** `Owner` (Deal Owner), `Amount`, `Expected_Revenue` (Expected Revenue).

**Description Information:** `Description` present and **not** mandatory.

Progressive visibility for later-stage-only custom fields is handled by `artifacts/zoho/client_scripts/deal_stage_field_visibility.js`; it does **not** replace layout mandatory rules — those stay in **Setup → Deals → Layouts**.

**Proposal / Quote gate (live org, 2026-05-01):** Kanban/API stage moves bypass Deal form Client Scripts. The reliable API-driven enforcement is server-side workflow rollback created by `tools/zoho/provision_deals_quotes_process.py`: `Deal gate rollback - Proposal ...` workflows apply `Deal gate rollback to Needs Analysis` when required Proposal fields are blank or Budget is `-None-`. Do not rely on `deal_stage_gate_guard` for this gate unless its workflow wrapper shows a real `dealId` argument mapping; the observed wrapper returned `arguments: null`.

**Industry + Sector (2026-04-26+):** Standard **Industry** is restricted to the OCRD value list (see `artifacts/zoho/picklists/leads_industry_ocrh.txt`; **Ripping Center** and **Home** removed 2026-04-26); other options remain in the field definition as *unused* but do not appear on the Standard layout. Custom picklist **Sector** (`Sector`, id `7353692000000823062`) has **Private** and **Government**. Re-apply: `make zoho-leads-industry-sector` / `tools/zoho/provision_leads_industry_sector.py`.
