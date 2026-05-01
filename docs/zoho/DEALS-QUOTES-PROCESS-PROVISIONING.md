# Deals + Quotes Process Provisioning

**Related:** extended **agent** copy-paste prompts and the full business/tech blueprint live in [`handoffs/README.md`](./handoffs/README.md).

Provisioning entry point:

```sh
make zoho-deals-quotes-process
```

Implemented through Zoho CRM v8 APIs:

- Deals fields: `Discovery_summary`, `Current_machines_setup`, `Applications`, `Budget_financing_status`, `Primary_Quote`, `Any_quote_shared_with_customer`, `Won_handoff_notes`, `Next_try_follow_up_date`.
- Quotes field: `Quote_shared_with_customer`.
- Standard Deals and Quotes layouts have the fields placed for reps.
- Workflow task actions and workflow rules:
  - Lead contact same day.
  - Deal stage follow-ups for Qualification, Needs Analysis, **Proposal / Quote** (+3 days), Negotiation, Closed Won, and Closed Lost revisit.
  - Needs Analysis task copy is normalized by `deal_stage_gate_guard`: the workflow task action creates the task, and the function updates the open task Description with the four discovery API fields, the Budget picklist note, and the Proposal / Quote block note; duplicate Needs Analysis discovery tasks are closed.
  - **Proposal / Quote server-side gate:** native workflow rules named `Deal gate rollback - Proposal ...` detect missing required fields and apply the field update `Deal gate rollback to Needs Analysis`. This covers Kanban, API, and form saves because it does not rely on Client Scripts.
  - 14-day stale open Deal review based on `Modified_Time`.
  - Closed Won manager notification via a task intended for `${!Deals.Owner.Reporting_To}`.
  - Negotiation integrity reminder if `Any_quote_shared_with_customer` becomes false.

Known API gaps from the provisioning run:

- Zoho CRM UI location for Blueprint definitions is **Setup → Process Management → Blueprint**. The live org currently has no configured Blueprints there.
- Zoho CRM v8/v9 exposes Blueprint data/update for record transitions (`/{module}/{record_id}/actions/blueprint`), but `/__apis` shows no Blueprint definition create/update endpoint under settings/process management.
- `/settings/validation_rules` is readable/dependency-visible, but no public create/update payload is exposed for API-only hard blocking in this org.
- Raw Deluge `POST /settings/automation/functions` can reject with `INVALID_DATA` at `$.functions[0].arguments.function`. The provisioner now prefers the Developer Hub function catalog endpoints instead:
  - `GET /settings/functions/{api_name}/code` to verify source.
  - `PUT /settings/functions/{api_name}` as multipart `metadata` plus a `.ds` `code` file to repair source drift.
  - `POST /settings/functions` with the same multipart payload for missing catalog functions, followed by automation wrapper linking through `POST /settings/automation/functions`.
  - `POST /settings/functions/{api_name}/actions/publish` when a created function needs publishing.

API attempt log, 2026-04-29:

- `GET /crm/v8/settings/blueprints` returned HTTP 204; `GET /crm/v9/settings/blueprints` also returned HTTP 204.
- `POST /crm/v8/settings/blueprints` and `PUT /crm/v8/settings/blueprints` returned HTTP 400 `API_NOT_SUPPORTED`.
- `GET /crm/v8/__apis` and `GET /crm/v9/__apis` list record-level `.../{id}/actions/blueprint` endpoints, but no settings Blueprint definition create/update endpoint.
- `POST /crm/v8/settings/automation/blueprints` returned HTTP 400 `API_NOT_SUPPORTED` with `supported_version: 9`; the matching v9 path returned HTTP 404 `INVALID_URL_PATTERN` and is not listed in v9 `/__apis`.
- `GET /settings/functions/{api_name}/code` returned HTTP 200 and exposed Deluge source for all three functions.
- `PUT /settings/functions/quote_shared_owner_guard` with JSON and form payloads returned HTTP 400 `EXPECTED_PARAM_MISSING` for `metadata, code`.
- `PUT /settings/functions/quote_shared_owner_guard` with multipart `metadata` plus `code` file extension `.deluge`, `.txt`, or `.dg` returned HTTP 415 `INVALID_FILE_EXTENSION`.
- `PUT /settings/functions/quote_shared_owner_guard` with multipart `metadata` plus `.ds` code file returned HTTP 200 `function updated successfully`; the same path repaired `deal_stage_gate_guard`.
- `GET /settings/functions/{api_name}/actions/download` returned HTTP 404 `INVALID_URL_PATTERN`; use `/code` instead.

API attempt log, 2026-05-01:

- `make zoho-deals-quotes-process` reprobed Blueprint/validation support: `GET /crm/v8/settings/blueprints` and `GET /crm/v9/settings/blueprints` returned HTTP 204; v8/v9 `/__apis` still list record-level `/{module}/{id}/actions/blueprint` only and no settings-side Blueprint definition create/update path.
- `GET /crm/v8/settings/validation_rules?module=Deals` returned HTTP 204. v8 `/__apis` lists read/dependency paths for validation rules, but no public create/update endpoint was found.
- `PUT /settings/automation/tasks/{task_id}` accepted `Description` field mappings but task metadata preserved/dropped them inconsistently. The repeatable implementation therefore uses the existing `deal_stage_gate_guard` Deluge function to update the Needs Analysis task record Description after the workflow task action creates it.
- A live move of Deal `V900` into `Proposal / Quote` exposed two false assumptions:
  - Deals Client Scripts do not cover every stage-change path; Kanban/stage updates can bypass form scripts.
  - The `deal_stage_gate_guard` catalog function has `dealId`, but its workflow wrapper returned `arguments: null`. Public wrapper update payloads either failed or returned Zoho internal errors, so the Proposal gate must not depend on that wrapper receiving the record id.
- Verified replacement: native workflow criteria using `value: "${EMPTY}"` correctly matches null/blank Deal fields, and a workflow field update can roll Stage back to `Needs Analysis`. This was verified on `V900`: after an API move to `Proposal / Quote`, workflows returned the Deal to `Needs Analysis`.
- API nuance: `/settings/automation/field_updates` supports listing with `module=Deals` and `feature_type=workflow`, but rejected the same name `filter` shape used by workflow rules. The provisioner lists Deals field updates and matches by `name` locally.
- API nuance: updating existing workflow criteria via `PUT` can return duplicate-condition errors or condition-limit errors. The provisioner creates rollback workflows when missing and treats existing rollback workflows as current rather than rewriting their criteria.

Resolved after the initial run:

- Missing `Lost_Reason` values were added via the Standard Deals layout API and `provision_phase2_layouts.py` was rerun so the Stage -> Lost Reason dependency includes them for `Closed Lost`.
- Function source drift was repaired by API: `quote_shared_owner_guard` and `deal_stage_gate_guard` now match the repo Deluge artifacts, and `make zoho-deals-quotes-process` reports all three function sources as `ok`.
- Needs Analysis guidance is repeatable from the repo: `Deal stage - Needs Analysis task` remains active, and `deal_stage_gate_guard` is still useful for soft task-description cleanup when the workflow function receives an id.
- Proposal / Quote is now guarded by native rollback workflows for `Discovery_summary`, `Current_machines_setup`, `Applications`, `Budget_financing_status`, `Amount`, and `Primary_Quote`, plus `Budget_financing_status = -None-`. These workflows use the shared Stage rollback field update and are the canonical server-side enforcement path until Blueprint/Validation Rule definition APIs are available.

Test walkthrough after closing the API gaps:

1. Create Lead; verify task `Contact lead`.
2. Convert to Deal in `Qualification`; verify discovery scheduling task.
3. Move through `Needs Analysis`; verify discovery task.
4. Attempt **Proposal / Quote** with discovery fields blank; verify the Deal returns to `Needs Analysis` after workflow execution.
5. Fill discovery fields, `Amount`, create at least one linked Quote, and set `Primary Quote`.
6. Move to **Proposal / Quote**; verify combined proposal/quote follow-up task due +3 days.
7. Mark one linked Quote `Quote shared with customer`; verify Deal `Any quote shared with customer` rollup.
8. Move to `Negotiation`; verify negotiation follow-up task and stage guard behavior.
9. Close Won with `Won / handoff notes`; verify handoff task and manager notification task.
10. Repeat Closed Lost paths for `Price` plus `Competitor`, and timing/budget/no-decision paths plus `Next try / follow-up date`.
