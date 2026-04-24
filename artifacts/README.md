# Artifacts (optional, non-secret)

Store **redacted** exports you want in version control: field lists, sample CSVs, **screenshot PDFs of quote layouts** (no customer PII), or other documentation aids.

| Folder | Use |
|--------|--------|
| `zoho/picklists/` | Starter CSVs for picklist values (lost reason, payment terms, quote line options, etc.) |
| `zoho/import/` | CSV templates and Canon catalog waves for product/lead import (no live PII in Git) |
| `zoho/import/canon_product_line/` | Build manifests for consolidated machine lines (five machines, Colorado, LFP, …) |
| `zoho/product_extensions/` | JSON that drives quote-line finisher / POD text per product code |
| `zoho/deluge/` | Reference copies of Deluge (source of truth remains in Zoho) |
| `zoho/client_scripts/` | Notes for client-side / layout-related behavior |
| `zoho/teamspace/` | Teamspace (Next Gen) JSON manifests, e.g. Direct department |
| `zoho/` (other) | Dated one-off drops: `zoho/2026-04-22-field-dictionary/…` |

## Rules

- **No** OAuth tokens, **no** `client_secret`, **no** live customer records unless policy allows and data is **anonymized**.
- Prefer **one folder per “drop”** with a clear date: `zoho/2026-04-22-field-dictionary/…`

Pull requests for changes under `artifacts/` should get a quick human review.
