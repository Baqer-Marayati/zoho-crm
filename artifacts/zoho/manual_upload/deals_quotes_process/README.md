# Deals + Quotes — manual upload package (fallback only)

**Default:** push everything from the repo with:

```sh
make zoho-deals-quotes-process
```

That command runs `tools/zoho/provision_deals_quotes_process.py`, which:

- Ensures Deals/Quotes fields and Standard layouts (idempotent).
- Creates or links **Developer Hub** functions under `GET /crm/v8/settings/functions`, verifies source via `GET .../code`, and repairs drift with multipart `POST`/`PUT /settings/functions` (`.ds` code file) when needed.
- Creates **automation wrapper** rows via `POST /crm/v8/settings/automation/functions` so workflow **instant actions** can reference `type: functions`.
- Creates workflow **task actions** and **workflow rules** (including function-backed rules).

Details and HTTP evidence: [`../../../../docs/zoho/DEALS-QUOTES-PROCESS-PROVISIONING.md`](../../../../docs/zoho/DEALS-QUOTES-PROCESS-PROVISIONING.md).

Use **this folder** only if you are blocked by an API error after a documented attempt log and need the Zoho **function editor** (FULL vs BODY_ONLY paste).

## 1. Deluge files (function editor escape hatch)

Zoho path: **Setup → Developer Hub → Functions** (catalog also appears on `GET /crm/v8/settings/functions`). When you create the shell, use **Category: Automation**.

Create these exact functions (the internal **API name** must match the first column):

| Function name | Module | Argument |
| --- | --- | --- |
| `quote_recompute_deal_shared` | Quotes | `quoteId` string mapped to Quote Id |
| `quote_shared_owner_guard` | Quotes | `quoteId` string mapped to Quote Id |
| `deal_stage_gate_guard` | Deals | `dealId` string mapped to Deal Id |

For each function:

1. Use the exact API name above (not only the display label).
2. Create the argument exactly as listed.
3. If Zoho shows an empty editor that accepts a full function, use the `*_FULL.deluge` file.
4. If Zoho already generated the outer function signature, use the matching `*_BODY_ONLY.deluge` file.
5. Save the function.

Files:

- `functions/01_quote_recompute_deal_shared_FULL.deluge`
- `functions/01_quote_recompute_deal_shared_BODY_ONLY.deluge`
- `functions/02_quote_shared_owner_guard_FULL.deluge`
- `functions/02_quote_shared_owner_guard_BODY_ONLY.deluge`
- `functions/03_deal_stage_gate_guard_FULL.deluge`
- `functions/03_deal_stage_gate_guard_BODY_ONLY.deluge`
- `functions_manifest.json`

After all three functions are saved, run:

```sh
make zoho-deals-quotes-process
```

The script resolves Developer Hub (`/settings/functions`) entries by API name, creates automation wrapper rows when workflows need them, and adds the function-backed workflow rules.

## 2. Lost Reason values

Reference CSV only: `picklists/lost_reason_missing_values.csv` (values were aligned in-org via API; see provisioning doc).

## 3. Not automatable via public API (this org)

**Blueprint** process definition: UI is **Setup → Process Management → Blueprint**; public settings APIs here expose **record transition** execution (`/{module}/{id}/actions/blueprint`), not graph create/update — see `DEALS-QUOTES-PROCESS-PROVISIONING.md` attempt log.

**Validation rules** (hard block on save): readable dependency metadata exists; create/update payload not used in this repo — native workflow rollback rules are the current substitute for Proposal / Quote.

`deal_stage_gate_guard` remains a prepared/supplementary enforcement function, but the current live Proposal / Quote gate should be the native workflow rollback rules from `provision_deals_quotes_process.py` unless the workflow function wrapper has a verified `dealId` argument mapping.
