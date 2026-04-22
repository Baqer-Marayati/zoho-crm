# Artifacts (optional exports)

Place **versioned, non-secret** exports here when you need an audit trail or restore point. This repo is **Zoho + Power BI**–first; Microsoft solution exports are **optional** and mostly historical.

## Folders

| Folder | Use |
|--------|--------|
| `solutions/` | **Microsoft** Dataverse / Power Platform solution `.zip` exports (only if you still use or archive them) |
| `metadata/` | Unpacked or diff-friendly metadata (e.g. `pac solution unpack` output) |
| `zoho/` *(create if needed)* | Zoho-originated **documentation exports**, CSV schema snapshots, or other **non-secret** dumps you want in git (never raw OAuth tokens) |

## Rules

- **No secrets** — scrub connection strings, client secrets, refresh tokens, and tenant-only URLs before committing.
- **Naming** — use a consistent stem so files sort in time order, e.g. `{env}-{YYYY-MM-DD}-{label}`.

## Git workflow

Prefer pull requests for anything that changes `artifacts/`, so someone scans filenames and that nothing sensitive slipped in.
