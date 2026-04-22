# Zoho API helpers (placeholder)

Add scripts here for:

- **OAuth** token health checks
- **Bulk import** of leads, products, or attachments
- **Scheduled** sync or backup jobs (if you outgrow Zoho’s built-in options)

## Setup (when scripts exist)

```bash
cd tools/zoho
python3 -m venv venv
./venv/bin/pip install --upgrade pip
# ./venv/bin/pip install -r requirements.txt
```

## Secrets

- Copy `.env.example` to `.env` in **this directory** (or repo root) and add real values.
- `chmod 600 .env` on Unix-like systems.
- **Never** commit `.env` or real tokens.

## Related documentation

- `../../docs/zoho/GETTING-STARTED.md`
- `../../docs/zoho/REPO-BASED-DEVELOPMENT.md`
