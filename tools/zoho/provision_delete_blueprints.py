#!/usr/bin/env python3
"""
List and delete all Zoho CRM Blueprint definitions (v8).

  GET  /crm/v8/settings/blueprints
  DELETE /crm/v8/settings/blueprints/{id}?module={ModuleAPIName}

OAuth: ZohoCRM.settings.ALL (or settings scopes that include blueprints)

  cd tools/zoho && ./venv/bin/python provision_delete_blueprints.py
  ./venv/bin/python provision_delete_blueprints.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys

import requests

from zoho_tokens import auth_headers, get_access_token_and_domain

API_VER = "v8"


def _crm(session: requests.Session, domain: str, method: str, path: str, **kwargs):
    return session.request(
        method, f"{domain.rstrip('/')}/crm/{API_VER}{path}", timeout=120, **kwargs
    )


def main() -> int:
    p = argparse.ArgumentParser(description="Delete all Blueprints in the org")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    access, dom = get_access_token_and_domain()
    s = requests.Session()
    s.headers.update(auth_headers(access))

    r = _crm(s, dom, "GET", "/settings/blueprints")
    if r.status_code == 204 or not (r.text or "").strip():
        print("No blueprints (empty).")
        return 0
    if not r.ok:
        print(f"GET blueprints HTTP {r.status_code}: {r.text[:2000]}", file=sys.stderr)
        return 1
    bps = r.json().get("blueprints") or []
    for bp in bps:
        bid = str(bp.get("id"))
        mod = (bp.get("module") or {}).get("api_name", "Leads")
        name = bp.get("name", "?")
        if args.dry_run:
            print(f"DRY-RUN DELETE blueprint id={bid} name={name!r} module={mod}")
            continue
        d = _crm(
            s,
            dom,
            "DELETE",
            f"/settings/blueprints/{bid}",
            params={"module": mod},
        )
        print(
            f"DELETE {name!r} ({bid}) module={mod} HTTP {d.status_code}",
            d.text[:500] if d.text else "",
        )
        if not d.ok:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
