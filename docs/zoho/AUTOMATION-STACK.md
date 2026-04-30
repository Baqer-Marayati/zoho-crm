# Zoho automation stack (what runs the org for you)

Goal: **do almost everything from this repo** (scripts + AI) and **minimize one-off clicks in Zoho**. You will still hit Zoho’s hard limits sometimes (see below).

## 1. Primary: `tools/zoho` (Python “CLI”)

This is the main automation surface for this project.

| Action | Command |
|--------|---------|
| Install toolchain (Homebrew **Node** + `npx`, Python **venv** + deps) | `make zoho-setup` (from repo root) |
| OAuth + `.env` | `cd tools/zoho && ./venv/bin/python connect_zoho.py` |
| Health / scopes | `./venv/bin/python zoho_doctor.py` or `make zoho-doctor` |
| Smoke test | `./venv/bin/python zoho_ping.py` |

**Grant scopes (one comma-separated line in Zoho API Console → Generate Code):**

Minimum for this repo’s scripts + API discovery:

`ZohoCRM.modules.ALL,ZohoCRM.settings.ALL,ZohoCRM.users.ALL,ZohoCRM.apis.READ`

Optional **maximum** CRM REST surface (COQL, bulk, org, notifications) — see [`tools/zoho/.env.example`](../../tools/zoho/.env.example) and [Zoho — scopes (v8)](https://www.zoho.com/crm/developer/docs/api/v8/scopes.html). After widening scopes, generate a **new** grant and refresh token.

- **settings.ALL** — fields, layouts, workflows, map dependency, most provisioning scripts.
- **apis.READ** — `GET /crm/v8/__apis` API index (discovery, debugging). Without it, `zoho_doctor` shows a **WARN** on `__apis` but CRM + settings calls can still work.

After you add scopes, you need a **new grant code** and a **new refresh token** (Zoho ties scopes to the refresh token).

## 2. Official Zoho MCP (for AI assistants and agents)

Zoho hosts the MCP servers; you wire **Cursor** to the endpoint Zoho gives you. This is separate from `tools/zoho/.env` (API refresh token) — MCP uses its own OAuth in the browser when you click **Connect**.

**References**

- [Zoho MCP](https://www.zoho.com/mcp/) — product overview and signup.
- [Zoho MCP console](https://mcp.zoho.com/) — create servers and copy the client URL.
- [Zoho CRM MCP — overview](https://www.zoho.com/crm/developer/docs/mcp/overview.html) — CRM tool bundles (data insights, CRUD, customization, workflows).
- [Zoho CRM API v8](https://www.zoho.com/crm/developer/docs/api/v8/) — REST baseline behind both MCP and `tools/zoho`.

**Cursor setup (recommended path)**

1. Sign in to [mcp.zoho.com](https://mcp.zoho.com/), click **Create MCP Server**, name it (e.g. `cursor-crm`).
2. Under **Tools** → **Add Tool**, add **Zoho CRM** (and any other Zoho apps you want). Enable only the actions you need.
3. Open **Connect** in the sidebar → **Cursor** (under MCP clients) → **Copy** the JSON snippet Zoho generates. Prefer that snippet over any template — Zoho may change the exact `command` / `args`.
4. Merge the snippet into your MCP config and save:
   - **Global:** `~/.cursor/mcp.json` (works across projects), or
   - **Project:** `.cursor/mcp.json` in this repo (if your Cursor build loads it).
5. Restart Cursor or reload MCP. In **Settings → Tools & MCP**, connect if prompted; complete **Allow** / **Accept** in the browser (Zoho OAuth).
6. Use **Agent** mode in chat so the agent can call MCP tools.

**Prerequisites:** `npx` (Node.js) on your PATH — Zoho’s Cursor config uses `mcp-remote` to bridge the hosted MCP URL.

**Template:** [`../../tools/zoho/cursor_mcp.example.json`](../../tools/zoho/cursor_mcp.example.json) — only if you need a structural example; replace the last `args` value with your real MCP URL from step 3.

**Regenerating the URL:** In Zoho MCP, **Regenerate API Key** invalidates the old URL — update `mcp.json` everywhere you pasted it.

### 2.1 MCP tool bundles (typical Cursor install)

In Cursor, hosted Zoho CRM MCP often appears as **several server identifiers** (names vary by how you added tools). Descriptor JSON lives under your Cursor project’s `mcps/` folder. A typical split:

| Server (example id) | What it maps to (v8-ish) | Representative tools |
|---------------------|--------------------------|----------------------|
| **zoho-crm-module-customisation** | Settings: modules, fields, layouts | `getModules`, `getFields`, `createFields`, `updateField`, `getLayouts`, `updateLayout`, … |
| **zoho-crm-automation** | Workflows, tasks, field updates, webhooks | `getWorkflowRules`, `postWorkflowRule`, `updateWorkflowRule`, `getWorkflowConfigurations`, `createWorkflowTasks`, `createFieldUpdates`, … |
| **zoho-crm-data-operations** | Module record CRUD | `getRecords`, `createRecords`, `updateRecords`, `deleteRecords`, related records |
| **zoho-crm-data-insights** | Read/analytics | `executeCOQLQuery`, `getModules`, `getFields` |

You may also see older or duplicate aliases (**user-CRM-Data-Metadata**, **user-CRM-Automation-Workflow**, **user-Lead-Management**) with overlapping tools — prefer the **zoho-crm-**\* bundles when both exist so schemas stay aligned with current Zoho CRM MCP.

**Gaps (still use `tools/zoho` Python today):**

- **Custom functions:** MCP does not replace the CRM REST function catalog and source endpoints. Use `GET /crm/v8/settings/functions`, `GET /crm/v8/settings/functions/{api_name}/code`, multipart `POST`/`PUT /crm/v8/settings/functions` with a `.ds` code file, and `POST /crm/v8/settings/automation/functions` for workflow wrapper rows. Repo: `provision_deals_quotes_process.py`, `provision_quoted_line_machine_sku_workflow.py`, `zoho_doctor.py`.
- **Client Scripts:** the public/MCP surface does not reliably create Developer Hub Client Scripts. Use the admin browser-session path in §4.1 when you need zero manual setup.
- **Blueprint *definitions***, **some validation-rule writes**, and other settings not exposed in v8 docs — still product limits.

**Agent discipline:** Read each tool’s JSON descriptor (parameters and constraints) before calling; workflow `post`/`update` payloads are strict (criteria shape, action ids, `GET /workflow_configurations` first when the tool says so).

## 3. Community MCP servers (optional, self-hosted)

Third-party MCP servers can expose Zoho CRM to **Cursor**, Claude Desktop, etc. They still need OAuth client + refresh token (same ideas as `tools/zoho`). Examples to evaluate (not endorsed; check code and trust before use):

- [junnaisystems/Zoho-CRM-MCP](https://github.com/junnaisystems/Zoho-CRM-MCP) (Python MCP server).

If you add one, keep **client secret and refresh token** out of the repo; use environment variables and Cursor’s MCP config UI or your OS secret store.

## 4. What will *not* be 100% API-driven

These are product limits, not gaps in this repo:

| Item | Reality |
|------|---------|
| **OAuth / trust** | First-time **Zoho API Console** client + **refresh token** (and MCP browser **Connect**) still require a human in the loop. After that, agents and scripts run without repeated login. |
| **Custom function source** | Raw Deluge `POST /settings/automation/functions` can return `INVALID_DATA` for `arguments.function`. Prefer **`/settings/functions`** for source: `GET /settings/functions/{api_name}/code` reads Deluge, and multipart `POST`/`PUT /settings/functions` with JSON `metadata` plus a `.ds` `code` file creates/updates catalog functions. Workflow **instant actions** still need wrapper ids from **`GET /crm/v8/settings/automation/functions`** or a thin **`POST /settings/automation/functions`** with `function: {id: <catalog_id>}`. |
| **Blueprint process graphs**, **some validation rules** | The UI location is **Setup → Process Management → Blueprint**. v8/v9 APIs and MCP metadata currently expose Blueprint support and record-level transition execution (`/{module}/{record_id}/actions/blueprint`), not settings-side Blueprint definition create/update. Design fallbacks with workflows + Deluge until Zoho exposes a definition endpoint. |
| **Some org settings** | Teamspace, certain UI-only toggles, or API preview features may need a one-time UI action. The repo documents those in the relevant `docs/zoho/*.md` file. |

### 4.1 Developer Hub Client Scripts via Safari admin session

Use this when a task needs **Client Script** creation/update and the public APIs return `INVALID_REQUEST_METHOD`, `EXPECTED_PARAM_MISSING`, or missing `metadata/code` errors.

**Prerequisite:** use an admin browser session, preferably **Safari** when Chrome is logged in as the test user. Ask the user to enable **Develop → Allow JavaScript from Apple Events** once. Then use `osascript` with `tell application "Safari" to do JavaScript ... in front document`.

**Working endpoint family (observed 2026-04-30):**

- `GET /crm/v2.2/settings/cscript_pages?include_extra_details=true`
- `GET /crm/v2.2/settings/cscript_snippets?page_uuid=<page_uuid>`
- `POST /crm/v2.2/settings/cscript_snippets` — creates a snippet and can auto-create the page.
- `PUT /crm/v2.2/settings/cscript_snippets/<snippet_uuid>` — updates a snippet.
- `PUT /crm/v2.2/settings/cscript_pages/<page_uuid>` — updates page metadata/static resources.

Always send browser-session headers:

- `X-ZCSRF-TOKEN: crmcsrfparam=<crmcsr cookie>`
- `X-CRM-ORG: <org id>`
- `Content-Type: application/json` for writes.

**Payload rules discovered:**

- Client Script code is not executed from raw `source_code`. Zoho executes compiled `async_code`.
- Compile in the page using:
  `Lyte.registeredMixins['crm-cscript-global-mixin'].compile_script(source, [])`
- Send all three content keys: `content.source_code`, `content.async_code`, `content.source_map`.
- Page metadata needs Zoho core static resources. Copy from a working page if needed: `ZRC-1.0`, `Kernel`, `ZDK-1.0`, `DotSDK-2.0`, `Concluder`. Without them, the target form can show `_cscript._globalEngine._state._c_cs_message = ["issue with cscript info/static resource"]`.
- For Deals, the UI label is **Deals** but internal routes may use **Potentials**. Discover selector values from the page (`get_module_definitions`) rather than guessing.

**Verification:**

1. Reload the target form.
2. Inspect `_cscript._globalEngine._state` in the browser session.
3. Confirm the target script resource URL is loaded and the expected form labels/behavior changed.

## 5. Operating discipline

1. Run **`zoho_doctor.py`** after any token or scope change.
2. Prefer **idempotent** provision scripts (re-run is safe) over manual edits in Zoho.
3. Keep **Deluge and JSON manifests** in `artifacts/`; treat Zoho as a deployment target.

## See also

- [GETTING-STARTED.md](./GETTING-STARTED.md) — API Console and first connection.
- [../../tools/zoho/README.md](../../tools/zoho/README.md) — script index and `make` targets.
