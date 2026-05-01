# Phase 2 — API automation vs short UI follow-up

## 1) Picklist fields (Leads + Deals)

From `tools/zoho`, with **`ZohoCRM.settings.ALL`** (or `settings.fields.CREATE`):

```bash
cd tools/zoho
./venv/bin/python provision_phase2_fields.py --dry-run   # optional
./venv/bin/python provision_phase2_fields.py
```

Or: `make zoho-phase2-fields` from the repo root.

**Creates** (if missing):

| Module | Field | Values from |
|--------|--------|-------------|
| **Leads** | **Line of business** | `artifacts/zoho/picklists/line_of_business.csv` |
| **Deals** | **Line of business** | same CSV (sector: Production / MPS / Radiology); placed on **Standard** Deals layout |
| **Deals** | **Lost Reason** | `artifacts/zoho/picklists/lost_reasons.csv` |
| **Deals** | **Competitor** | `artifacts/zoho/picklists/competitors_template.csv` |

Re-running is safe: same **label** → skipped; new CSV picklist values are **merged** onto existing Lead/Deal **Line of business** fields when possible.

---

## 2) Deals layout — Closing Date, required Lost/Competitor, Stage map dependencies

With **`ZohoCRM.settings.ALL`** (or `settings.layouts.*` + `settings.map_dependency.*` for read/create/update):

```bash
cd tools/zoho
./venv/bin/python provision_phase2_layouts.py --dry-run
./venv/bin/python provision_phase2_layouts.py
```

Or: `make zoho-phase2-layouts`.

**Does:**

- Ensures **Closing Date** is **required** on the **Standard** Deals layout (no-op if already).
- Sets **Lost Reason** and **Competitor** as **required** on that layout (disable with `--no-require-lost-fields` if you prefer).
- Creates or updates **map dependencies**: **Stage** → **Lost Reason**, **Stage** → **Competitor** on that layout.  
  - Stages whose label contains **“closed lost”** (e.g. *Closed Lost*, *Closed Lost to Competition*) expose **all real** picklist values (not the system `-None-` row).  
  - All **other** stages expose **only** `-None-` for those two fields.

Idempotent: re-run updates existing map dependency rows.

---

## 3) What you still do in Zoho (small)

1. **Lead conversion mapping** — confirm with **`make zoho-audit-lead-conversion`** (`audit_lead_conversion_mapping.py`). Zoho exposes per-field `convert_mapping` on **`GET /crm/v8/settings/fields?module=Leads`**; layouts include a **`convert_mapping`** block for the Deal layout used on convert. Change mappings in **Setup → Leads → Lead Conversion Mapping** if needed.

2. **Stage–probability** for **Standard (Standard)** pipeline (§5 — UI recommended)  
   `/settings/stages?module=Deals` (HTTP 200) returns stage rows with probability values (your **pipeline** may list **6** stages while older **picklist** options can still exist for legacy deals).
   values. Zoho default values are already loaded (10 % → 100 %). Custom % can be set via
   `PUT /settings/stages/{stage_id}?module=Deals` — but this endpoint is undocumented in the
   main v8 public docs; test manually before scripting.

   **Recommended manual step (~2 min per pipeline):**  
   `Setup → Pipelines → [select pipeline] → Stage-Probability Mapping column`

3. **Layouts** — only if fields sit under **Unused** in your org (uncommon after API create). Drag **Line of business** / **Lost Reason** / **Competitor** onto the layouts you use.

---

## 4) §6 Field history tracking (API-automated)

From `tools/zoho`, run:

```bash
cd tools/zoho
./venv/bin/python provision_phase2_tracking.py --dry-run   # optional preview
./venv/bin/python provision_phase2_tracking.py
```

Or: `make zoho-phase2-tracking` from the repo root.

**What it does:**

- Probes the stage-probability API (§5) — reports result and manual path
- Enables `history_tracking=true` on **Stage** and **Amount** in the Deals module  
  via `PATCH /settings/fields/{field_id}?module=Deals`
- Idempotent: skips fields that already have tracking enabled

**Scope:** `ZohoCRM.settings.ALL` (same token as other Phase 2 scripts)

---

## 5) §7 Activity discipline — training only

No API configuration available or needed. Process rules to communicate to your pilot reps:

- Log a **call or meeting** within 24 h of every stage change
- Use **Tasks** for follow-ups (due date required)
- Review the **Activities** tab during weekly pipeline meetings
- Optional later: configure a Blueprint in Setup → Process Management → Blueprint

---

## If a script errors

- **`OAUTH_SCOPE_MISMATCH`** — new grant with **`ZohoCRM.settings.ALL`**, update `ZOHO_REFRESH_TOKEN`.  
- **Map dependency** — ensure **Lost Reason** / **Competitor** are on the **used** layout (not Unused).  
- **Stage labels** — script treats any stage containing **closed lost** as “closed lost” for dependency mapping; rename stages in Zoho if that heuristic is wrong.

## Related

- [`IMPLEMENTATION-CHECKLIST.md`](./IMPLEMENTATION-CHECKLIST.md) — Phase 2  
- [`LEADS-AND-DEALS.md`](./LEADS-AND-DEALS.md)
