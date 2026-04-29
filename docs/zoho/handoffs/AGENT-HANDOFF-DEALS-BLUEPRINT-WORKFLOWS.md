# Agent handoff: Deals + Quotes Blueprints & workflows (Zoho CRM)

**Audience:** Next automation agent implementing this org’s sales process in **Zoho CRM**.  
**Goal:** Encode the agreed sales motion (production printing / equipment, B2B Iraq) using **custom fields**, **workflow rules**, **optional Deluge**, and **Deals Blueprint** (or API-equivalent enforcement).  
**Repo context:** `tools/zoho/` (v8 API, `zoho_tokens.py`, patterns in `provision_*` scripts).

---

## 0) Critical expectation: “zero manual work”

The stakeholder wants **full automation** (no clicking in Zoho Setup).

**You must verify current Zoho product/API limits before promising completion:**

| Area | Typical automation path | Risk |
|------|-------------------------|------|
| **Custom fields** (Deals, Quotes) | `POST/PATCH` Settings Fields API | Low — repo already does this (`provision_phase2_fields.py`). |
| **Workflow rules** | `POST /crm/v8/settings/automation/workflow_rules` | Medium — some actions need separate “actions” APIs; **Custom Functions** sometimes fail creation via API (see `provision_quoted_line_machine_sku_workflow.py` comments). |
| **Blueprint definition** (process graph, transitions, mandatory fields on transition) | **Unclear / often UI-first** | **High** — this repo only documents `GET`/`DELETE` for `/settings/blueprints` (`provision_delete_blueprints.py`). Record-level `PUT .../actions/blueprint` is for **executing** transitions, not **defining** the blueprint. **Search Zoho’s latest v8 Settings docs** for blueprint **create/update**. If no create API exists, you **cannot** honestly deliver 100% hands-off Blueprint setup; use **Validation Rules** + **workflows** to enforce the same business rules and state this limitation in your summary to the stakeholder. |

**Deliverable if Blueprint definition is not API-available:** Implement **equivalent enforcement** (validation rules on save + stage-change workflows) and list the **single** remaining manual step (if any) with exact Setup clicks — do not claim “none” without proof.

---

## 1) Business process (source of truth)

- **Lead** registered first; rep **contacts** and qualifies.
- **Convert Lead → Deal** when **first contact shows interest / possible need** (Deal starts in **Qualification**).
- **Official quotation** lives in **Zoho Quotes** (with products/lines). Multiple **A/B quotes** per Deal are normal; **Primary Quote** on the Deal indicates the expected winner for reporting.
- **Discovery** is captured on the **Deal only** (Lead stays lightweight).
- **Low admin** for sales: prefer **auto-created tasks** over blocking “next activity” requirements.
- **No manager approval** and **no technical approval** before quote.
- **Deal Amount** is **manually** maintained on the Deal (not auto-synced from Quote); nudge consistency via workflows if useful.
- **Quote Sent** means **Quote exists in Zoho** (created), not necessarily emailed yet; **Negotiation** requires evidence the customer received **at least one** quote option.

---

## 2) Pipeline stages (must match picklist + `pipelines_seed.json`)

Unified **Standard (Standard)** pipeline; **7** stages in order:

1. Qualification  
2. Needs Analysis  
3. Solution / Value  
4. Quote Sent  
5. Negotiation  
6. Closed Won  
7. Closed Lost  

Source: `tools/zoho/pipelines_seed.json`, `docs/zoho/SALES-PIPELINE-AND-STAGES.md`.

---

## 3) Stakeholder decisions (from structured Q&A — implement exactly)

### 3.1 Quotes & stages

| Topic | Decision |
|-------|----------|
| Quote source | **Zoho Quotes** module (official). |
| Multiple quotes | **A/B options**; Deal has **Primary Quote** (lookup). |
| Quote Sent meaning | Stage when quote **exists in Zoho** (created). |
| Negotiation entry | When **active discussion** on price/terms/etc. — **not** only after formal customer reply. |
| Gate into Negotiation | Keep stage **Quote Sent**; add per-**Quote** checkbox **`Quote shared with customer`**. **Negotiation** allowed only if **≥1 Quote linked to the Deal** has this checkbox **true** (any linked quote, not Primary-only). |
| Evidence of share | **Checkbox only** on Quote (no date/channel). |
| Who sets “shared” | **Quote Owner only** (verify Quote profile permissions). |

### 3.2 Discovery strictness

| Topic | Decision |
|-------|----------|
| Discovery location | **Structured fields on Deal** (not Lead). |
| Strictness | **Moderate:** required summary + key fields **before formal quoting**, not ultra-heavy checklist. |
| Minimum before Quote Sent | **Discovery summary**, **Current machines/setup**, **Applications**, **Budget/financing status**. |
| Repeat customers | **Rare** — no special “fast path” required. |

### 3.3 Activities

| Topic | Decision |
|-------|----------|
| Next activity | **Auto-create** follow-up tasks on stage changes (do **not** block saves for “future activity exists” in v1). |

### 3.4 Timing (workflows)

| Topic | Decision |
|-------|----------|
| After Quote Sent | First follow-up task **+2 days**. |
| Stale open deals | Reminder if **no stage change** and **no logged activity** for **14 days** (see §6.2 — implement as close as Zoho allows; may need “Last meaningful touch” field + workflows). |

### 3.5 Closed Won

| Topic | Decision |
|-------|----------|
| Requirements | **Won / handoff notes** (mandatory). |
| Notify | **Sales manager** on Closed Won. |
| Other fields (PO, delivery) | **Not** mandatory in v1. |

### 3.6 Closed Lost

| Topic | Decision |
|-------|----------|
| Always | **Lost Reason**. |
| Competitor | Required when **Lost Reason** is **Lost to competitor / bought elsewhere** OR **Price** (stakeholder chose **always require Competitor for Price**). |
| Next try date | Required when **Lost Reason** is one of: **Timing**, **Budget**, **No decision**, **Project paused**, **Tender lost but future opportunities** (exact picklist labels TBD — map to org picklist or add values via API). |

### 3.7 Deal rollup for Blueprint simplicity

| Topic | Decision |
|-------|----------|
| Negotiation gate on Deal | Stakeholder approved a **Deal-level helper field** (e.g. boolean **Any quote shared with customer**) **updated by workflow** when any related Quote’s share checkbox flips, so **Blueprint or validation** can key off one Deal field. |

### 3.8 Uncheck “shared” after Negotiation

| Topic | Decision |
|-------|----------|
| If share unchecked | **Recompute** rollup; if **no** linked quote remains shared → **alert** Deal owner (and optionally manager) to **fix data or move stage back manually** (do **not** auto-rewind stage in v1). |

### 3.9 Amount

| Topic | Decision |
|-------|----------|
| Deal Amount | **Required before Quote Sent** (enforce on transition **Solution / Value → Quote Sent** or equivalent validation on stage + Amount). |

---

## 4) Schema to create / verify

Implement idempotent provisioning (new script or extend `provision_phase2_fields.py` / layouts) unless fields already exist.

### 4.1 Deal (custom fields — labels are canonical; API names via Zoho conventions)

| Label (UI) | Type | Purpose |
|------------|------|---------|
| Discovery summary | Multi-line | Required before Quote Sent (with other discovery fields). |
| Current machines / setup | Multi-line | Discovery. |
| Applications | Multi-line (or picklist later) | What they print / want to print. |
| Budget / financing status | Picklist | e.g. Unknown, Rough range, Firm, Financing needed, Tender, … |
| Primary Quote | Lookup → Quotes | Expected winning quote among A/B. |
| Any quote shared with customer | Checkbox (read-only for users if possible) | **Maintained by automation** from Quote checkboxes. |
| Won / handoff notes | Multi-line | Required on Closed Won. |
| Next try / follow-up date | Date | Required for specific Lost Reasons (§3.6). |

**Layout:** Add a **Discovery** section on **Standard Deals** layout; place fields for rep clarity.

**Existing:** **Stage**, **Amount**, **Lost Reason**, **Competitor**, **Line of business** — use as-is; ensure Competitor + Lost Reason behaviors match §3.6.

### 4.2 Quotes (custom field)

| Label (UI) | Type | Purpose |
|------------|------|---------|
| Quote shared with customer | Checkbox | **Quote Owner** sets when customer received this quote option. |

**Linking:** Ensure Deal–Quote relation is used (standard **Potential Name** / Deal lookup on Quote — confirm API names in org metadata).

---

## 5) Automation: rollup `Any quote shared with customer`

**Behavior:**

- On **Quote** create/edit: when **`Quote shared with customer`** is true for **any** Quote whose Deal = this Deal, set Deal **`Any quote shared with customer` = true**.
- When **all** related Quotes for that Deal are false or unrelated quotes removed, set Deal flag **false**.
- Optionally: on Deal **enter Negotiation**, re-run check (scheduled function) — v1 can rely on Quote-triggered updates only.

**Implementation options (pick what works in-org):**

1. **Workflow on Quotes** (create/edit) → **Custom Function** (Deluge) that queries sibling quotes for the same Deal and PATCHes the Deal flag.  
2. If sibling iteration is painful in workflow, **Custom Function** triggered from Quote workflow that uses `related_records` / search API (v8) to recompute.

**Idempotency:** Multiple quotes true should still yield Deal flag true.

---

## 6) Workflow rules catalog (automate via API)

Follow payload patterns in `tools/zoho/provision_quoted_line_machine_sku_workflow.py` and Zoho’s [Configure Workflow Rule API](https://www.zoho.com/crm/developer/docs/api/v8/config-workflow.html). Create **task actions** via the documented task/action APIs if required.

### 6.1 Leads

| Rule name (suggested) | Trigger | Actions |
|----------------------|---------|---------|
| Lead — contact same day | Lead created | Create task **Contact lead** (due today or +1 business day). |
| Lead — stale contact (optional) | Lead not modified / no activity 2–3 days | Email/reminder to owner (if feasible). |

### 6.2 Deals — stage entered

| Stage entered | Task subject (suggested) | Due offset |
|---------------|---------------------------|------------|
| Qualification | Schedule discovery / confirm opportunity | +2 days |
| Needs Analysis | Complete discovery fields on Deal | +3 days |
| Solution / Value | Finalize configuration; create Quote(s); set Primary Quote | +5 days |
| Quote Sent | Follow up on quote | **+2 days** |
| Negotiation | Confirm decision timeline; address objections | +3 days |
| Closed Won | Handoff / delivery kickoff | +1 day |
| Closed Lost | If Next try date set — create task on that date (or single task “Revisit on …”) | per field |

### 6.3 Deals — Closed Won

| Trigger | Actions |
|---------|---------|
| Stage = Closed Won | Email / notify **sales manager**; include Deal link, Amount, Primary Quote. |

### 6.4 Stale open deals (14 days)

**Intent:** Stage unchanged **and** no meaningful customer-facing activity.

**Practical v1:** Workflow on **Schedule** / **Date-based** criteria if available: “Deal Modified Time older than 14 days” **and** Stage not in (Closed Won, Closed Lost) → task **Review deal stage**.  
**Better v2:** Custom datetime **Last meaningful activity** updated by workflows on Call/Meeting/Task completion — stakeholder intent in Q&A was stage **or** activity; document any gap.

### 6.5 Rollup failure / integrity

| Trigger | Actions |
|---------|---------|
| Deal in **Negotiation**, `Any quote shared` becomes **false** | Notify Deal owner (email/task): fix share flags or move stage back. |

### 6.6 Optional nudge

| Trigger | Actions |
|---------|---------|
| Primary Quote or Amount changed | Task: **Reconcile Deal Amount with quotes** (stakeholder uses manual Amount). |

---

## 7) Blueprint specification (Deals) — or validation-equivalent

If **Blueprint definition** is API-automatable, implement this graph; otherwise implement **Validation Rules** with the same conditions (on **save** / **stage change** per Zoho capabilities).

### 7.1 Allowed transitions

- Full forward path + **rollbacks** (e.g. Negotiation → Quote Sent) with **optional** rollback reason field (stakeholder did not require — skip v1 unless trivial).
- **Closed Lost** from any **open** stage.

### 7.2 Mandatory fields per transition

| Transition | Mandatory before transition |
|------------|----------------------------|
| **Qualification → Needs Analysis** | Light: e.g. **Line of business** if not already mandatory; optional short note (stakeholder: keep light). |
| **Needs Analysis → Solution / Value** | **Discovery summary**, **Current machines**, **Applications**, **Budget/financing**. |
| **Solution / Value → Quote Sent** | All **Needs Analysis → Solution / Value** fields + **Deal Amount** filled + **≥1 Quote** linked to Deal + **Primary Quote** set. |
| **Quote Sent → Negotiation** | Deal **`Any quote shared with customer` = true** (rollup from any linked Quote). **No** extra “negotiation topic” field required. |
| **Negotiation → Closed Won** | **Won / handoff notes**. |
| **Any open → Closed Lost** | **Lost Reason**; **Competitor** if reason is **competitive** or **Price**; **Next try date** if reason ∈ {Timing, Budget, No decision, Project paused, Tender future opportunity} (exact picklist mapping required). |

### 7.3 Quotes module

- Do **not** require a separate Quote Blueprint for v1 unless stakeholder expands scope.

---

## 8) Permissions & profiles

- Ensure **Quote Owner** can edit **`Quote shared with customer`**; restrict others if needed.
- Deal fields: reps can edit discovery fields; **`Any quote shared`** should be **read-only** on layout (automation-only).

---

## 9) OAuth / scopes

Minimum (adjust per Zoho console):

- `ZohoCRM.settings.fields.ALL` (or CREATE/UPDATE)  
- `ZohoCRM.settings.layouts.ALL` (place fields on Standard Deals / Quotes)  
- `ZohoCRM.settings.workflow_rules.ALL` (or CREATE/UPDATE)  
- `ZohoCRM.settings.automation` / **functions** if creating Deluge via API  
- `ZohoCRM.modules.ALL` for record PATCH tests  
- **Blueprints:** if Settings API supports blueprint **create**, include the documented scope; else validation rules scope if separate  

Run `tools/zoho/zoho_doctor.py` if tokens lack scopes.

---

## 10) Implementation checklist (for the next agent)

1. Pull **live metadata** (`make zoho-cache-summary` or field/layout GETs) — confirm Deals **Standard** layout id, Quote layout, Deal–Quote lookup API names.  
2. **Create fields** (idempotent).  
3. **Patch layouts** — Discovery section; read-only rollup; Quote checkbox placement.  
4. Implement **rollup** (Quote workflow + Deluge).  
5. Implement **workflows** (Lead + Deal catalog §6).  
6. Implement **Blueprint** **or** **Validation rules** for §7; verify transitions in UI with test records.  
7. **Picklists:** align **Lost Reason** values with §3.6; add missing values via API.  
8. **Test matrix:** create Lead → Deal → walk stages → create 2 Quotes → mark one shared → enter Negotiation → Closed Won; repeat Closed Lost paths (Price / Timing) for Competitor + Next try rules.  
9. Document **any** manual step remaining and why (API gap).

---

## 11) Files to reference in this repo

- `tools/zoho/pipelines_seed.json` — stage order.  
- `docs/zoho/SALES-PIPELINE-AND-STAGES.md` — pipeline philosophy.  
- `tools/zoho/provision_phase2_fields.py`, `provision_phase2_layouts.py` — field/layout patterns.  
- `tools/zoho/provision_quoted_line_machine_sku_workflow.py` — workflow POST + function caveats.  
- `tools/zoho/provision_delete_blueprints.py` — blueprint settings GET/DELETE (research create).  
- `tools/zoho/zoho_tokens.py` — auth.

---

## 12) Non-goals (v1)

- Manager approval gates.  
- Technical pre-quote approval.  
- Auto-sync Deal Amount from Quote totals.  
- Mandatory “next scheduled activity” blocking (use tasks instead).  
- Separate pipeline per Line of business (filter only).

---

*Handoff generated from stakeholder Q&A (2026). Update this file if decisions change.*
