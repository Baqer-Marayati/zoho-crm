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
  - Deal stage follow-ups for Qualification, Needs Analysis, Solution / Value, Quote Sent (+2 days), Negotiation, Closed Won, and Closed Lost revisit.
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

Resolved after the initial run:

- Missing `Lost_Reason` values were added via the Standard Deals layout API and `provision_phase2_layouts.py` was rerun so the Stage -> Lost Reason dependency includes them for `Closed Lost`.
- Function source drift was repaired by API: `quote_shared_owner_guard` and `deal_stage_gate_guard` now match the repo Deluge artifacts, and `make zoho-deals-quotes-process` reports all three function sources as `ok`.

Test walkthrough after closing the API gaps:

1. Create Lead; verify task `Contact lead`.
2. Convert to Deal in `Qualification`; verify discovery scheduling task.
3. Move through `Needs Analysis` and `Solution / Value`; verify discovery/quote-prep tasks.
4. Fill discovery fields, `Amount`, create at least one linked Quote, and set `Primary Quote`.
5. Move to `Quote Sent`; verify `Follow up on quote` due +2 days.
6. Mark one linked Quote `Quote shared with customer`; verify Deal `Any quote shared with customer` rollup.
7. Move to `Negotiation`; verify negotiation follow-up task and stage guard behavior.
8. Close Won with `Won / handoff notes`; verify handoff task and manager notification task.
9. Repeat Closed Lost paths for `Price` plus `Competitor`, and timing/budget/no-decision paths plus `Next try / follow-up date`.
