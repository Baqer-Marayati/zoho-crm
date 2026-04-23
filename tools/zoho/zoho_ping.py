#!/usr/bin/env python3
"""
Smoke test: refresh an access token and call Zoho CRM GET Leads (1 row).

Uses the Leads endpoint so a typical Self Client grant with ZohoCRM.modules.ALL
works. The Users API needs ZohoCRM.users.ALL — see Zoho scopes docs.

Requires in tools/zoho/.env:
  ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET, ZOHO_REFRESH_TOKEN
Optional:
  ZOHO_ACCOUNTS_URL (default https://accounts.zoho.com)
  ZOHO_API_DOMAIN — if unset, taken from the refresh-token response
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent / ".env"


def main() -> int:
    load_dotenv(ENV_PATH)

    accounts = os.environ.get("ZOHO_ACCOUNTS_URL", "https://accounts.zoho.com").rstrip("/")
    client_id = os.environ.get("ZOHO_CLIENT_ID", "").strip()
    client_secret = os.environ.get("ZOHO_CLIENT_SECRET", "").strip()
    refresh_token = os.environ.get("ZOHO_REFRESH_TOKEN", "").strip()
    api_domain_env = os.environ.get("ZOHO_API_DOMAIN", "").strip().rstrip("/")

    if not all([client_id, client_secret, refresh_token]):
        print(
            "Set ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET, ZOHO_REFRESH_TOKEN in tools/zoho/.env",
            file=sys.stderr,
        )
        return 1

    tok = requests.post(
        f"{accounts}/oauth/v2/token",
        data={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        },
        timeout=60,
    )
    if not tok.ok:
        print(f"Refresh failed HTTP {tok.status_code}", file=sys.stderr)
        print(tok.text[:2000], file=sys.stderr)
        return 1

    try:
        tdata = tok.json()
    except json.JSONDecodeError:
        print("Non-JSON token response:", tok.text[:500], file=sys.stderr)
        return 1

    access = tdata.get("access_token")
    api_domain = (tdata.get("api_domain") or api_domain_env or "").rstrip("/")
    if not access:
        print("No access_token in response:", json.dumps(tdata)[:500], file=sys.stderr)
        return 1
    if not api_domain:
        print(
            "No api_domain in token response. Add ZOHO_API_DOMAIN to .env "
            "(from the first successful token exchange).",
            file=sys.stderr,
        )
        return 1

    headers = {"Authorization": f"Zoho-oauthtoken {access}"}
    # Leads works with ZohoCRM.modules.ALL; /users needs ZohoCRM.users.ALL
    crm = requests.get(
        f"{api_domain}/crm/v2/Leads",
        params={"per_page": 1, "page": 1},
        headers=headers,
        timeout=60,
    )
    if not crm.ok:
        print(f"CRM API HTTP {crm.status_code}", file=sys.stderr)
        print(crm.text[:2000], file=sys.stderr)
        return 1

    try:
        payload = crm.json()
    except json.JSONDecodeError:
        print("Non-JSON CRM response:", crm.text[:500], file=sys.stderr)
        return 1

    print("Connected to Zoho CRM API.\n")
    print(json.dumps(payload, indent=2)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
