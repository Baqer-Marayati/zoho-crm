# Zoho CRM (with Power BI) — project monorepo

This repository is the **working home** for a **Zoho CRM Professional**–based sales stack: lead-to-deal pipeline, quotes and product library, and **Power BI** reporting for management. The goal is to keep **automation, scripts, and documentation in Git** while Zoho and Microsoft remain the live systems of record.

## What lives here

| Path | Purpose |
|------|--------|
| `docs/zoho/` | Zoho and Power BI playbooks, architecture, and repo workflow |
| `docs/PROJECT-STATUS.md` | Current phase, scope, and decisions (keep this current) |
| `tools/zoho/` | API helpers and integration scripts (OAuth, data sync) — *to be added as you build* |
| `artifacts/` | Optional exports and snapshots; **no secrets** (see `artifacts/README.md`) |
| `archive/` | Deprecated Microsoft / Dataverse / canvas experiments — **read-only history** |

## What does *not* live here

- Your Zoho **login** and **refresh tokens** (use env vars, never commit; see `tools/zoho/.env.example`).
- A full 1:1 “clone” of the Zoho org as code. Zoho is configured in the product; this repo holds **automation, specs, and copies** of scripts.

## First steps

1. Read `docs/zoho/GETTING-STARTED.md`.
2. Skim `docs/PROJECT-STATUS.md` and adjust scope for your org.
3. When scripts exist, copy `tools/zoho/.env.example` to `.env` (gitignored) and run scripts locally or in CI.

## Renaming the folder on disk (optional)

The Git remote name and this README use **Zoho CRM** as the product name. If your local folder is still named `Power Platform`, you can rename the parent directory in Finder, or from the **Microsoft Platform** parent folder run:

`mv "Power Platform" "Zoho-CRM"`

Re-open the project in your editor after renaming.

## Legacy material

The original **Power Platform approvals starter** and the **Dataverse / canvas** experiments are under `archive/`. They are not part of the active Zoho plan unless you explicitly revive them.
