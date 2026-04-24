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

## 3. Community MCP servers (optional, self-hosted)

Third-party MCP servers can expose Zoho CRM to **Cursor**, Claude Desktop, etc. They still need OAuth client + refresh token (same ideas as `tools/zoho`). Examples to evaluate (not endorsed; check code and trust before use):

- [junnaisystems/Zoho-CRM-MCP](https://github.com/junnaisystems/Zoho-CRM-MCP) (Python MCP server).

If you add one, keep **client secret and refresh token** out of the repo; use environment variables and Cursor’s MCP config UI or your OS secret store.

## 4. What will *not* be 100% API-driven

These are product limits, not gaps in this repo:

| Item | Reality |
|------|--------|
| **POST custom function (raw Deluge)** | Often returns `INVALID_DATA` for `arguments.function`. First-time create in Zoho **Functions** UI is common; the repo still stores Deluge in `artifacts/zoho/deluge/` and scripts attach **workflows** by ID. |
| **List functions returns `[]` but UI shows a function** | Possible org/API quirks, or the function is under a name your token cannot list. Use the function’s **ID from the URL** and `--function-id=…` on the provisioner. |
| **Some org settings** | Teamspace, certain UI-only toggles, or API preview features may need a one-time UI action. The repo documents those in the relevant `docs/zoho/*.md` file. |

## 5. Operating discipline

1. Run **`zoho_doctor.py`** after any token or scope change.
2. Prefer **idempotent** provision scripts (re-run is safe) over manual edits in Zoho.
3. Keep **Deluge and JSON manifests** in `artifacts/`; treat Zoho as a deployment target.

## See also

- [GETTING-STARTED.md](./GETTING-STARTED.md) — API Console and first connection.
- [../../tools/zoho/README.md](../../tools/zoho/README.md) — script index and `make` targets.
