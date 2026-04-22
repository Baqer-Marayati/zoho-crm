# Artifacts (optional, non-secret)

Store **redacted** exports you want in version control: field lists, sample CSVs, **screenshot PDFs of quote layouts** (no customer PII), or other documentation aids.

| Folder | Use |
|--------|--------|
| `zoho/` | Zoho-related snapshots (e.g. schema exports, **scrubbed** data samples) |

## Rules

- **No** OAuth tokens, **no** `client_secret`, **no** live customer records unless policy allows and data is **anonymized**.
- Prefer **one folder per “drop”** with a clear date: `zoho/2026-04-22-field-dictionary/…`

Pull requests for changes under `artifacts/` should get a quick human review.
