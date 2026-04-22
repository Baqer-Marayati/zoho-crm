# `tools/zoho` — Zoho CRM API automation

Add **small, focused** scripts here: OAuth test, bulk import, health checks, webhooks, or one-off data fixes.

## Setup

```bash
cd tools/zoho
cp .env.example .env
# edit .env with your OAuth client + refresh token (never commit)
chmod 600 .env
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

## Running

```bash
# Example once you add a script:
# ./venv/bin/python hello_zoho.py
```

## Documentation

- `../../docs/zoho/DEVELOPER.md` — repo workflow
- `../../docs/zoho/GETTING-STARTED.md` — Zoho API Console and scopes

Zoho’s official **CRM API v2** docs: use the current URL for your data center (`.com` / `.eu` / etc.) from [Zoho’s developer site](https://www.zoho.com/crm/developer/docs/api/v2/).
