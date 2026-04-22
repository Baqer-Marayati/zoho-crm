# Developer workflow (this repository)

This repo is **Zoho-first**: documentation under `docs/zoho/`, automation under `tools/zoho/`. There is **no** Canvas, Power Apps, or Dataverse content here.

## Folder map

```text
Zoho-CRM/
  README.md                 # Project entry
  .gitignore                # Ignores .env, venv, local reference clones
  docs/
    PROJECT-STATUS.md       # Update when milestones change
    README.md               # Doc index
    zoho/                   # All playbooks
  tools/zoho/
    .env.example            # Copy to .env — never commit .env
    requirements.txt        # Python deps for API scripts
    README.md               # How to run scripts
  artifacts/zoho/           # Optional non-secret exports (see artifacts/README.md)
```

## Environment (local only)

1. Copy `tools/zoho/.env.example` to `tools/zoho/.env`.
2. Fill values from Zoho API Console (OAuth client + refresh token). See [GETTING-STARTED.md](./GETTING-STARTED.md).
3. `chmod 600 tools/zoho/.env` on macOS/Linux.

Do **not** paste production tokens into chat or commit them.

## Python (when you add scripts)

```bash
cd tools/zoho
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
# ./venv/bin/python your_script.py
```

Use `venv/` only under `tools/zoho/`; it is gitignored everywhere.

## Git and GitHub

- **Feature work:** short branch names, e.g. `feature/bulk-import-leads`.
- **PRs:** especially for anything under `artifacts/` or new dependencies in `requirements.txt`.
- **Main branch** should always build/run the documented path (even if “run” is only “doc is accurate”).

## What does *not* belong in this repo

- Entire clones of upstream apps (use `git clone` elsewhere, or add paths under `../` outside this project).
- Power Platform solution `.zip` or `pac` output (out of scope).
- **Secrets** in any tracked file.

## Power BI

Report **definitions** are typically edited in **Power BI Desktop** (Windows) and published to the service. This repo can hold **exported snippets** (M/DAX) as `.md` or small files *if* you want them versioned — optional; add a `docs/powerbi/` folder if you start doing that, and keep datasets aligned with your Zoho model.
