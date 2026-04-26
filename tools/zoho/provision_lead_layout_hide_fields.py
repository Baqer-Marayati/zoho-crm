#!/usr/bin/env python3
"""
Move selected Leads (Standard) layout fields to Unused — hides them on Create/Edit Lead forms.
Field definitions and existing data are unchanged; this is the supported v8 API behavior.

  cd tools/zoho && ./venv/bin/python provision_lead_layout_hide_fields.py
  ./venv/bin/python provision_lead_layout_hide_fields.py --dry-run
  ./venv/bin/python provision_lead_layout_hide_fields.py --verify  # only read layout, no writes

OAuth: ZohoCRM.settings.layouts.UPDATE (or ZohoCRM.settings.ALL)

If Zoho returns ALREADY_USED (Blueprint), that field is referenced in a Leads Blueprint and must
be removed from the Blueprint in Setup before this script can move it to Unused.
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
MODULE = "Leads"

# User-requested: hide from Standard lead form (by api_name; discovered on layout)
TARGET_API_NAMES: frozenset[str] = frozenset(
    {
        "Mobile",
        "Annual_Revenue",
        "Email_Opt_Out",
        "Fax",
        "Lead_Status",
        "No_of_Employees",
        "Rating",
        "Skype_ID",
        "Secondary_Email",
        "Twitter",
    }
)


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
                wait = 30.0 * (2**n)  # 30, 60, 120, 240, 480
                time.sleep(min(wait, 300.0))
            else:
                raise
    assert err
    raise err


def _standard_layout_id(session: requests.Session, api_domain: str) -> str:
    r = _crm(session, api_domain, "GET", "/settings/layouts", params={"module": MODULE})
    r.raise_for_status()
    for lo in r.json().get("layouts") or []:
        if lo.get("name") == "Standard" and lo.get("status") == "active":
            return str(lo["id"])
    layouts = r.json().get("layouts") or []
    if not layouts:
        raise RuntimeError("No Leads layouts returned.")
    return str(layouts[0]["id"])


def _get_layout(
    session: requests.Session, api_domain: str, layout_id: str
) -> dict[str, Any]:
    r = _crm(
        session,
        api_domain,
        "GET",
        f"/settings/layouts/{layout_id}",
        params={"module": MODULE},
    )
    r.raise_for_status()
    layouts = r.json().get("layouts") or []
    if not layouts:
        raise RuntimeError("Empty layout response.")
    return layouts[0]


def _field_placements(
    layout: dict[str, Any],
) -> tuple[dict[str, str], str | None]:
    """
    Return (api_name -> field_id) for target fields on any *used* section (not Unassigned).
    """
    in_section: dict[str, str] = {}
    for sec in layout.get("sections") or []:
        name = (sec.get("name") or sec.get("display_label") or "").strip().lower()
        if "unassign" in name or "unused" in name:
            continue
        for f in sec.get("fields") or []:
            an = f.get("api_name")
            if an in TARGET_API_NAMES and f.get("id"):
                in_section[str(an)] = str(f["id"])
    return in_section, None


def _hide_one(
    session: requests.Session,
    api_domain: str,
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
        print("DRY-RUN would hide field_id:", field_id)
        return True
    r = _crm(
        session,
        api_domain,
        "PATCH",
        f"/settings/layouts/{layout_id}",
        params={"module": MODULE},
        data=json.dumps(body),
        headers={**session.headers, "Content-Type": "application/json"},
    )
    if not r.ok:
        print(
            f"PATCH field {field_id} failed HTTP {r.status_code}: {r.text[:2000]}",
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


def main() -> int:
    ap = argparse.ArgumentParser(description="Hide Leads layout fields (move to Unused) via v8 API.")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true", help="List placement only; do not PATCH.")
    ap.add_argument(
        "--sleep",
        type=float,
        default=3.0,
        help="Seconds to sleep before token refresh and between PATCH calls (default 3).",
    )
    args = ap.parse_args()

    time.sleep(args.sleep)  # reduce hitting rate limits after previous sessions
    access, api_domain = _token_with_retries()
    s = requests.Session()
    s.headers.update(auth_headers(access))
    s.headers["Content-Type"] = "application/json"

    try:
        layout_id = _standard_layout_id(s, api_domain)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    print(f"Leads Standard layout_id={layout_id} ({api_domain})")

    layout = _get_layout(s, api_domain, layout_id)
    placements, _ = _field_placements(layout)
    missing = sorted(TARGET_API_NAMES - set(placements))
    if missing:
        print(
            f"Not on a regular section (already Unused or not on this layout): {missing}"
        )
    if not placements:
        print("Nothing to hide — all target fields are already off the main section(s).")
        return 0

    ordered = sorted(placements, key=str.lower)
    to_hide_ids = [placements[k] for k in ordered]
    all_ids = set(to_hide_ids)
    # All targets should be in the same "Lead Information" section in a typical org; verify one section
    section_id = _find_section_id_for_field_ids(layout, all_ids)
    if not section_id:
        print("Could not resolve section_id for fields.", file=sys.stderr)
        return 1

    if args.verify or args.dry_run:
        print("Fields to hide (order):", ordered)
        print("Field ids:", to_hide_ids)
        print("section_id:", section_id)
        if args.verify:
            return 0

    def _reauth() -> None:
        nonlocal s, access, api_domain
        access, api_domain = _token_with_retries()
        s = requests.Session()
        s.headers.update(auth_headers(access))
        s.headers["Content-Type"] = "application/json"

    # Reuse the same access token for all calls (avoids rate-limiting the token refresh API).
    fail_api: list[str] = []
    for n, api in enumerate(ordered, 1):
        print(f"\n[{n}/{len(ordered)}] {api}")
        time.sleep(args.sleep)
        r_lo = _crm(
            s, api_domain, "GET", f"/settings/layouts/{layout_id}", params={"module": MODULE}
        )
        if r_lo.status_code == 401:
            _reauth()
            r_lo = _crm(
                s, api_domain, "GET", f"/settings/layouts/{layout_id}", params={"module": MODULE}
            )
        if not r_lo.ok:
            print(f"GET layout HTTP {r_lo.status_code}", file=sys.stderr)
            fail_api.append(api)
            continue
        layout = (r_lo.json().get("layouts") or [None])[0] or {}
        placements, _ = _field_placements(layout)
        if api not in placements:
            print("  (already on Unused / not on layout; skip)")
            continue
        sid = _find_section_id_for_field_ids(layout, {placements[api]})
        if not sid:
            print("  (section not found; skip)", file=sys.stderr)
            continue
        if not _hide_one(
            s, api_domain, layout_id, sid, placements[api], dry_run=args.dry_run
        ):
            fail_api.append(api)

    if not args.dry_run:
        time.sleep(1.0)
        r2 = _crm(
            s, api_domain, "GET", f"/settings/layouts/{layout_id}", params={"module": MODULE}
        )
        if r2.status_code == 401:
            _reauth()
            r2 = _crm(
                s, api_domain, "GET", f"/settings/layouts/{layout_id}", params={"module": MODULE}
            )
        if r2.ok:
            layout2 = (r2.json().get("layouts") or [None])[0] or {}
            placements2, _ = _field_placements(layout2)
            if placements2:
                print(
                    "\nStill on main section (Blueprint blocks Zoho from moving to Unused):",
                    sorted(placements2),
                    file=sys.stderr,
                )
            if fail_api:
                print(
                    "\nPATCH error for (Blueprint / permissions):",
                    fail_api,
                    file=sys.stderr,
                )
            if placements2 or fail_api:
                return 2

    print(
        "\nDone. Hid on Standard layout: fields moved to Unused; Create/Edit no longer list them."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
