# Agent and assistant notes (Zoho-CRM)

This repository automates and documents a **Zoho CRM Professional** rollout plus **Power BI** (see `docs/PROJECT-STATUS.md`).

- **Docs entrypoint:** `docs/zoho/INDEX.md` — open this first to navigate active vs archived content. **Folder map:** `docs/zoho/REPO-LAYOUT.md`.
- **Quote PDF template:** `docs/zoho/QUOTE-TEMPLATE-LEARNINGS.md` — canonical layout (50/50 meta + address, no grey panel, date clipping). HTML source: `tools/zoho/provision_quote_template.py`.
- **Build order:** `docs/zoho/IMPLEMENTATION-CHECKLIST.md` — do not improvise phase order.
- **Developer setup:** `docs/zoho/DEVELOPER.md`, `docs/zoho/GETTING-STARTED.md`; scripts live in `tools/zoho/`; secrets only in `tools/zoho/.env` (gitignored).
- **Automation index:** `tools/zoho/README.md` and `make help` from the repo root.
- **Workshop context (archive):** `docs/zoho/archive/configuration-rounds/`.
- **Cursor rule:** `.cursor/rules/zoho-crm-api-automation.mdc` — run scripts in-terminal when the task is clearly Zoho API work; confirm before bulk-destructive or org-wide security changes.

Never commit or paste real OAuth refresh tokens, client secrets, or customer PII.
