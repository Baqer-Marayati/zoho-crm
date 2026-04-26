#!/usr/bin/env python3
"""
Remove Iraq custom address fields from Leads and the Province -> City (Iraq) map dependency.

Discovers fields by api_name: Country_Iraq, Province, City_Iraq (idempotent: skips if missing).

  cd tools/zoho && ./venv/bin/python delete_lead_address_iraq_fields.py

OAuth: ZohoCRM.settings.map_dependency.DELETE, ZohoCRM.settings.fields.DELETE
       (or ZohoCRM.settings.ALL)
"""
from __future__ import annotations

import json
import sys
import time

import requests

from zoho_tokens import auth_headers, get_access_token_and_domain

API_VER = "v8"
MODULE = "Leads"
APIS = ("Country_Iraq", "Province", "City_Iraq")
STANDARD_LEADS_LAYOUT_NAME = "Standard"


def _crm(s: requests.Session, dom: str, method: str, path: str, **kwargs):
    return s.request(
        method, f"{dom.rstrip('/')}/crm/{API_VER}{path}", timeout=120, **kwargs
    )


def _layout_id(s: requests.Session, dom: str) -> str:
    r = _crm(s, dom, "GET", "/settings/layouts", params={"module": MODULE})
    r.raise_for_status()
    for lo in r.json().get("layouts") or []:
        if lo.get("name") == STANDARD_LEADS_LAYOUT_NAME and lo.get("status") == "active":
            return str(lo["id"])
    return str((r.json().get("layouts") or [{}])[0].get("id", ""))


def main() -> int:
    for i in range(5):
        try:
            t, d = get_access_token_and_domain()
            break
        except RuntimeError as e:
            if "too many" not in str(e).lower() or i == 4:
                raise
            time.sleep(45 * (i + 1))
    s = requests.Session()
    s.headers.update(auth_headers(t))

    lid = _layout_id(s, d)
    r = _crm(
        s,
        d,
        "GET",
        f"/settings/layouts/{lid}/map_dependency",
        params={"module": MODULE},
    )
    if r.ok and (r.text or "").strip():
        for md in r.json().get("map_dependency") or []:
            p = (md.get("parent") or {}).get("api_name")
            c = (md.get("child") or {}).get("api_name")
            did = md.get("id")
            if p == "Province" and c == "City_Iraq" and did:
                rd = s.delete(
                    f"{d.rstrip('/')}/crm/{API_VER}/settings/layouts/{lid}/map_dependency/{did}",
                    params={"module": MODULE},
                    timeout=120,
                )
                print("map_dependency", did, rd.status_code, rd.text[:200])

    r2 = s.get(
        f"{d.rstrip('/')}/crm/{API_VER}/settings/fields", params={"module": MODULE}, timeout=120
    )
    r2.raise_for_status()
    by_api: dict[str, str] = {}
    for f in r2.json().get("fields") or []:
        an = f.get("api_name")
        if an in APIS and f.get("id"):
            by_api[str(an)] = str(f["id"])

    s.headers["Content-Type"] = "application/json"
    for an in ("City_Iraq", "Province", "Country_Iraq"):
        fid = by_api.get(an)
        if not fid:
            print(f"skip (not found): {an}")
            continue
        r3 = s.delete(
            f"{d.rstrip('/')}/crm/{API_VER}/settings/fields/{fid}",
            params={"module": MODULE},
            timeout=120,
        )
        print("DELETE", an, r3.status_code, (r3.text or "")[:300])
        if not r3.ok:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
