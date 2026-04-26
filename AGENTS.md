# Agent and assistant notes (Zoho-CRM)

This repository automates and documents a **Zoho CRM Professional** rollout plus **Power BI** (see `docs/PROJECT-STATUS.md`).

- **Docs entrypoint:** `docs/zoho/INDEX.md` — open this first to navigate active vs archived content. **Folder map:** `docs/zoho/REPO-LAYOUT.md`.
- **Quote PDF template:** `docs/zoho/QUOTE-TEMPLATE-LEARNINGS.md` — canonical layout (50/50 meta + address, no grey panel, date clipping). HTML source: `tools/zoho/provision_quote_template.py`.
- **Build order:** `docs/zoho/IMPLEMENTATION-CHECKLIST.md` — do not improvise phase order.
- **Developer setup:** `docs/zoho/DEVELOPER.md`, `docs/zoho/GETTING-STARTED.md`; scripts live in `tools/zoho/`; secrets only in `tools/zoho/.env` (gitignored).
- **Automation index:** `tools/zoho/README.md` and `make help` from the repo root.
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

**Not layout-required (examples; reps can leave empty unless other rules apply):** `Owner`, `Salutation`, `Designation` (Title), `Full_Name` (synthetic), `Email`, `Website`, `Tag`, `Description`, address `Flat_House_No_Building_Apartment_Name`, `Street`, `Zip_Code`, `Latitude` / `Longitude`, etc.

**System mandatory (field definition, not the same as layout):** `Last_Name` is the only Leads field flagged `system_mandatory` in the fields API; other “required on save” behavior comes from the **layout** `required` flags above.

**Read-only on layout (typical system / reporting):** e.g. compound `Address` row `read_only: true` while subfields are editable; `Unsubscribed_*`, conversion fields, `id`, `Converted__s`, `Change_Log_Time__s`, `Locked__s`, enrichment flags — mostly `read_only: true` in metadata.

**Automation context:** Country is forced to **Iraq** via a workflow field update on create/edit; a Client Script on Create/Edit can set the **Country / Region** control in the browser (do not wrap the whole script in `function onLoad()` when the event is already **Page → onLoad**). Source: `artifacts/zoho/client_scripts/lead_country_iraq_lock.js`.

**Industry + Sector (2026-04-26+):** Standard **Industry** is restricted to the OCRD value list (see `artifacts/zoho/picklists/leads_industry_ocrh.txt`; **Ripping Center** and **Home** removed 2026-04-26); other options remain in the field definition as *unused* but do not appear on the Standard layout. Custom picklist **Sector** (`Sector`, id `7353692000000823062`) has **Private** and **Government**. Re-apply: `make zoho-leads-industry-sector` / `tools/zoho/provision_leads_industry_sector.py`.
