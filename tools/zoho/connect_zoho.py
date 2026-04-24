#!/usr/bin/env python3
"""
Interactive Zoho CRM OAuth setup — run in Terminal, not in Cursor chat.

  cd tools/zoho
  ./venv/bin/python connect_zoho.py

You will be asked for Client ID, Client Secret, and grant code. Those answers stay
on your computer only (written to .env). Do not paste them into AI chat.
"""
from __future__ import annotations

import getpass
import json
import os
import sys
from pathlib import Path

import requests

ENV_PATH = Path(__file__).resolve().parent / ".env"

DEFAULT_ACCOUNTS = "https://accounts.zoho.com"
REDIRECT_TRIES = ("https://localhost", "http://localhost")


def _write_env(data: dict[str, str]) -> None:
    lines = [f"{k}={v}" for k, v in data.items() if v is not None and v != ""]
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        ENV_PATH.chmod(0o600)
    except OSError:
        pass


def _exchange(
    accounts: str,
    client_id: str,
    client_secret: str,
    code: str,
) -> tuple[bool, dict | str]:
    accounts = accounts.rstrip("/")
    url = f"{accounts}/oauth/v2/token"
    last_text = ""
    for redirect_uri in REDIRECT_TRIES:
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
        last_text = resp.text
        if not resp.ok:
            continue
        try:
            return True, resp.json()
        except json.JSONDecodeError:
            return False, resp.text[:2000]
    return False, last_text[:2000]


def _ping(
    accounts: str,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    api_domain: str | None,
) -> tuple[bool, str]:
    accounts = accounts.rstrip("/")
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
        return False, f"Refresh failed: HTTP {tok.status_code}\n{tok.text[:1500]}"
    try:
        tdata = tok.json()
    except json.JSONDecodeError:
        return False, tok.text[:1500]
    access = tdata.get("access_token")
    domain = (tdata.get("api_domain") or api_domain or "").rstrip("/")
    if not access or not domain:
        return False, json.dumps(tdata)[:1500]
    # Leads: works with ZohoCRM.modules.ALL. /users needs ZohoCRM.users.ALL.
    crm = requests.get(
        f"{domain}/crm/v2/Leads",
        params={"per_page": 1, "page": 1},
        headers={"Authorization": f"Zoho-oauthtoken {access}"},
        timeout=60,
    )
    if not crm.ok:
        return False, f"CRM HTTP {crm.status_code}\n{crm.text[:1500]}"
    try:
        body = crm.json()
    except json.JSONDecodeError:
        return False, crm.text[:1500]
    return True, json.dumps(body, indent=2)[:4000]


def main() -> int:
    print(
        "\n=== Zoho CRM — interactive connect ===\n"
        "Type answers here in Terminal only. Do NOT paste secrets into Cursor chat.\n"
    )

    if not ENV_PATH.parent.exists():
        print("Unexpected: tools/zoho folder missing.", file=sys.stderr)
        return 1

    print(
        f"Zoho Accounts URL — press Enter for default.\n"
        f"  Default: {DEFAULT_ACCOUNTS}\n"
        f"  (EU: https://accounts.zoho.eu  IN: https://accounts.zoho.in)\n"
    )
    accounts = input(f"Accounts URL [{DEFAULT_ACCOUNTS}]: ").strip() or DEFAULT_ACCOUNTS

    client_id = input("Client ID (from API Console → Self Client → Client Secret tab): ").strip()
    if not client_id:
        print("Client ID is required.", file=sys.stderr)
        return 1

    print("Client Secret (input hidden):")
    client_secret = getpass.getpass("Client Secret: ").strip()
    if not client_secret:
        print("Client Secret is required.", file=sys.stderr)
        return 1

    print(
        "\nGrant code — from API Console → Self Client → Generate Code.\n"
        "It expires quickly; generate a new one if this fails.\n"
        "\n**Scopes (paste into Generate Code) for most repo automation + API discovery:\n"
        "  ZohoCRM.modules.ALL,ZohoCRM.settings.ALL,ZohoCRM.users.ALL,ZohoCRM.apis.READ\n"
        "After setup, run: ./venv/bin/python zoho_doctor.py  (or: make zoho-doctor)\n"
    )
    grant = input("Grant code: ").strip()
    if not grant:
        print("Grant code is required.", file=sys.stderr)
        return 1

    # Temporary .env so exchange_grant.py could be used too; we keep grant only until success
    _write_env(
        {
            "ZOHO_ACCOUNTS_URL": accounts,
            "ZOHO_CLIENT_ID": client_id,
            "ZOHO_CLIENT_SECRET": client_secret,
            "ZOHO_GRANT_CODE": grant,
            "ZOHO_REDIRECT_URI": REDIRECT_TRIES[0],
        }
    )
    print(f"\nWrote {ENV_PATH} (mode 600). Exchanging grant for refresh token…\n")

    ok, payload = _exchange(accounts, client_id, client_secret, grant)
    if not ok:
        print("Exchange failed. Zoho said:\n", file=sys.stderr)
        print(payload if isinstance(payload, str) else json.dumps(payload), file=sys.stderr)
        print(
            "\nTry: new grant code from Zoho, correct Accounts URL for your region, "
            "and scopes that include CRM.",
            file=sys.stderr,
        )
        return 1

    if not isinstance(payload, dict):
        print("Unexpected response.", file=sys.stderr)
        return 1

    refresh = payload.get("refresh_token", "").strip()
    api_domain = (payload.get("api_domain") or "").strip().rstrip("/")
    if not refresh:
        print("No refresh_token in response:", json.dumps(payload)[:800], file=sys.stderr)
        return 1

    _write_env(
        {
            "ZOHO_ACCOUNTS_URL": accounts,
            "ZOHO_CLIENT_ID": client_id,
            "ZOHO_CLIENT_SECRET": client_secret,
            "ZOHO_REFRESH_TOKEN": refresh,
            "ZOHO_API_DOMAIN": api_domain,
            "ZOHO_REDIRECT_URI": REDIRECT_TRIES[0],
        }
    )

    print("Saved refresh token and API domain to .env (grant code removed).\n")
    print("Testing CRM API (current user)…\n")

    pok, pmsg = _ping(accounts, client_id, client_secret, refresh, api_domain or None)
    if not pok:
        print("Ping failed:", file=sys.stderr)
        print(pmsg, file=sys.stderr)
        return 1

    print("Success — Zoho CRM API responded:\n")
    print(pmsg)
    print("\nDone. You can run ./venv/bin/python zoho_ping.py anytime to verify.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
