# `tools/zoho` — Zoho CRM API automation

Add **small, focused** scripts here: OAuth test, bulk import, health checks, webhooks, or one-off data fixes.

## Setup

```bash
cd tools/zoho
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

### Easiest: one interactive command (recommended)

Run this in **Terminal** (not in Cursor chat). The script asks for Client ID, Client Secret, and grant code **locally** and writes `tools/zoho/.env` for you.

```bash
cd tools/zoho
./venv/bin/python connect_zoho.py
```

Get **Client ID**, **Client Secret**, and a fresh **grant code** from [Zoho API Console](https://api-console.zoho.com/) → **Self Client** (same flow as before). If you are not on US Zoho, type the right **Accounts URL** when prompted (e.g. `https://accounts.zoho.eu`).

**Scopes (Generate Code):** For API smoke tests we call **Leads**, so include at least **`ZohoCRM.modules.ALL`** (comma-separated if you add more). To use the **Users** API later, add **`ZohoCRM.users.ALL`** and generate a **new** grant + refresh token (scopes are fixed per refresh token).

**Pipelines automation:** To run `provision_pipelines.py`, include **`ZohoCRM.settings.ALL`** (or equivalent settings scopes) in the grant and refresh `ZOHO_REFRESH_TOKEN`. Then:

```bash
./venv/bin/python provision_pipelines.py --dry-run
./venv/bin/python provision_pipelines.py
```

Edit `pipelines_seed.json` so stage names match your org’s **Deals → Stage** picklist labels.

**After you change stage lists** for existing pipelines, push updates to Zoho:

```bash
./venv/bin/python provision_pipelines.py --sync
# or: make zoho-sync-pipelines
```

**Unified model:** `pipelines_seed.json` now defines only **Standard (Standard)**; sector is **Line of business** on Lead/Deal (see `provision_phase2_fields.py`). `pipelines_seed.radiology.json` is **archived** (Radiology = picklist value, not a pipeline).

### Phase 2 fields (Line of business, Lost Reason, Competitor)

Requires **`ZohoCRM.settings.ALL`** (or `settings.fields.CREATE`) on your refresh token.

```bash
./venv/bin/python provision_phase2_fields.py --dry-run
./venv/bin/python provision_phase2_fields.py
```

Then run **layout + map dependencies** (needs `settings.layouts` + `settings.map_dependency` scopes, or `settings.ALL`):

```bash
./venv/bin/python provision_phase2_layouts.py --dry-run
./venv/bin/python provision_phase2_layouts.py
# or: make zoho-phase2-layouts
```

Finish any remaining **UI** steps in [`../../docs/zoho/PHASE2-AUTOMATED.md`](../../docs/zoho/PHASE2-AUTOMATED.md) (conversion mapping, stage–probability %).

**Do not paste those secrets into AI chat** — only into this Terminal wizard.

### Manual path (`.env` by hand)

```bash
cp .env.example .env
chmod 600 .env
# fill .env, then:
./venv/bin/python exchange_grant.py
./venv/bin/python zoho_ping.py
```

## Running

```bash
./venv/bin/python zoho_ping.py
# Add your own scripts alongside these helpers.
```

## Documentation

- `../../docs/zoho/DEVELOPER.md` — repo workflow
- `../../docs/zoho/GETTING-STARTED.md` — Zoho API Console and scopes

Zoho’s official **CRM API v2** docs: use the current URL for your data center (`.com` / `.eu` / etc.) from [Zoho’s developer site](https://www.zoho.com/crm/developer/docs/api/v2/).
