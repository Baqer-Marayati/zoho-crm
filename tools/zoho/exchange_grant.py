#!/usr/bin/env python3
"""
One-time: exchange a Zoho Self Client grant code for access + refresh tokens.

Put ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET, and ZOHO_GRANT_CODE in .env (this folder),
then run: ./venv/bin/python exchange_grant.py

On success, add ZOHO_REFRESH_TOKEN (and optional ZOHO_API_DOMAIN) to .env and
delete ZOHO_GRANT_CODE. Never commit .env or paste secrets into chat.
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
    code = os.environ.get("ZOHO_GRANT_CODE", "").strip()

    if not all([client_id, client_secret, code]):
        print(
            "Missing values. In tools/zoho/.env set:\n"
            "  ZOHO_CLIENT_ID\n"
            "  ZOHO_CLIENT_SECRET\n"
            "  ZOHO_GRANT_CODE\n"
            f"(Loaded from: {ENV_PATH})",
            file=sys.stderr,
        )
        return 1

    configured_redirect = os.environ.get("ZOHO_REDIRECT_URI", "").strip()
    redirect_candidates = []
    for r in (configured_redirect, "https://localhost", "http://localhost"):
        if r and r not in redirect_candidates:
            redirect_candidates.append(r)

    url = f"{accounts}/oauth/v2/token"
    last_body = None
    last_status = None

    for redirect_uri in redirect_candidates:
        resp = requests.post(
            url,
            data={
                "grant_type": "authorization_code",
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
            timeout=60,
        )
        last_status, last_body = resp.status_code, resp.text
        if not resp.ok:
            continue
        try:
            data = resp.json()
        except json.JSONDecodeError:
            print("Unexpected non-JSON response:", resp.text[:500], file=sys.stderr)
            return 1

        refresh = data.get("refresh_token")
        api_domain = data.get("api_domain")
        print("Token exchange succeeded.\n")
        if api_domain:
            print(f"ZOHO_API_DOMAIN={api_domain}")
        if refresh:
            print(f"ZOHO_REFRESH_TOKEN={refresh}")
        print(
            "\nNext: copy the two lines above into tools/zoho/.env, remove ZOHO_GRANT_CODE, "
            "then run: ./venv/bin/python zoho_ping.py"
        )
        return 0

    print(f"Token exchange failed (HTTP {last_status}).", file=sys.stderr)
    print(last_body[:2000], file=sys.stderr)
    print(
        "\nIf you see invalid_redirect_uri, set ZOHO_REDIRECT_URI in .env to the exact "
        "value Zoho shows for Self Client, or generate a new grant code and retry.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
