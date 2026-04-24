#!/usr/bin/env python3
"""
Move **Machine SKU** off the Quoted_Items (quote line) layout into Unused, via Update Layout API.
Same as Zoho UI: the field still exists and can be set by Deluge; reps do not see it on the form.

  cd tools/zoho && ./venv/bin/python provision_quoted_line_hide_machine_sku_layout.py

OAuth: ZohoCRM.settings.layouts.UPDATE (or ZohoCRM.settings.ALL).

Idempotent: if Machine SKU is already not on the used section, exits 0.
"""
from __future__ import annotations

import sys

import requests

from zoho_tokens import auth_headers, get_access_token_and_domain

API_VER = "v8"
API_SKU = "Machine_SKU"


def main() -> int:
    try:
        access, dom = get_access_token_and_domain()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1
    s = requests.Session()
    s.headers.update({**auth_headers(access), "Content-Type": "application/json"})

    r0 = s.get(
        f"{dom.rstrip('/')}/crm/{API_VER}/settings/layouts",
        params={"module": "Quoted_Items"},
        timeout=60,
    )
    if not r0.ok:
        print(f"GET layouts HTTP {r0.status_code}: {r0.text[:1500]}", file=sys.stderr)
        return 1
    layouts = r0.json().get("layouts") or []
    if not layouts:
        print("No Quoted_Items layouts", file=sys.stderr)
        return 1
    lid = str(layouts[0].get("id", ""))
    if not lid:
        return 1

    r1 = s.get(
        f"{dom.rstrip('/')}/crm/{API_VER}/settings/layouts/{lid}",
        params={"module": "Quoted_Items"},
        timeout=60,
    )
    if not r1.ok:
        print(f"GET layout HTTP {r1.status_code}", file=sys.stderr)
        return 1
    L = (r1.json().get("layouts") or [None])[0] or {}
    msku_fid: str | None = None
    section_id: str | None = None
    for sec in L.get("sections") or []:
        for f in sec.get("fields") or []:
            if (f.get("api_name") or "") == API_SKU and (sec.get("type") or "") == "used":
                msku_fid = str(f.get("id", ""))
                section_id = str(sec.get("id", ""))
                break
        if msku_fid:
            break
    if not msku_fid or not section_id:
        print("Machine SKU is not on a used Quoted_Items layout section; nothing to do.")
        return 0

    body = {
        "layouts": [
            {
                "sections": [
                    {
                        "id": section_id,
                        "fields": [
                            {
                                "id": msku_fid,
                                "_delete": {"permanent": False},
                            }
                        ],
                    }
                ]
            }
        ]
    }
    r2 = s.patch(
        f"{dom.rstrip('/')}/crm/{API_VER}/settings/layouts/{lid}",
        params={"module": "Quoted_Items"},
        json=body,
        timeout=60,
    )
    if not r2.ok:
        print(f"PATCH layout HTTP {r2.status_code}: {r2.text[:2000]}", file=sys.stderr)
        return 1
    print(f"OK: Machine SKU (field id={msku_fid}) moved to Unused on layout {lid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
