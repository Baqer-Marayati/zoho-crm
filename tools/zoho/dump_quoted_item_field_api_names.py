#!/usr/bin/env python3
"""Print Quoted_Items + Quotes Product_Details field API names (for Deluge / workflows)."""
from __future__ import annotations

import json
import sys

import requests

from zoho_tokens import auth_headers, get_access_token_and_domain

API_VER = "v8"


def main() -> int:
    try:
        access, dom = get_access_token_and_domain()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1
    s = requests.Session()
    s.headers.update(auth_headers(access))
    base = f"{dom.rstrip('/')}/crm/{API_VER}"
    for mod in ("Quoted_Items", "Quotes"):
        r = s.get(f"{base}/settings/fields", params={"module": mod}, timeout=60)
        if not r.ok:
            print(f"GET {mod} fields HTTP {r.status_code}", file=sys.stderr)
            continue
        fields = r.json().get("fields") or []
        out = [
            {
                "field_label": f.get("field_label"),
                "api_name": f.get("api_name"),
                "data_type": f.get("data_type"),
            }
            for f in fields
            if f.get("field_label")
        ]
        print(f"=== {mod} ({len(out)} fields) ===")
        print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
