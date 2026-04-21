# Artifacts

Place **exported solutions** and optional **unpacked metadata** here. Keep **secrets out of git** (connection references, passwords, tenant-only URLs); scrub or use environment-specific settings before committing.

## Folders

| Folder | Use |
|--------|-----|
| `solutions/` | Solution `.zip` exports (portal **Export** or **PAC**). |
| `metadata/` | Optional unpacked solution or source for diff/review (e.g. `pac solution unpack`). |

## Naming (required)

Use a single pattern so exports sort chronologically and stay identifiable:

```text
{environment}-{YYYY-MM-DD}-{version}-{managed|unmanaged}.zip
```

**Examples**

- `dev-2026-04-21-v1-unmanaged.zip`
- `test-2026-04-22-v2-managed.zip`

**Parts**

- **environment** — short label (`dev`, `test`, `prod`, or your tenant/env code).
- **date** — export day (UTC or local, but stay consistent).
- **version** — `v1`, `v2`, … or semver if you prefer.
- **managed \| unmanaged** — matches the export type.

For unpacked folders under `metadata/`, mirror the same stem as a directory name, e.g. `dev-2026-04-21-v1-unmanaged/`.

## Git workflow (strict)

- Prefer merging changes under `artifacts/` via **pull request** so filenames and contents get a quick review.
- Optional: use a branch such as `exports/dev` for frequent drops, then open a PR to `main` when a snapshot is “canonical.”
