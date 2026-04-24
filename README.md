# Zoho CRM + Power BI — monorepo

This repository holds **docs and automation** for a **Zoho CRM Professional** sales stack: pipeline, quotes, product library, and **Power BI** reporting. Zoho and Microsoft 365 are the live systems; this folder is the **versioned** companion (scripts, env templates, and playbooks).

## Layout

| Path | Purpose |
|------|--------|
| `docs/zoho/` | Zoho and Power BI playbooks, architecture, developer workflow |
| `docs/zoho/INDEX.md` | **Single docs entrypoint** for Zoho implementation |
| `docs/zoho/IMPLEMENTATION-CHECKLIST.md` | **Phased go-live** — start here after workshops |
| `docs/PROJECT-STATUS.md` | Current scope and next steps — update as you go |
| `docs/zoho/archive/` | Workshop **configuration rounds** (3–8) and other **historical** notes |
| `tools/zoho/` | Python **API** helpers — OAuth, pipelines, product sync, one-off tools |
| `tools/zoho/archive/` | Legacy or alternate **JSON** seeds (e.g. old pipeline layout) |
| `artifacts/zoho/` | **Non-secret** data: import CSVs, picklists, Deluge copies, product extensions |
| `make help` | From repo root: lists **zoho-*** **Makefile** shortcuts |

## Quick start (developer)

1. **Docs entrypoint:** [`docs/zoho/INDEX.md`](docs/zoho/INDEX.md) (then follow [`docs/zoho/IMPLEMENTATION-CHECKLIST.md`](docs/zoho/IMPLEMENTATION-CHECKLIST.md) for phased execution). **Picklist/import starters:** [`artifacts/zoho/picklists/`](artifacts/zoho/picklists/), [`artifacts/zoho/import/`](artifacts/zoho/import/).
2. Read `docs/zoho/DEVELOPER.md` and `docs/zoho/GETTING-STARTED.md`.
3. `make venv`, then run **`tools/zoho/connect_zoho.py`** in Terminal for guided OAuth (secrets stay local — do not paste them into AI chat). See `tools/zoho/README.md` for `provision_pipelines.py --sync`, `zoho_ping.py`, etc.

## Secrets

Never commit real tokens. Use `tools/zoho/.env` locally with `chmod 600 .env` on macOS/Linux.

## Remote

The Git **remote** URL does not have to match the folder name. This project is the **Zoho CRM** work tree on disk (e.g. `…/Zoho-CRM`).
