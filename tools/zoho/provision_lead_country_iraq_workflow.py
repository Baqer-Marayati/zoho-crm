#!/usr/bin/env python3
"""
Enforce Leads **Address - Country / Region** (`Country`) = **Iraq** on every create and save.

Zoho v8 **blocks** PATCH on standard address subfields (default, read-only, layout) with
*Address field configuration is not supported in this version*. The reliable API approach is a
**workflow field update** (instant action) on **Leads**, trigger **Create or Edit**, **every time**
(`repeat: true`).

Caveat: reps may still *choose* another country in the form; after **Save** the workflow overwrites
the stored value to Iraq. For a greyed-out control, add a **Client Script** in the Zoho UI or use
**layout rules** if your edition allows them for that field.

  cd tools/zoho
  ./venv/bin/python provision_lead_country_iraq_workflow.py --dry-run
  ./venv/bin/python provision_lead_country_iraq_workflow.py

Requires OAuth scopes that include field-update and workflow create (e.g. `ZohoCRM.settings.ALL`).

[1] https://www.zoho.com/crm/developer/docs/api/v8/field-update-details.html
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

import requests

from zoho_tokens import auth_headers, get_access_token_and_domain

API_VER = "v8"

MODULE_API = "Leads"
COUNTRY_API = "Country"
COUNTRY_VALUE = "Iraq"
FIELD_UPDATE_NAME = "Leads set Country to Iraq"
WF_NAME = "Lead Country always Iraq"
WF_DESCRIPTION = (
    "Sets standard Address Country to Iraq on every create and edit. "
    "Complements org policy when the API cannot mark the field read-only."
)


def _crm(
    session: requests.Session, api_domain: str, method: str, path: str, **kwargs: Any
) -> requests.Response:
    url = f"{api_domain.rstrip('/')}/crm/{API_VER}{path}"
    return session.request(method, url, timeout=120, **kwargs)


def _get_token_retry() -> tuple[str, str]:
    delays = (2, 10, 45, 120, 300)
    last: Exception | None = None
    for d in delays:
        try:
            return get_access_token_and_domain()
        except RuntimeError as e:
            last = e
            if "too many requests" in str(e).lower() or "400" in str(e):
                print(f"  Token refresh rate-limited; waiting {d}s…", file=sys.stderr)
                time.sleep(d)
                continue
            raise
    assert last is not None
    raise last


def _module_meta(session: requests.Session, api_domain: str, api_name: str) -> dict[str, Any]:
    r = _crm(session, api_domain, "GET", "/settings/modules")
    r.raise_for_status()
    for m in r.json().get("modules") or []:
        if m.get("api_name") == api_name:
            return m
    raise RuntimeError(f"Module not found: {api_name}")


def _country_field(session: requests.Session, api_domain: str) -> dict[str, Any]:
    r = _crm(session, api_domain, "GET", "/settings/fields", params={"module": MODULE_API})
    r.raise_for_status()
    for f in r.json().get("fields") or []:
        if f.get("api_name") == COUNTRY_API:
            return f
    raise RuntimeError(f"Field {MODULE_API}.{COUNTRY_API} not found")


def _find_field_update_id(
    session: requests.Session, api_domain: str, name: str, module_id: str
) -> str | None:
    page = 1
    while True:
        r = _crm(
            session,
            api_domain,
            "GET",
            "/settings/automation/field_updates",
            params={"per_page": 200, "page": page, "module": MODULE_API},
        )
        if not r.ok:
            print(f"  GET field_updates HTTP {r.status_code}: {r.text[:800]}", file=sys.stderr)
            return None
        data = r.json()
        for fu in data.get("field_updates") or []:
            if (fu.get("name") or "").strip() == name:
                mod = fu.get("module") or {}
                if str(mod.get("id", "")) == str(module_id):
                    fu_id = fu.get("id")
                    if fu_id:
                        return str(fu_id)
        info = data.get("info") or {}
        if not info.get("more_records"):
            break
        page += 1
    return None


def _create_field_update(
    session: requests.Session,
    api_domain: str,
    leads: dict[str, Any],
    country: dict[str, Any],
    dry_run: bool,
) -> str | None:
    mid, fid = str(leads["id"]), str(country["id"])
    body = {
        "field_updates": [
            {
                "name": FIELD_UPDATE_NAME,
                "module": {"api_name": MODULE_API, "id": mid},
                "field": {"id": fid, "api_name": COUNTRY_API},
                "type": "static",
                "value": COUNTRY_VALUE,
                "feature_type": "workflow",
            }
        ]
    }
    if dry_run:
        print("--- dry-run POST /settings/automation/field_updates ---")
        print(json.dumps(body, indent=2))
        return "dry_run"
    r = _crm(session, api_domain, "POST", "/settings/automation/field_updates", json=body)
    if not r.ok:
        print(f"  POST field_updates HTTP {r.status_code}: {r.text[:3000]}", file=sys.stderr)
        return None
    for item in r.json().get("field_updates") or []:
        if item.get("code") == "SUCCESS":
            out = (item.get("details") or {}).get("id")
            if out:
                return str(out)
    print(json.dumps(r.json(), indent=2)[:3000], file=sys.stderr)
    return None


def _find_workflow_id(session: requests.Session, api_domain: str, name: str) -> str | None:
    filt = json.dumps(
        {"field": {"api_name": "name"}, "comparator": "contains", "value": name}
    )
    r = _crm(
        session,
        api_domain,
        "GET",
        "/settings/automation/workflow_rules",
        params={"module": MODULE_API, "filter": filt, "per_page": 200},
    )
    if not r.ok:
        return None
    for w in r.json().get("workflow_rules") or []:
        if w.get("name") == name:
            return str(w.get("id", "")) or None
    return None


def _create_workflow(
    session: requests.Session, api_domain: str, leads: dict[str, Any], field_update_id: str, dry_run: bool
) -> str | None:
    qid = str(leads["id"])
    body = {
        "workflow_rules": [
            {
                "execute_when": {
                    "type": "create_or_edit",
                    "details": {
                        "trigger_module": {"api_name": MODULE_API, "id": qid},
                        "repeat": True,
                    },
                },
                "module": {"api_name": MODULE_API, "id": qid},
                "name": WF_NAME,
                "description": WF_DESCRIPTION,
                "status": {"active": True},
                "conditions": [
                    {
                        "sequence_number": 1,
                        "instant_actions": {
                            "actions": [
                                {
                                    "type": "field_updates",
                                    "id": field_update_id,
                                    "name": FIELD_UPDATE_NAME,
                                }
                            ]
                        },
                    }
                ],
            }
        ]
    }
    if dry_run:
        print("--- dry-run POST /settings/automation/workflow_rules ---")
        print(json.dumps(body, indent=2)[:8000])
        return "dry_run"
    r = _crm(session, api_domain, "POST", "/settings/automation/workflow_rules", json=body)
    if not r.ok:
        print(f"  POST workflow_rules HTTP {r.status_code}: {r.text[:5000]}", file=sys.stderr)
        return None
    for wr in r.json().get("workflow_rules") or []:
        if wr.get("code") == "SUCCESS":
            did = (wr.get("details") or {}).get("id")
            if did:
                return str(did)
    print(json.dumps(r.json(), indent=2)[:4000], file=sys.stderr)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="Print payloads only; no POST.")
    args = ap.parse_args()

    try:
        access, api_domain = _get_token_retry()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1

    session = requests.Session()
    session.headers.update(auth_headers(access))
    session.headers["Content-Type"] = "application/json"

    try:
        leads = _module_meta(session, api_domain, MODULE_API)
        country = _country_field(session, api_domain)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1

    print(f"  Module: {MODULE_API} (id={leads['id']})")
    print(f"  Field:  {COUNTRY_API} (id={country['id']})  value={COUNTRY_VALUE!r}")

    mid = str(leads["id"])
    fuid = _find_field_update_id(session, api_domain, FIELD_UPDATE_NAME, mid)
    if fuid:
        print(f"  Field update already exists: id={fuid}")
    else:
        out = _create_field_update(session, api_domain, leads, country, args.dry_run)
        if args.dry_run:
            fuid = "<new_field_update_id>"
        else:
            if not out or out == "dry_run":
                return 1
            fuid = out
            print(f"  Created field update id: {fuid}")

    wfid = _find_workflow_id(session, api_domain, WF_NAME)
    if wfid:
        print(f"  Workflow already exists: id={wfid}")
        if args.dry_run:
            return 0
        return 0

    wf = _create_workflow(session, api_domain, leads, fuid, args.dry_run)
    if not wf and not args.dry_run:
        return 1
    if wf and wf != "dry_run":
        print(f"  Created workflow id: {wf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
