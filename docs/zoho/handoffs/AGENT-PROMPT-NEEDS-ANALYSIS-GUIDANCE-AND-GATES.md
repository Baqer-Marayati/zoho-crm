# Agent prompt: Needs Analysis guidance + Proposal/Quote gates (automated)

**Use this entire document as the user briefing for a new Cursor agent chat** (paste into the message or attach the file).  
**Goal:** Implement the **Needs Analysis** experience and **Proposal / Quote** enforcement agreed with the stakeholder **inside Zoho CRM**, using **repo scripts + REST + official Zoho MCP** first, and **Safari “Allow JavaScript from Apple Events”** only where Zoho exposes no supported settings API—so the stakeholder does **not** repeat manual clicks in **Setup** after one-time machine/account prerequisites.

---

## One-time prerequisites (not counted as “manual Zoho build work”)

These are **outside** Blueprint/workflow configuration; do **not** ask the stakeholder to recreate workflows by hand in Setup.

| Prerequisite | Owner | Notes |
|--------------|-------|--------|
| Repo | Agent | Workspace root = **Zoho-CRM**; paths below are relative to it. |
| OAuth | Stakeholder already set | `tools/zoho/.env` with refresh token and scopes including **`ZohoCRM.settings.ALL`** (and modules as needed). Run `make zoho-doctor` if calls fail. |
| Safari admin session | Agent drives after permission | For **UI-only** surfaces (Blueprint definitions, some validation rules, Client Scripts), use **Safari** with an **admin** Zoho CRM session on `crm.zoho.com` (or correct DC). **Stakeholder enables once:** Safari → **Develop** → **Allow JavaScript from Apple Events**. Without this, `osascript` cannot execute `do JavaScript` in Safari. |
| Chrome vs Safari | Agent judgment | If Chrome holds the only login but is not admin, **still** use Safari for admin CSRF/cookie replay per `.cursor/rules/zoho-crm-api-automation.mdc` and `docs/zoho/AUTOMATION-STACK.md` §4.1. |

**Honesty rule:** If an operation remains impossible without a human physically clicking in Zoho after documented API + Safari-JS attempts, **stop**, log exact HTTP responses and URL patterns in `docs/zoho/DEALS-QUOTES-PROCESS-PROVISIONING.md` (dated subsection), and report what remains—but **exhaust** automation paths below first.

---

## Canonical business behavior (implement exactly)

| Transition | Behavior | Rationale |
|------------|----------|-----------|
| **Qualification → Needs Analysis** | **Soft landing.** Rep **may** enter **Needs Analysis** without filling discovery fields first. | Coaching stage; reduce friction at first move. |
| **While in Needs Analysis** | **Guide:** reminders / instructions to complete discovery fields **after** they land (tasks; optional in-app emphasis via Client Script if justified). | Makes expectations explicit without blocking the stage change. |
| **Into Proposal / Quote** | **Hard gate.** Rep **must not** remain in **Proposal / Quote** until discovery fields are complete **per policy** (see fields below). Blueprint/validation would be ideal, but the current API-driven implementation is server-side rollback workflows. | Covers Kanban/API moves even when form Client Scripts do not run. |

**Discovery fields (API names on Deals)** — mandatory **before Proposal / Quote** is valid:

- `Discovery_summary` — text / textarea (large).  
- `Current_machines_setup` — text today; stakeholder direction is **eventually** a **subform** (one row per machine + **annual total A4** per row). **v1:** enforce non-empty string on existing field; **v2 (optional follow-up):** add subform + migrate guard/Blueprint/validation—only if this prompt’s Phase A is green and stakeholder confirms.  
- `Applications` — textarea (large) is appropriate.  
- `Budget_financing_status` — **picklist** (single select); options must be **curated business statuses**, not free text—ensure layout exposes values and gate treats empty / `-None-` as invalid.

**Already deployed enforcement (do not duplicate blindly):**

- `tools/zoho/provision_deals_quotes_process.py` — canonical Proposal / Quote gate in this org: native workflow rollback rules for blank required fields, plus the shared Stage rollback field update.
- `artifacts/zoho/deluge/deal_stage_gate_guard.deluge` — still kept in sync as a supplementary/legacy guard and for Needs Analysis task cleanup, but the observed workflow wrapper had `arguments: null`; do not treat it as the Proposal gate unless the wrapper mapping is verified fixed.

---

## Read before coding

| File | Why |
|------|-----|
| `docs/zoho/handoffs/AGENT-HANDOFF-DEALS-BLUEPRINT-WORKFLOWS.md` | Full Deals/Quotes process intent and API risks. |
| `docs/zoho/DEALS-QUOTES-PROCESS-PROVISIONING.md` | API gaps (Blueprint definition **not** exposed on settings REST in this org’s probe). |
| `docs/zoho/AUTOMATION-STACK.md` | MCP bundles vs Python; Safari Client Script path §4.1. |
| `.cursor/rules/zoho-crm-api-automation.mdc` | Execute scripts in-terminal; Safari CSRF headers for internal `v2.2` settings calls. |
| `tools/zoho/provision_deals_quotes_process.py` | **Existing** workflow: **Needs Analysis** → creates task **“Deal - complete discovery task”** via `_stage_update_trigger` + `stage_task_map`. |
| `artifacts/zoho/client_scripts/deal_stage_field_visibility.js` | Pattern for Deals UI behavior. |

---

## Phase A — Needs Analysis: workflows + reminders (API-first)

**Intent:** When **Stage** becomes **Needs Analysis**, the owner gets **clear, field-level instructions** and optional **follow-up nudges** while discovery remains incomplete.

### A1. Verify current automation

1. Run `make zoho-deals-quotes-process` (or dry-run first if you changed code).  
2. Use **zoho-crm-automation** MCP: **`getWorkflowRules`** — confirm a rule named like **`Deal stage - Needs Analysis task`** exists and fires on **stage transition** into **Needs Analysis**.  
3. If missing or wrong, fix **`_ensure_workflows`** / `stage_task_map` in `provision_deals_quotes_process.py`—do **not** create one-off rules only in the UI.

### A2. Improve task copy (required)

Update the **task action** backing **`Deal - complete discovery task`** so **Description** includes:

- Explicit **labels + API names**:  
  `Discovery_summary`, `Current_machines_setup`, `Applications`, `Budget_financing_status`.  
- One line: **Budget** must be a **picklist choice**, not prose.  
- One line: **Proposal / Quote is blocked** until these are complete (so reps understand why).  

Keep **Subject** scannable (e.g. “Complete discovery on Deal — Needs Analysis”).  
Re-provision idempotently so existing org rules pick up the updated **task action** definition (follow patterns already in script for `PUT` task actions if implemented; if Zoho requires new action id, clone safely and rewire rule).

### A3. Optional second workflow — “still in Needs Analysis, discovery incomplete”

If **date-based** or **field-update** triggers support **AND** criteria without excessive noise:

- **Trigger:** schedule (e.g. **3 days after** stage entered Needs Analysis) **or** periodic review **only when** Stage = Needs Analysis **and** any discovery field still empty / `-None-`.  
- **Action:** **second task** or **email** to Owner with same checklist (lower priority than first).

**Caution:** Zoho criteria cannot always express “any of four fields empty” cleanly without a **formula/checkbox** field maintained by workflow—only add if you can implement **without** stakeholder manual Setup; otherwise skip v1 and document.

### A4. Optional Client Script (Safari path only)

If rep behavior needs **in-form banner** when **Stage = Needs Analysis** and fields incomplete:

- Reuse **`docs/zoho/AUTOMATION-STACK.md` §4.1**: compile via `compile_script`, POST/PUT `cscript_snippets`, correct static resources, Deals/`Potentials` routing.  
- Do **not** replace workflows; this is **supplementary**.

### Phase A verification

- Move a **test Deal** Qualification → Needs Analysis: **exactly one** primary coaching task (unless you deliberately added scheduled nudge), description lists **four** fields.  
- Confirm **no** blocking validation on **Needs Analysis** entry.

---

## Phase B — Proposal / Quote: hard gate (layered)

**Preference order** (best UX → broadest coverage):

1. **Blueprint** — transition **into** **Proposal / Quote** with **mandatory fields**: the four discovery fields (and any others org keeps e.g. Amount, Quotes—**must match** `deal_stage_gate_guard`).  
2. **Validation rule** — Stage = **Proposal / Quote** ⇒ fields non-empty / picklist valid. Attempt **`GET/POST .../settings/validation_rules`** and MCP **module-customisation** tools first; if unsupported, document.  
3. **Native workflow rollback** — current proven API-driven enforcement in this org. Use workflow criteria with `value: "${EMPTY}"` and a field update that returns Stage to **Needs Analysis**. This covers Kanban/API stage updates where Client Scripts do not run.
4. **`deal_stage_gate_guard`** — useful for Needs Analysis task cleanup, but do **not** rely on it for Proposal / Quote unless the workflow wrapper shows a real `dealId` argument mapping. The observed wrapper had `arguments: null`.

### B1. REST/MCP attempt log

- Probe **`GET /crm/v8/__apis`** and MCP for blueprint **definition** create/update.  
- If **API_NOT_SUPPORTED** or absent (per `DEALS-QUOTES-PROCESS-PROVISIONING.md`), proceed to **B2**.

### B2. Blueprint via Safari admin session (Apple Events)

When settings REST cannot define Blueprints:

1. Ensure **Allow JavaScript from Apple Events** is enabled (stakeholder one-time).  
2. Open **admin** Safari tab: CRM **Setup → Process Management → Blueprint** (exact menu labels may vary slightly by edition).  
3. Use **`osascript`** → `tell application "Safari" to do JavaScript "..." in front document` to:  
   - Read CSRF/org headers from the page context **or** copy cookies + `X-ZCSRF-TOKEN` / `X-CRM-ORG` pattern from §4.1.  
   - **`fetch`** internal Zoho endpoints observed in **Network** inspector while manually performing **one** blueprint save in a **throwaway** tab session captured by stakeholder **once**—**agent** should replicate via captured `curl`-equivalent in JS, **not** require stakeholder to build Blueprint.  
4. If **no** internal JSON API is discoverable, implement **UI-driving JS** only if stable (click sequences break on Zoho UI changes)—prefer **validation rule** capture via same Safari method or strengthen **guard** + **layout mandatory** for Proposal/Quote **only** if product supports stage-dependent layout required flags via **`updateLayout`** API.

**Deliverable:** Either a **Blueprint** published for Deals covering **Standard** pipeline stages used by the org, or a **written proof** (HAR notes + API index) that automation cannot publish Blueprints yet, with **validation + guard** as the enforced combo.

### B3. Align server-side rollback

- Keep `tools/zoho/provision_deals_quotes_process.py` as the canonical implementation.
- Maintain the `Deal gate rollback - Proposal ...` workflows for blank discovery fields, `Amount`, `Primary_Quote`, and invalid `Budget_financing_status = -None-`.
- Keep `deal_stage_gate_guard` source consistent with repo artifacts, but treat it as supplementary until wrapper argument mapping can be proven via `GET /settings/automation/functions/{id}`.

### Phase B verification

- Moving a Deal to **Proposal / Quote** with empty `Discovery_summary` (etc.) returns it to **Needs Analysis** after workflow execution.  
- With all four complete (and any retained Amount/Quote checks), transition **succeeds**.  
- Kanban drag may briefly show the move, then snap back after workflows run unless a Blueprint/Validation Rule is later published.

---

## Phase C — Budget picklist values (if missing)

- Use **module-customisation** MCP or `provision_*` scripts to ensure **`Budget_financing_status`** picklist values match workshop wording; rerun layout provisioning if needed (`provision_deals_quotes_process.py` discovery section).  
- Confirm **`deal_stage_gate_guard`** treats `-None-` as missing (already does for this field).

---

## MCP and script discipline

1. **Read** each MCP tool descriptor under Cursor `mcps/*/tools/*.json` **before** invoking.  
2. Prefer **`provision_deals_quotes_process.py`** changes + `make zoho-deals-quotes-process` over ad-hoc creates.  
3. Cache: before heavy metadata pulls, use `.cache/zoho/metadata.summary.md` or `make zoho-cache-summary`.  
4. **Never** commit tokens, secrets, or customer PII.

---

## Final report (agent must produce)

Short markdown summary:

| Item | Status |
|------|--------|
| Needs Analysis task workflow | Created/updated + MCP id/name |
| Task description lists 4 API fields | Yes/No |
| Optional nudge workflow / Client Script | Done/Skipped + reason; note that Client Scripts are form UX only, not Kanban/API hard gates |
| Proposal/Quote enforcement | Blueprint / Validation / Guard-only |
| Safari internal API used | Endpoints or “none found” |
| Native rollback workflows aligned | Workflow names + field update id |
| Stakeholder recurring manual steps in Zoho | **Must state “none”** or list unavoidable gaps |

---

## Success criteria

- **Needs Analysis:** entering the stage **never blocked** by discovery; **instruction/reminder** fires reliably (task + optional extras).  
- **Proposal / Quote:** discovery fields **cannot** be skipped in normal rep flows; current implementation returns invalid Deals to **Needs Analysis** via server-side workflows.  
- **All configuration changes** are **repeatable** from repo (`make` + artifacts), not one-off UI edits—except where Zoho product **requires** browser-session writes, which must still be **scripted** (`osascript` + Safari JS) and **documented**.
