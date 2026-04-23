# Artifacts (optional, non-secret)

Store **redacted** exports you want in version control: field lists, sample CSVs, **screenshot PDFs of quote layouts** (no customer PII), or other documentation aids.

| Folder | Use |
|--------|--------|
| `zoho/picklists/` | Starter CSVs for picklist values (lost reason, payment terms, etc.) |
| `zoho/import/` | CSV templates for lead/product imports (no live PII in Git) |
| `zoho/` (other) | Schema exports, **scrubbed** samples, dated drops |

## Rules

- **No** OAuth tokens, **no** `client_secret`, **no** live customer records unless policy allows and data is **anonymized**.
- Prefer **one folder per “drop”** with a clear date: `zoho/2026-04-22-field-dictionary/…`

Pull requests for changes under `artifacts/` should get a quick human review.
