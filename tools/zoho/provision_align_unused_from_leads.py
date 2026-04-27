#!/usr/bin/env python3
"""
Move the same *standard* fields to Unused on Accounts, Contacts, and Deals Standard layouts
as are already Unused on Leads (GET /settings/fields?module=Leads&type=unused, custom_field=false).

Leads-only fields (e.g. Lead_Status) are skipped on other modules. No_of_Employees on Leads maps
to Employees on Accounts.

  cd tools/zoho && ./venv/bin/python provision_align_unused_from_leads.py
  ./venv/bin/python provision_align_unused_from_leads.py --dry-run
  ./venv/bin/python provision_align_unused_from_leads.py --verify

OAuth: ZohoCRM.settings.layouts.UPDATE (or ZohoCRM.settings.ALL)
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
LEADS_MODULE = "Leads"
TARGET_MODULES: tuple[str, ...] = ("Accounts", "Contacts", "Deals")

# Leads uses No_of_Employees; Accounts uses Employees for the same idea.
LEADS_TO_ACCOUNTS_NAME: dict[str, str] = {"No_of_Employees": "Employees"}


def _crm(session: requests.Session, api_domain: str, method: str, path: str, **kwargs):
    return session.request(
        method,
        f"{api_domain.rstrip('/')}/crm/{API_VER}{path}",
        timeout=120,
        **kwargs,
    )


def _token_with_retries(attempts: int = 5) -> tuple[str, str]:
    err: Exception | None = None
    for n in range(attempts):
        try:
            return get_access_token_and_domain()
        except RuntimeError as e:
            err = e
            if "too many requests" in str(e).lower() or "400" in str(e):
                time.sleep(min(30.0 * (2**n), 300.0))
            else:
                raise
    assert err
    raise err


def _standard_layout_id(
    session: requests.Session, api_domain: str, module: str
) -> str:
    r = _crm(session, api_domain, "GET", "/settings/layouts", params={"module": module})
    r.raise_for_status()
    for lo in r.json().get("layouts") or []:
        if lo.get("name") == "Standard" and lo.get("status") == "active":
            return str(lo["id"])
    layouts = r.json().get("layouts") or []
    if not layouts:
        raise RuntimeError(f"No layouts returned for {module}.")
    return str(layouts[0]["id"])


def _get_layout(
    session: requests.Session, api_domain: str, layout_id: str, module: str
) -> dict[str, Any]:
    r = _crm(
        session,
        api_domain,
        "GET",
        f"/settings/layouts/{layout_id}",
        params={"module": module},
    )
    r.raise_for_status()
    layouts = r.json().get("layouts") or []
    if not layouts:
        raise RuntimeError("Empty layout response.")
    return layouts[0]


def _all_module_api_names(
    session: requests.Session, api_domain: str, module: str
) -> set[str]:
    r = _crm(
        session, api_domain, "GET", "/settings/fields", params={"module": module, "type": "all"}
    )
    r.raise_for_status()
    return {f.get("api_name") for f in (r.json().get("fields") or []) if f.get("api_name")}


def _leads_unused_standard_api_names(
    session: requests.Session, api_domain: str
) -> set[str]:
    r = _crm(
        session,
        api_domain,
        "GET",
        "/settings/fields",
        params={"module": LEADS_MODULE, "type": "unused"},
    )
    r.raise_for_status()
    return {
        str(f["api_name"])
        for f in (r.json().get("fields") or [])
        if f.get("api_name") and not f.get("custom_field")
    }


def _field_placements(
    layout: dict[str, Any], targets: frozenset[str]
) -> dict[str, str]:
    """api_name -> field_id for targets that sit on a used section (not Unused)."""
    in_section: dict[str, str] = {}
    for sec in layout.get("sections") or []:
        name = (sec.get("name") or sec.get("display_label") or "").strip().lower()
        if "unassign" in name or "unused" in name:
            continue
        for f in sec.get("fields") or []:
            an = f.get("api_name")
            if an in targets and f.get("id"):
                in_section[str(an)] = str(f["id"])
    return in_section


def _find_section_id_for_field_ids(
    layout: dict[str, Any], field_ids: set[str]
) -> str | None:
    for sec in layout.get("sections") or []:
        name = (sec.get("name") or sec.get("display_label") or "").strip().lower()
        if "unassign" in name or "unused" in name:
            continue
        for f in sec.get("fields") or []:
            if str(f.get("id")) in field_ids and sec.get("id"):
                return str(sec["id"])
    return None


def _hide_one(
    session: requests.Session,
    api_domain: str,
    module: str,
    layout_id: str,
    section_id: str,
    field_id: str,
    dry_run: bool,
) -> bool:
    body = {
        "layouts": [
            {
                "sections": [
                    {
                        "id": section_id,
                        "fields": [
                            {
                                "id": field_id,
                                "_delete": {"permanent": False},
                            }
                        ],
                    }
                ]
            }
        ]
    }
    if dry_run:
        print("  DRY-RUN hide field_id:", field_id)
        return True
    r = _crm(
        session,
        api_domain,
        "PATCH",
        f"/settings/layouts/{layout_id}",
        params={"module": module},
        data=json.dumps(body),
        headers={**session.headers, "Content-Type": "application/json"},
    )
    if not r.ok:
        print(
            f"  PATCH field {field_id} failed HTTP {r.status_code}: {r.text[:2000]}",
            file=sys.stderr,
        )
        return False
    try:
        j = r.json()
        for row in j.get("layouts", []):
            if row.get("status") == "error":
                print(json.dumps(j, indent=2)[:2000], file=sys.stderr)
                return False
        print("  OK", field_id, j.get("layouts", [{}])[0].get("message", ""))
    except json.JSONDecodeError:
        print(r.text[:2000])
    return True


def _target_apis_for_module(
    lead_unused: set[str], module_apis: set[str], module: str
) -> frozenset[str]:
    t: set[str] = set()
    for an in lead_unused:
        if an in module_apis:
            t.add(an)
    if module == "Accounts":
        for a, b in LEADS_TO_ACCOUNTS_NAME.items():
            if a in lead_unused and b in module_apis:
                t.add(b)
    return frozenset(t)


def _process_module(
    s: requests.Session,
    api_domain: str,
    module: str,
    targets: frozenset[str],
    dry_run: bool,
    verify: bool,
    sleep_s: float,
) -> int:
    if not targets:
        print(f"\n=== {module} — no matching fields in module; skip. ===\n")
        return 0

    layout_id = _standard_layout_id(s, api_domain, module)
    print(f"\n=== {module} Standard layout_id={layout_id} ===")
    print(f"  Target api_names ({len(targets)}): {sorted(targets)}")

    layout = _get_layout(s, api_domain, layout_id, module)
    placements = _field_placements(layout, targets)
    on_layout = set(placements.keys())
    not_on = sorted(targets - on_layout)
    if not_on:
        print(f"  Already unused / not on layout: {not_on}")
    if not placements:
        print("  Nothing to hide on main section(s).")
        return 0

    ordered = sorted(placements, key=str.lower)
    if verify or dry_run:
        print("  To hide (on a section):", ordered)
        print("  field_ids:", [placements[k] for k in ordered])
    if verify:
        return 0

    fail: list[str] = []
    for n, api in enumerate(ordered, 1):
        print(f"\n  [{module} {n}/{len(ordered)}] {api}")
        time.sleep(sleep_s)
        r_lo = _crm(
            s, api_domain, "GET", f"/settings/layouts/{layout_id}", params={"module": module}
        )
        if r_lo.status_code == 401:
            # refresh token: caller must reauth — duplicate lead script pattern
            access, api_domain = _token_with_retries()
            s = requests.Session()
            s.headers.update(auth_headers(access))
            s.headers["Content-Type"] = "application/json"
            r_lo = _crm(
                s, api_domain, "GET", f"/settings/layouts/{layout_id}", params={"module": module}
            )
        if not r_lo.ok:
            print(f"  GET layout HTTP {r_lo.status_code}", file=sys.stderr)
            fail.append(api)
            continue
        layout2 = (r_lo.json().get("layouts") or [None])[0] or {}
        pl2 = _field_placements(layout2, targets)
        if api not in pl2:
            print("  (already Unused / not on layout; skip)")
            continue
        sid = _find_section_id_for_field_ids(layout2, {pl2[api]})
        if not sid:
            print("  (section not found; skip)", file=sys.stderr)
            fail.append(api)
            continue
        if not _hide_one(s, api_domain, module, layout_id, sid, pl2[api], dry_run):
            fail.append(api)

    if not dry_run and fail:
        print(f"\n  {module} failures: {fail}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Align Accounts/Contacts/Deals Standard layouts to Leads Unused standard fields."
    )
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true", help="List targets only; no PATCH.")
    ap.add_argument("--sleep", type=float, default=3.0, help="Seconds between PATCH calls.")
    args = ap.parse_args()

    time.sleep(min(args.sleep, 3.0))
    access, api_domain = _token_with_retries()
    s = requests.Session()
    s.headers.update(auth_headers(access))
    s.headers["Content-Type"] = "application/json"

    try:
        lead_unused = _leads_unused_standard_api_names(s, api_domain)
    except Exception as e:
        print(f"Error reading Leads unused fields: {e}", file=sys.stderr)
        return 1

    print(f"Leads unused (standard) api_names: {len(lead_unused)}")
    print(" ", sorted(lead_unused))

    module_apis: dict[str, set[str]] = {}
    for m in TARGET_MODULES:
        try:
            module_apis[m] = _all_module_api_names(s, api_domain, m)
        except Exception as e:
            print(f"Error listing fields for {m}: {e}", file=sys.stderr)
            return 1

    rc = 0
    for m in TARGET_MODULES:
        targets = _target_apis_for_module(lead_unused, module_apis[m], m)
        r = _process_module(
            s, api_domain, m, targets, args.dry_run, args.verify, args.sleep
        )
        if r != 0:
            rc = r

    if not args.verify and not args.dry_run and rc == 0:
        print(
            "\nDone. Hid standard fields on Standard layouts to match Leads Unused (where the field exists in each module)."
        )
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
