"""Shared OAuth access token refresh for Zoho CRM API scripts."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent / ".env"
TOKEN_CACHE_PATH = Path(__file__).resolve().parent / ".token_cache.json"


def load_env() -> None:
    load_dotenv(ENV_PATH)


def get_access_token_and_domain() -> tuple[str, str]:
    """
    Return (access_token, api_domain) using ZOHO_REFRESH_TOKEN in tools/zoho/.env.
    api_domain comes from the token response, else ZOHO_API_DOMAIN in .env.
    """
    load_env()
    accounts = os.environ.get("ZOHO_ACCOUNTS_URL", "https://accounts.zoho.com").rstrip("/")
    client_id = os.environ.get("ZOHO_CLIENT_ID", "").strip()
    client_secret = os.environ.get("ZOHO_CLIENT_SECRET", "").strip()
    refresh = os.environ.get("ZOHO_REFRESH_TOKEN", "").strip()
    fallback_domain = os.environ.get("ZOHO_API_DOMAIN", "").strip().rstrip("/")

    if not all([client_id, client_secret, refresh]):
        raise RuntimeError(
            "Set ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET, ZOHO_REFRESH_TOKEN in tools/zoho/.env"
        )

    cache_key = f"{accounts}|{client_id}|{refresh[:12]}"
    if os.environ.get("ZOHO_DISABLE_TOKEN_CACHE", "").lower() not in ("1", "true", "yes"):
        try:
            cached = json.loads(TOKEN_CACHE_PATH.read_text(encoding="utf-8"))
            if (
                cached.get("cache_key") == cache_key
                and cached.get("access_token")
                and cached.get("api_domain")
                and float(cached.get("expires_at", 0)) > time.time() + 120
            ):
                return str(cached["access_token"]), str(cached["api_domain"]).rstrip("/")
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass

    resp = requests.post(
        f"{accounts}/oauth/v2/token",
        data={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh,
        },
        timeout=60,
    )
    if not resp.ok:
        raise RuntimeError(f"Token refresh failed HTTP {resp.status_code}: {resp.text[:1500]}")

    try:
        data = resp.json()
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Non-JSON token response: {resp.text[:500]}") from e

    access = data.get("access_token", "").strip()
    domain = (data.get("api_domain") or fallback_domain or "").strip().rstrip("/")
    if not access:
        raise RuntimeError(f"No access_token in response: {json.dumps(data)[:500]}")
    if not domain:
        raise RuntimeError(
            "No api_domain in token response. Set ZOHO_API_DOMAIN in .env or re-run connect_zoho.py."
        )
    try:
        expires_in = int(data.get("expires_in") or 3600)
        TOKEN_CACHE_PATH.write_text(
            json.dumps(
                {
                    "cache_key": cache_key,
                    "access_token": access,
                    "api_domain": domain,
                    "expires_at": time.time() + max(300, expires_in - 60),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    except (OSError, TypeError, ValueError):
        pass
    return access, domain


def auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Zoho-oauthtoken {access_token}"}
