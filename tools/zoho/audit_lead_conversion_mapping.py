#!/usr/bin/env python3
"""
Read-only audit: lead conversion targets as exposed by Zoho CRM v8 metadata.

- GET /settings/layouts?module=Leads → convert_mapping (Deal layout + fields on convert form)
- GET /settings/fields?module=Leads → per-field convert_mapping.{Deals,Accounts,Contacts}

This does not change org data. Run from tools/zoho with .env configured.

Usage:
  ./venv/bin/python audit_lead_conversion_mapping.py
"""
from __future__ import annotations

import json
import sys

import requests

from zoho_tokens import auth_headers, get_access_token_and_domain

API_VER = "v8"


def main() -> int:
    access, api_domain = get_access_token_and_domain()
    base = f"{api_domain.rstrip('/')}/crm/{API_VER}"
    s = requests.Session()
    s.headers.update(auth_headers(access))

    r = s.get(f"{base}/settings/layouts", params={"module": "Leads"}, timeout=120)
    if not r.ok:
        print(f"GET layouts Leads HTTP {r.status_code}: {r.text[:2000]}", file=sys.stderr)
        return 1

    layouts = r.json().get("layouts") or []
    print("=== Lead layouts — convert_mapping (Deal layout + convert form fields) ===\n")
    for L in layouts:
        cm = L.get("convert_mapping") or {}
        deals = cm.get("Deals") or {}
        fields = deals.get("fields") or []
        apis = [f.get("api_name") for f in fields]
        print(f"Layout: {L.get('display_label') or L.get('name')} (id={L.get('id')})")
        print(f"  Accounts layout: {(cm.get('Accounts') or {}).get('id')}")
        print(f"  Contacts layout: {(cm.get('Contacts') or {}).get('id')}")
        print(f"  Deals layout:    {deals.get('id')} ({deals.get('display_label')})")
        print(f"  Fields on convert UI: {', '.join(apis)}")
        print()

    r2 = s.get(f"{base}/settings/fields", params={"module": "Leads"}, timeout=120)
    if not r2.ok:
        print(f"GET fields Leads HTTP {r2.status_code}: {r2.text[:2000]}", file=sys.stderr)
        return 1

    rows: list[tuple[str, str, str]] = []
    for f in r2.json().get("fields") or []:
        cm = f.get("convert_mapping") or {}
        tgt = cm.get("Deals")
        if tgt:
            rows.append((f.get("api_name", "?"), f.get("field_label", "?"), tgt))

    rows.sort(key=lambda x: x[0])
    print("=== Lead fields with Deals target (field-level convert_mapping) ===\n")
    for api_name, label, tgt in rows:
        print(f"  {api_name:30}  →  Deals.{tgt}  ({label})")

    if not any(r[2] == "Line_of_business" for r in rows):
        print(
            "\n⚠ No Lead field maps to Deals.Line_of_business — "
            "set mapping in Setup or via Fields API.",
            file=sys.stderr,
        )
        return 2

    if not any(r[2] == "Deal_Name" for r in rows):
        print(
            "\nNote: No Lead field maps to Deals.Deal_Name — "
            "Potential Name is usually entered on the convert screen (or map Company via UI).",
        )

    print("\nOK: Line of business copy-on-convert is configured in field metadata.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
