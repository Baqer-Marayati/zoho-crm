# Agent prompt: Deals + Quotes — Deluge functions + workflow wiring (zero human clicks in Zoho)

**Use this as the user message (or system briefing) for a new Cursor agent chat.**  
**Goal:** Ensure the three custom Deluge functions exist in Zoho CRM with the **correct API names and body**, are **updated in place** if they already exist, and that **function-backed workflow rules** from this repo are created or repaired—**without asking the human to open Zoho Setup or paste code manually**, unless every documented API path fails after a documented attempt log.

**Context:** After legacy MCPs were removed, rely on the **four official Zoho CRM MCP servers** (`zoho-crm-data-insights`, `zoho-crm-data-operations`, `zoho-crm-module-customisation`, `zoho-crm-automation`) **plus** the repo’s authenticated CRM REST scripts in `tools/zoho/`. See `docs/zoho/AUTOMATION-STACK.md`: **Developer Hub function source** is managed via REST (`GET /settings/functions/{api_name}/code`, multipart `POST`/`PUT /settings/functions` with `.ds` code files, `POST /settings/automation/functions` for workflow wrappers), not via MCP.

---

## Preconditions (verify, do not ask the user to “go set up” if already satisfied)

1. **Repository:** Open the **Zoho-CRM** workspace at the repo root (paths below are relative to it).
2. **OAuth for scripts:** `tools/zoho/.env` exists with a valid refresh token and scopes including at least **`ZohoCRM.settings.ALL`** (and modules as needed). If provisioning fails with **401/403**, run `make zoho-doctor` and fix tokens/scopes per `tools/zoho/README.md`—execute commands yourself; do not hand-wave.
3. **Toolchain:** `tools/zoho/venv` usable; from repo root, `make zoho-deals-quotes-process` runs `provision_deals_quotes_process.py`.
4. **MCP:** Official four servers are connected in Cursor; use them for **discovery, workflow inspection, and record-level verification**—read each tool’s schema before calling.

---

## Canonical spec (read first)

| File | Purpose |
|------|---------|
| `artifacts/zoho/manual_upload/deals_quotes_process/functions_manifest.json` | API names, modules, arguments, purposes, paths to FULL/BODY deluge |
| `artifacts/zoho/deluge/quote_recompute_deal_shared.deluge` | Source used by `provision_deals_quotes_process.py` for API `POST` bodies |
| `artifacts/zoho/deluge/quote_shared_owner_guard.deluge` | Same |
| `artifacts/zoho/deluge/deal_stage_gate_guard.deluge` | Same |
| `docs/zoho/DEALS-QUOTES-PROCESS-PROVISIONING.md` | What the script provisions and known API gaps |
| `tools/zoho/provision_deals_quotes_process.py` | Idempotent create/link logic, workflow rules |

**The three functions (exact `api_name` / name string the org must use):**

1. `quote_recompute_deal_shared` — module **Quotes** — argument `quoteId` (string) mapped to Quote Id.  
2. `quote_shared_owner_guard` — module **Quotes** — argument `quoteId` (string).  
3. `deal_stage_gate_guard` — module **Deals** — argument `dealId` (string).

If Zoho already shows shells with different names, **rename or recreate to match** via API—do not invent new names (workflow wiring in the script keys off these strings).

---

## Execution order (you run this; the human does not)

### Phase A — Provision + discover failures

1. From repo root:

   ```bash
   cd tools/zoho && ./venv/bin/python provision_deals_quotes_process.py --dry-run
   ```

   Review output for function POST / wrapper steps and workflow plan.

2. Run for real:

   ```bash
   make zoho-deals-quotes-process
   ```

   (from repo root), or the same script without `--dry-run` from `tools/zoho`.

3. Capture **full stderr/stdout** if any step reports HTTP errors (especially `POST .../settings/automation/functions` or missing catalog ids).

### Phase B — MCP verification (official bundles only)

Use **zoho-crm-automation** where possible:

- **`getWorkflowRules`** — confirm rules exist for quote rollup, owner guard, deal stage guard, and related stage tasks; note rule names/ids from the response.  
- **`getWorkflowConfigurations`** — before creating or updating rules, respect constraints (module, trigger types, associate actions).

Use **zoho-crm-data-insights** (`getModules`, `getFields`, `executeCOQLQuery`) to confirm Deals/Quotes field API names still match what Deluge expects (e.g. `Any_quote_shared_with_customer`, `Quote_shared_with_customer`, discovery fields).

Use **zoho-crm-data-operations** only for **non-destructive** test updates on **sandbox/test records** if the human has them; do not mass-edit production data without explicit approval.

If workflows reference function actions by id but functions are wrong/empty, **`updateWorkflowRule` / `postWorkflowRule`** (per tool schema) may be used **after** valid function **action** ids exist—prerequisite is always: function exists in catalog + automation wrapper id resolved (the Python script already encodes this pattern).

### Phase C — “Exists but wrong body” / API create rejected

1. **Inspect** script logic in `provision_deals_quotes_process.py`: `_create_function`, `_find_settings_functions_catalog_id`, `_create_automation_wrapper_from_catalog`.  
2. **If** functions appear in Developer Hub but Deluge is outdated: consult current [Zoho CRM v8 Functions API](https://www.zoho.com/crm/developer/docs/api/v8/functions.html) (and related settings docs). If **`PUT`/`PATCH`** to update function source is available for this org, add a **minimal** idempotent updater to the provision script or a one-off `tools/zoho/` helper, then re-run `make zoho-deals-quotes-process`.  
3. **If** only the **full editor paste** path works (no update API), document the exact error payloads and **`__apis`** findings in your final report and in `docs/zoho/DEALS-QUOTES-PROCESS-PROVISIONING.md` under a dated “API attempt log” subsection—**still** avoid asking the user to paste if you can close the gap with code on a later pass.

### Phase D — Re-run and close

After functions and wrappers are correct:

```bash
make zoho-deals-quotes-process
```

Repeat MCP checks until workflow rules reference the expected functions and no “skipped because function unavailable” messages remain in the script output.

---

## Success criteria (all must be true)

- [ ] `GET /crm/v8/settings/functions` (via `zoho_doctor`, repro script, or logged provision output) lists all three names with stable ids.  
- [ ] Automation **wrapper** rows exist where the script expects them, so workflow **associate** actions can use **`type: functions`** with valid ids (per Zoho’s workflow payload rules).  
- [ ] `provision_deals_quotes_process.py` completes **without** gaps like `Custom function … could not be created/found via API`.  
- [ ] **MCP** `getWorkflowRules` shows the function-backed rules aligned with `docs/zoho/DEALS-QUOTES-PROCESS-PROVISIONING.md`.  
- [ ] Human was **not** asked to use Setup → Functions → paste—unless you attach a **short, evidence-based** block explaining that all v8 endpoints you tried returned errors (status + snippet), and the product requires UI.

---

## What not to do

- Do not duplicate legacy MCP server names or rely on removed bundles.  
- Do not change the three function API names without updating `FUNCTIONS` in `provision_deals_quotes_process.py` and `functions_manifest.json`.  
- Do not mark the task complete while only **COQL** or read-only MCP calls succeeded—**write path** (functions + workflows) must be verified.

---

## Optional: one-line user message to start the agent

Copy-paste into a new Agent chat:

> Follow `docs/zoho/handoffs/AGENT-PROMPT-DEALS-DELUGE-FUNCTIONS.md` end-to-end: run provisioning with dry-run then live, fix or extend `tools/zoho/provision_deals_quotes_process.py` if Zoho rejects function create/update, use only the four official Zoho CRM MCPs to verify and repair workflow rules, and deliver a short success checklist with any remaining API gaps evidenced by HTTP responses—no manual Zoho UI steps for me unless impossible after documented API attempts.
