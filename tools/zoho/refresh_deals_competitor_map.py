#!/usr/bin/env python3
"""
Re-apply Stage → Competitor map dependency from current picklist options.

Run after adding competitor values in Zoho (or editing competitors_template.csv + provision_phase2_fields.py)
so **Closed Lost** exposes every non–**-None-** value. Open stages only show -None- (per provision_phase2_layouts).

  cd tools/zoho && ./venv/bin/python refresh_deals_competitor_map.py
  ./venv/bin/python refresh_deals_competitor_map.py --dry-run

OAuth: ZohoCRM.settings.map_dependency.UPDATE (or settings.ALL)
"""
from __future__ import annotations

import argparse
import sys

import requests

from zoho_tokens import auth_headers, get_access_token_and_domain

import provision_phase2_layouts as p


def _load_all_deal_fields(session, api_domain: str) -> dict[str, dict]:
    by_api: dict[str, dict] = {}
    page = 1
    while True:
        r = p._crm(
            session,
            api_domain,
            "GET",
            "/settings/fields",
            params={"module": p.DEALS_MODULE, "per_page": 200, "page": page},
        )
        r.raise_for_status()
        j = r.json()
        for f in j.get("fields") or []:
            api = f.get("api_name")
            if api:
                by_api[str(api)] = f
        if not (j.get("info") or {}).get("more_records"):
            break
        page += 1
    return by_api


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    access, api_domain = get_access_token_and_domain()
    session = requests.Session()
    session.headers.update(auth_headers(access))
    session.headers["Content-Type"] = "application/json"

    r_layouts = p._crm(session, api_domain, "GET", "/settings/layouts", params={"module": p.DEALS_MODULE})
    r_layouts.raise_for_status()
    layout_id = p._pick_standard_layout_id(r_layouts.json())
    by_api = _load_all_deal_fields(session, api_domain)
    if p.STAGE_API not in by_api or p.COMP_API not in by_api:
        print("Deals must have Stage and Competitor fields.", file=sys.stderr)
        return 1
    body = p._build_map_dependency_body(by_api[p.STAGE_API], by_api[p.COMP_API])
    print(f"Deals layout_id={layout_id}  PUT Stage → Competitor")
    if not p._sync_map_dependency(session, api_domain, layout_id, body, args.dry_run):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
