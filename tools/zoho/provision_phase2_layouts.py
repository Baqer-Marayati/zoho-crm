#!/usr/bin/env python3
"""
Phase 2 — Deals layout: Closing Date mandatory + Stage→picklist map dependencies.

Uses Zoho CRM API v8:
  PATCH  /settings/layouts/{layout_id}?module=Deals
  GET/POST/PUT /settings/layouts/{layout_id}/map_dependency?module=Deals

Requires OAuth scopes including at least:
  ZohoCRM.settings.layouts.READ
  ZohoCRM.settings.layouts.UPDATE
  ZohoCRM.settings.map_dependency.READ
  ZohoCRM.settings.map_dependency.CREATE
  ZohoCRM.settings.map_dependency.UPDATE
(or ZohoCRM.settings.ALL)

Map dependency strategy (approximates “only fill Lost Reason / Competitor on closed-lost”):
  - For stages whose label contains "closed lost" (case-insensitive), child shows all real
    picklist values (excluding the system \"-None-\" row).
  - For all other stages, child shows only \"-None-\".

Closing Date is set required on the Standard Deals layout if it is not already.

Lost Reason and Competitor are set **required** on that layout when --require-lost-fields (default: on).
With the Stage map above, open stages only expose \"-None-\", so reps can leave those fields as None until closed-lost.

Does not configure stage–probability % (still UI-only in most orgs).

  cd tools/zoho && ./venv/bin/python provision_phase2_layouts.py
  ./venv/bin/python provision_phase2_layouts.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import requests

from zoho_tokens import auth_headers, get_access_token_and_domain

API_VER = "v8"
SCRIPT_DIR = Path(__file__).resolve().parent

DEALS_MODULE = "Deals"
STAGE_API = "Stage"
CLOSING_API = "Closing_Date"
# Phase 2 script creates "Lost_Reason"; some orgs use Zoho's "Reason For Loss" instead.
LOST_API = "Lost_Reason"
LOST_API_FALLBACKS: tuple[str, ...] = ("Reason_For_Loss__s",)
COMP_API = "Competitor"


def _crm(session: requests.Session, api_domain: str, method: str, path: str, **kwargs):
    url = f"{api_domain.rstrip('/')}/crm/{API_VER}{path}"
    return session.request(method, url, timeout=120, **kwargs)


def _pick_standard_layout_id(layouts_payload: dict) -> str:
    layouts = layouts_payload.get("layouts") or []
    if not layouts:
        raise RuntimeError("No Deals layouts returned.")
    for lo in layouts:
        if lo.get("status") == "active" and lo.get("name") == "Standard":
            return str(lo["id"])
    for lo in layouts:
        if lo.get("status") == "active":
            return str(lo["id"])
    return str(layouts[0]["id"])


def _find_section_for_field(layout: dict, field_id: str) -> dict | None:
    for sec in layout.get("sections") or []:
        for f in sec.get("fields") or []:
            if str(f.get("id")) == str(field_id):
                return sec
    return None


def _fields_by_api_name(module: str, fields_payload: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for f in fields_payload.get("fields") or []:
        api = f.get("api_name")
        if api:
            out[str(api)] = f
    return out


def _resolve_lost_field(by_api: dict[str, dict]) -> dict | None:
    for key in (LOST_API, *LOST_API_FALLBACKS):
        if key in by_api:
            return by_api[key]
    return None


def _is_system_none(opt: dict) -> bool:
    dv = (opt.get("display_value") or "").strip()
    av = (opt.get("actual_value") or "").strip()
    return dv in ("-None-", "") and av in ("-None-", "", dv)


def _is_closed_lost_stage(opt: dict) -> bool:
    dv = (opt.get("display_value") or "").lower()
    av = (opt.get("actual_value") or "").lower()
    return "closed lost" in dv or "closed lost" in av


def _child_map_entry(opt: dict) -> dict[str, Any]:
    return {
        "display_value": opt.get("display_value"),
        "actual_value": opt.get("actual_value") or opt.get("display_value"),
        "id": str(opt["id"]),
    }


def _maps_for_stage(
    stage_opt: dict,
    child_field: dict,
) -> list[dict[str, Any]]:
    child_opts = child_field.get("pick_list_values") or []
    none_opts = [o for o in child_opts if _is_system_none(o)]
    real_opts = [o for o in child_opts if not _is_system_none(o)]

    if _is_closed_lost_stage(stage_opt):
        targets = real_opts
    else:
        targets = none_opts
    if not targets:
        raise RuntimeError(
            f"No picklist targets for Stage={stage_opt.get('display_value')!r} "
            f"on child {child_field.get('api_name')}; check -None- exists."
        )
    return [_child_map_entry(o) for o in targets]


def _build_map_dependency_body(
    stage_field: dict,
    child_field: dict,
) -> dict[str, Any]:
    pick_list_values: list[dict[str, Any]] = []
    for popt in stage_field.get("pick_list_values") or []:
        if str(popt.get("type") or "").lower() == "unused":
            continue
        pid = popt.get("id")
        if not pid:
            continue
        pick_list_values.append(
            {
                "display_value": popt.get("display_value"),
                "actual_value": popt.get("actual_value") or popt.get("display_value"),
                "id": str(pid),
                "maps": _maps_for_stage(popt, child_field),
            }
        )
    if not pick_list_values:
        raise RuntimeError("Stage has no picklist values; cannot map dependency.")

    return {
        "map_dependency": [
            {
                "parent": {
                    "api_name": stage_field["api_name"],
                    "id": str(stage_field["id"]),
                },
                "child": {
                    "api_name": child_field["api_name"],
                    "id": str(child_field["id"]),
                },
                "pick_list_values": pick_list_values,
            }
        ]
    }


def _sync_map_dependency(
    session: requests.Session,
    api_domain: str,
    layout_id: str,
    body: dict,
    dry_run: bool,
) -> bool:
    item = body["map_dependency"][0]
    parent_api = item["parent"]["api_name"]
    child_api = item["child"]["api_name"]

    r_get = _crm(
        session,
        api_domain,
        "GET",
        f"/settings/layouts/{layout_id}/map_dependency",
        params={"module": DEALS_MODULE},
        headers=session.headers,
    )
    if not r_get.ok:
        print(f"GET map_dependency HTTP {r_get.status_code}: {r_get.text[:2000]}", file=sys.stderr)
        return False

    existing = r_get.json().get("map_dependency") or []
    dep_id: str | None = None
    for md in existing:
        p = md.get("parent") or {}
        c = md.get("child") or {}
        if p.get("api_name") == parent_api and c.get("api_name") == child_api:
            dep_id = str(md.get("id") or "")
            break

    label = f"{parent_api} → {child_api}"
    if dep_id:
        print(f"PUT map_dependency id={dep_id} ({label})")
        if dry_run:
            return True
        r_put = _crm(
            session,
            api_domain,
            "PUT",
            f"/settings/layouts/{layout_id}/map_dependency/{dep_id}",
            params={"module": DEALS_MODULE},
            headers=session.headers,
            data=json.dumps(body),
        )
        if not r_put.ok:
            print(f"PUT failed HTTP {r_put.status_code}: {r_put.text[:2000]}", file=sys.stderr)
            return False
        print(json.dumps(r_put.json(), indent=2)[:3500])
        return True

    print(f"POST map_dependency ({label})")
    if dry_run:
        return True
    r_post = _crm(
        session,
        api_domain,
        "POST",
        f"/settings/layouts/{layout_id}/map_dependency",
        params={"module": DEALS_MODULE},
        headers=session.headers,
        data=json.dumps(body),
    )
    if not r_post.ok:
        print(f"POST failed HTTP {r_post.status_code}: {r_post.text[:2000]}", file=sys.stderr)
        return False
    print(json.dumps(r_post.json(), indent=2)[:3500])
    return True


def _field_required_flags(layout: dict, field_ids: list[str]) -> dict[str, bool | None]:
    out: dict[str, bool | None] = {fid: None for fid in field_ids}
    for sec in layout.get("sections") or []:
        for f in sec.get("fields") or []:
            fid = str(f.get("id") or "")
            if fid in out:
                out[fid] = bool(f.get("required"))
    return out


def _ensure_picklist_fields_required(
    session: requests.Session,
    api_domain: str,
    layout_id: str,
    field_ids: list[str],
    dry_run: bool,
) -> bool:
    r_lo = _crm(
        session,
        api_domain,
        "GET",
        f"/settings/layouts/{layout_id}",
        params={"module": DEALS_MODULE},
        headers=session.headers,
    )
    if not r_lo.ok:
        print(f"GET layout HTTP {r_lo.status_code}: {r_lo.text[:2000]}", file=sys.stderr)
        return False
    layout = (r_lo.json().get("layouts") or [None])[0]
    if not layout:
        print("Empty layout response", file=sys.stderr)
        return False

    flags = _field_required_flags(layout, field_ids)
    if all(flags.get(fid) is True for fid in field_ids):
        print("Lost Reason / Competitor already required on layout; skip PATCH.")
        return True

    sec_id: str | None = None
    fields_patch: list[dict[str, Any]] = []
    for fid in field_ids:
        sec = _find_section_for_field(layout, fid)
        if not sec or not sec.get("id"):
            print(f"No section for field id {fid}", file=sys.stderr)
            return False
        if sec_id is None:
            sec_id = str(sec["id"])
        elif sec_id != str(sec["id"]):
            print("Lost Reason and Competitor must share one section for a single PATCH.", file=sys.stderr)
            return False
        fields_patch.append({"id": str(fid), "required": True})

    patch = {"layouts": [{"sections": [{"id": sec_id, "fields": fields_patch}]}]}
    print(f"PATCH layout {layout_id}: Lost Reason + Competitor required=True")
    if dry_run:
        return True
    r_patch = _crm(
        session,
        api_domain,
        "PATCH",
        f"/settings/layouts/{layout_id}",
        params={"module": DEALS_MODULE},
        headers=session.headers,
        data=json.dumps(patch),
    )
    if not r_patch.ok:
        print(f"PATCH layout HTTP {r_patch.status_code}: {r_patch.text[:2000]}", file=sys.stderr)
        return False
    try:
        print(json.dumps(r_patch.json(), indent=2)[:2000])
    except json.JSONDecodeError:
        print(r_patch.text[:2000])
    return True


def _ensure_closing_date_required(
    session: requests.Session,
    api_domain: str,
    layout_id: str,
    closing_field_id: str,
    dry_run: bool,
) -> bool:
    r_lo = _crm(
        session,
        api_domain,
        "GET",
        f"/settings/layouts/{layout_id}",
        params={"module": DEALS_MODULE},
        headers=session.headers,
    )
    if not r_lo.ok:
        print(f"GET layout HTTP {r_lo.status_code}: {r_lo.text[:2000]}", file=sys.stderr)
        return False
    layout = (r_lo.json().get("layouts") or [None])[0]
    if not layout:
        print("Empty layout response", file=sys.stderr)
        return False

    sec = _find_section_for_field(layout, closing_field_id)
    if not sec or not sec.get("id"):
        print("Could not find section for Closing Date on layout.", file=sys.stderr)
        return False

    for f in sec.get("fields") or []:
        if str(f.get("id")) == str(closing_field_id):
            if f.get("required") is True:
                print("Closing Date already required on layout; skip PATCH.")
                return True
            break

    patch = {
        "layouts": [
            {
                "sections": [
                    {
                        "id": str(sec["id"]),
                        "fields": [{"id": str(closing_field_id), "required": True}],
                    }
                ]
            }
        ]
    }
    print(f"PATCH layout {layout_id}: Closing_Date required=True (section {sec['id']})")
    if dry_run:
        return True
    r_patch = _crm(
        session,
        api_domain,
        "PATCH",
        f"/settings/layouts/{layout_id}",
        params={"module": DEALS_MODULE},
        headers=session.headers,
        data=json.dumps(patch),
    )
    if not r_patch.ok:
        print(f"PATCH layout HTTP {r_patch.status_code}: {r_patch.text[:2000]}", file=sys.stderr)
        return False
    try:
        print(json.dumps(r_patch.json(), indent=2)[:2000])
    except json.JSONDecodeError:
        print(r_patch.text[:2000])
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Phase 2 Deals layout: Closing Date required + Stage dependencies for Lost Reason & Competitor"
    )
    parser.add_argument("--dry-run", action="store_true", help="Print actions only")
    parser.add_argument(
        "--no-require-lost-fields",
        action="store_true",
        help="Do not set Lost Reason / Competitor as layout-required (map dependency still applied)",
    )
    args = parser.parse_args()

    access, api_domain = get_access_token_and_domain()
    session = requests.Session()
    session.headers.update(auth_headers(access))
    session.headers["Content-Type"] = "application/json"

    r_layouts = _crm(session, api_domain, "GET", "/settings/layouts", params={"module": DEALS_MODULE})
    if not r_layouts.ok:
        print(
            f"Layouts API failed HTTP {r_layouts.status_code}. "
            "Need ZohoCRM.settings.layouts.READ (or settings.ALL).\n"
            f"{r_layouts.text[:1500]}",
            file=sys.stderr,
        )
        return 1

    layout_id = _pick_standard_layout_id(r_layouts.json())
    print(f"Deals Standard layout_id={layout_id}")

    r_fields = _crm(
        session,
        api_domain,
        "GET",
        "/settings/fields",
        params={"module": DEALS_MODULE, "per_page": 200},
    )
    if not r_fields.ok:
        print(f"Fields API HTTP {r_fields.status_code}: {r_fields.text[:1500]}", file=sys.stderr)
        return 1
    fr = r_fields.json()
    by_api = _fields_by_api_name(DEALS_MODULE, fr)
    page = 1
    while (fr.get("info") or {}).get("more_records"):
        page += 1
        r2 = _crm(
            session,
            api_domain,
            "GET",
            "/settings/fields",
            params={"module": DEALS_MODULE, "per_page": 200, "page": page},
        )
        if not r2.ok:
            break
        fr = r2.json()
        for f in fr.get("fields") or []:
            api = f.get("api_name")
            if api:
                by_api[str(api)] = f

    for key in (STAGE_API, CLOSING_API, COMP_API):
        if key not in by_api:
            print(
                f"Missing Deals field api_name={key}. Run provision_phase2_fields.py first.",
                file=sys.stderr,
            )
            return 1

    lost_f = _resolve_lost_field(by_api)
    if not lost_f:
        print(
            "Missing a Lost/closed-lost reason field (Lost_Reason or Reason_For_Loss__s).",
            file=sys.stderr,
        )
        return 1

    stage_f = by_api[STAGE_API]
    comp_f = by_api[COMP_API]
    closing_id = str(by_api[CLOSING_API]["id"])

    ok = _ensure_closing_date_required(session, api_domain, layout_id, closing_id, args.dry_run)
    if not args.no_require_lost_fields:
        ok = (
            _ensure_picklist_fields_required(
                session,
                api_domain,
                layout_id,
                [str(lost_f["id"]), str(by_api[COMP_API]["id"])],
                args.dry_run,
            )
            and ok
        )
    ok = (
        _sync_map_dependency(
            session,
            api_domain,
            layout_id,
            _build_map_dependency_body(stage_f, lost_f),
            args.dry_run,
        )
        and ok
    )
    ok = (
        _sync_map_dependency(
            session,
            api_domain,
            layout_id,
            _build_map_dependency_body(stage_f, comp_f),
            args.dry_run,
        )
        and ok
    )

    if ok:
        print("\nDone. Stage–probability % is still manual in Zoho UI if your org uses it.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
