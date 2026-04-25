# Repository layout — where to look

This file is a **stable map** of the Zoho-CRM work tree. For execution order, use [`IMPLEMENTATION-CHECKLIST.md`](./IMPLEMENTATION-CHECKLIST.md) and [`../PROJECT-STATUS.md`](../PROJECT-STATUS.md).

| Path | Role |
|------|------|
| `docs/zoho/INDEX.md` | Single **navigation** entry for all Zoho docs (start here) |
| `docs/PROJECT-STATUS.md` | **Scope, next steps**, and dated notes |
| `docs/zoho/IMPLEMENTATION-CHECKLIST.md` | **Phased** go-live order |
| `docs/zoho/QUOTE-TEMPLATE-LEARNINGS.md` | **Quote PDF** template: design rules, `provision_quote_template.py`, pitfalls |
| `tools/zoho/` | **Python** — OAuth, provisioning, sync (`README.md` + `Makefile` at repo root) |
| `tools/zoho/venv/` | Local virtualenv (gitignored) |
| `tools/zoho/archive/` | **Alternate or legacy** JSON seeds (e.g. old pipeline variants) — not default paths |
| `artifacts/zoho/` | **Versioned, non-secret** data: CSVs, picklists, Deluge copies, client scripts, product extensions |
| `artifacts/zoho/import/` | Product and catalog import CSVs (clean before import) |
| `.cursor/rules/` | Cursor rules for this repo (e.g. Zoho API automation) |
| `legal/` | Legal text (e.g. T&Cs) — source for copy-paste or attachment policy, not Zoho config |

**Secrets:** only `tools/zoho/.env` (and similar) on disk — **never** committed. See `tools/zoho/.env.example`.

**Building on this repo:** add new automation under `tools/zoho/` with a focused script + doc line in `tools/zoho/README.md`; add durable decisions under `docs/zoho/`.
