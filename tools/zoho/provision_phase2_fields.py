#!/usr/bin/env python3
"""
Create Phase 2 picklist fields in Zoho CRM (Leads + Deals) via API v8 — idempotent.

Requires OAuth scope: ZohoCRM.settings.fields.CREATE (or ZohoCRM.settings.ALL).

  cd tools/zoho && ./venv/bin/python provision_phase2_fields.py
  ./venv/bin/python provision_phase2_fields.py --dry-run

Picklist values are read from ../../artifacts/zoho/picklists/*.csv

Also:
  - Ensures **Line of business** exists on **Deals** (same label/values as Leads) and is on the
    Standard Deals layout — for unified pipeline + sector filtering.
  - Appends any **new** CSV values (e.g. Radiology) to an existing **Leads** Line of business
    field via PATCH when possible.
  - Appends new values to an existing **Deals** **Competitor** picklist from
    `artifacts/zoho/picklists/competitors_template.csv` when the field already exists.

What this does NOT configure via this script: lead conversion field mapping (that is org
metadata; read/audit with `audit_lead_conversion_mapping.py` — mapping is on each Lead
field’s `convert_mapping` in `GET /settings/fields?module=Leads`). This script also does not
set layout rules for “required on Closed Lost”, stage–probability %, or Closing Date mandatory
(those use `provision_phase2_layouts.py` or UI). See docs/zoho/PHASE2-AUTOMATED.md after running.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
import requests

from zoho_tokens import auth_headers, get_access_token_and_domain

API_VER = "v8"
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_PICKLISTS = SCRIPT_DIR.parent.parent / "artifacts" / "zoho" / "picklists"

# Field labels must match what you want in the UI (and for conversion mapping hints).
LEAD_LINE_LABEL = "Line of business"
DEAL_LOST_LABEL = "Lost Reason"
DEAL_COMPETITOR_LABEL = "Competitor"

# Standard Deals layout (live org); used to surface Line of business on Deal records.
DEALS_STANDARD_LAYOUT_ID = "7353692000000091023"


def _slug_actual(display: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", display.strip()).strip("_")
    return s[:100] if s else "value"


def _read_picklist_csv(path: Path) -> list[str]:
    if not path.is_file():
        raise FileNotFoundError(path)
    out: list[str] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        col = reader.fieldnames[0] if reader.fieldnames else "Display_Value"
        tbd_n = 0
        for row in reader:
            raw = (row.get(col) or "").strip()
            if not raw:
                continue
            if raw.startswith("REPLACE_ME"):
                tbd_n += 1
                raw = f"Competitor TBD {tbd_n}"
            out.append(raw)
    return out


def _crm(session: requests.Session, api_domain: str, method: str, path: str, **kwargs):
    url = f"{api_domain.rstrip('/')}/crm/{API_VER}{path}"
    return session.request(method, url, timeout=120, **kwargs)


def _crm_get_fields(session: requests.Session, api_domain: str, module: str) -> dict:
    url = f"{api_domain.rstrip('/')}/crm/{API_VER}/settings/fields"
    r = session.get(url, params={"module": module}, timeout=120)
    if not r.ok:
        raise RuntimeError(f"GET fields {module} HTTP {r.status_code}: {r.text[:2000]}")
    return r.json()


def _labels_lower(fields_payload: dict) -> set[str]:
    return {
        (f.get("field_label") or "").strip().lower()
        for f in fields_payload.get("fields", [])
        if f.get("field_label")
    }


def _field_by_label(fields_payload: dict, label: str) -> dict | None:
    ll = label.strip().lower()
    for f in fields_payload.get("fields", []):
        if (f.get("field_label") or "").strip().lower() == ll:
            return f
    return None


def _is_system_none(opt: dict) -> bool:
    dv = (opt.get("display_value") or "").strip()
    av = (opt.get("actual_value") or "").strip()
    return dv in ("-None-", "") and av in ("-None-", "", dv)


def _picklist_field(field_label: str, values: list[dict]) -> dict:
    return {
        "field_label": field_label,
        "data_type": "picklist",
        "pick_list_values": values,
        "pick_list_values_sorted_lexically": True,
        "enable_colour_code": False,
    }


def _build_pick_values(display_values: list[str]) -> list[dict]:
    return [
        {"display_value": v, "actual_value": _slug_actual(v)}
        for v in display_values
    ]


def _post_fields(
    session: requests.Session,
    api_domain: str,
    module: str,
    field_defs: list[dict],
    dry_run: bool,
) -> bool:
    if not field_defs:
        return True
    print(f"POST {len(field_defs)} field(s) on module={module}:")
    for fd in field_defs:
        print(f"  - {fd['field_label']} ({len(fd.get('pick_list_values', []))} options)")
    if dry_run:
        return True
    url = f"{api_domain.rstrip('/')}/crm/{API_VER}/settings/fields"
    r = session.post(
        url,
        params={"module": module},
        data=json.dumps({"fields": field_defs}),
        headers={**session.headers, "Content-Type": "application/json"},
        timeout=120,
    )
    txt = r.text[:4000]
    if not r.ok:
        print(f"HTTP {r.status_code}: {txt}", file=sys.stderr)
        return False
    try:
        print(json.dumps(r.json(), indent=2)[:3500])
    except json.JSONDecodeError:
        print(txt)
    return True


def _find_target_section(layout: dict, preferred_substring: str | None) -> dict | None:
    sections = layout.get("sections") or []
    if preferred_substring:
        ps = preferred_substring.lower()
        for sec in sections:
            name = (sec.get("name") or sec.get("display_label") or "").lower()
            if ps in name and sec.get("id") is not None:
                return sec
    for sec in sections:
        if sec.get("id") and sec.get("fields") is not None:
            return sec
    return sections[0] if sections else None


def _ensure_field_on_deals_layout(
    session: requests.Session,
    api_domain: str,
    field_id: str,
    field_label: str,
    dry_run: bool,
) -> bool:
    r_lo = _crm(
        session,
        api_domain,
        "GET",
        f"/settings/layouts/{DEALS_STANDARD_LAYOUT_ID}",
        params={"module": "Deals"},
    )
    if not r_lo.ok:
        print(f"GET Deals layout HTTP {r_lo.status_code}: {r_lo.text[:2000]}", file=sys.stderr)
        return False
    layout = (r_lo.json().get("layouts") or [None])[0]
    if not layout:
        print("Empty Deals layout response", file=sys.stderr)
        return False
    for sec in layout.get("sections") or []:
        for f in sec.get("fields") or []:
            if str(f.get("id")) == str(field_id):
                sec_name = sec.get("name") or sec.get("display_label") or "?"
                print(
                    f"Deals: '{field_label}' already on layout section '{sec_name}'; skip PATCH."
                )
                return True
    sec = _find_target_section(layout, "potential")
    if not sec or not sec.get("id"):
        print("No section to place Line of business on Deals layout.", file=sys.stderr)
        return False
    print(
        f"PATCH Deals layout: add '{field_label}' to section "
        f"'{sec.get('name') or sec.get('display_label')}' (id={sec['id']})"
    )
    if dry_run:
        return True
    patch = {
        "layouts": [
            {
                "sections": [
                    {
                        "id": str(sec["id"]),
                        "fields": [{"id": str(field_id)}],
                    }
                ]
            }
        ]
    }
    r_patch = _crm(
        session,
        api_domain,
        "PATCH",
        f"/settings/layouts/{DEALS_STANDARD_LAYOUT_ID}",
        params={"module": "Deals"},
        data=json.dumps(patch),
        headers={**session.headers, "Content-Type": "application/json"},
    )
    if not r_patch.ok:
        print(f"PATCH layout HTTP {r_patch.status_code}: {r_patch.text[:2000]}", file=sys.stderr)
        return False
    try:
        print(json.dumps(r_patch.json(), indent=2)[:1500])
    except json.JSONDecodeError:
        print(r_patch.text[:1500])
    return True


def _get_deals_line_of_business_field_id(
    session: requests.Session, api_domain: str
) -> str | None:
    payload = _crm_get_fields(session, api_domain, "Deals")
    f = _field_by_label(payload, LEAD_LINE_LABEL)
    return str(f["id"]) if f and f.get("id") else None


def _merge_deals_competitor_options(
    session: requests.Session,
    api_domain: str,
    desired_display: list[str],
    dry_run: bool,
) -> bool:
    """Append picklist options on Deals Competitor when CSV has new values."""
    payload = _crm_get_fields(session, api_domain, "Deals")
    f = _field_by_label(payload, DEAL_COMPETITOR_LABEL)
    if not f or not f.get("id"):
        return True
    fid = str(f["id"])
    existing = {
        (o.get("display_value") or "").strip()
        for o in (f.get("pick_list_values") or [])
        if not _is_system_none(o)
    }
    to_add = [d for d in desired_display if d not in existing]
    if not to_add:
        print(f"Deals: '{DEAL_COMPETITOR_LABEL}' already has all CSV values; skip PATCH.")
        return True
    new_opts = _build_pick_values(to_add)
    print(f"Deals: PATCH '{DEAL_COMPETITOR_LABEL}' — add options: {to_add}")
    if dry_run:
        return True
    keep = [
        {
            "display_value": o.get("display_value"),
            "actual_value": o.get("actual_value") or o.get("display_value"),
            "id": str(o["id"]),
        }
        for o in (f.get("pick_list_values") or [])
        if o.get("id") and not _is_system_none(o)
    ]
    merged = keep + [
        {"display_value": x["display_value"], "actual_value": x["actual_value"]} for x in new_opts
    ]
    r = _crm(
        session,
        api_domain,
        "PATCH",
        f"/settings/fields/{fid}",
        params={"module": "Deals"},
        data=json.dumps({"fields": [{"id": fid, "pick_list_values": merged}]}),
        headers={**session.headers, "Content-Type": "application/json"},
    )
    if not r.ok:
        print(
            f"PATCH Deals Competitor HTTP {r.status_code}: {r.text[:2000]}\n"
            "  If this fails, add values in Setup → Deals → Competitor.",
            file=sys.stderr,
        )
        return False
    try:
        print(json.dumps(r.json(), indent=2)[:2000])
    except json.JSONDecodeError:
        print(r.text[:1500])
    return True


def _merge_deal_line_of_business_options(
    session: requests.Session,
    api_domain: str,
    desired_display: list[str],
    dry_run: bool,
) -> bool:
    """Append picklist options on Deals Line of business when CSV has new values."""
    payload = _crm_get_fields(session, api_domain, "Deals")
    f = _field_by_label(payload, LEAD_LINE_LABEL)
    if not f or not f.get("id"):
        return True
    fid = str(f["id"])
    existing = {
        (o.get("display_value") or "").strip()
        for o in (f.get("pick_list_values") or [])
        if not _is_system_none(o)
    }
    to_add = [d for d in desired_display if d not in existing]
    if not to_add:
        print(f"Deals: '{LEAD_LINE_LABEL}' already has all CSV values; skip PATCH.")
        return True
    new_opts = _build_pick_values(to_add)
    print(f"Deals: PATCH '{LEAD_LINE_LABEL}' — add options: {to_add}")
    if dry_run:
        return True
    keep = [
        {
            "display_value": o.get("display_value"),
            "actual_value": o.get("actual_value") or o.get("display_value"),
            "id": str(o["id"]),
        }
        for o in (f.get("pick_list_values") or [])
        if o.get("id") and not _is_system_none(o)
    ]
    merged = keep + [
        {"display_value": x["display_value"], "actual_value": x["actual_value"]} for x in new_opts
    ]
    r = _crm(
        session,
        api_domain,
        "PATCH",
        f"/settings/fields/{fid}",
        params={"module": "Deals"},
        data=json.dumps({"fields": [{"id": fid, "pick_list_values": merged}]}),
        headers={**session.headers, "Content-Type": "application/json"},
    )
    if not r.ok:
        print(
            f"PATCH Deals picklist HTTP {r.status_code}: {r.text[:2000]}\n"
            "  If this fails, add the new values manually in Setup → Deals → Line of business.",
            file=sys.stderr,
        )
        return False
    try:
        print(json.dumps(r.json(), indent=2)[:2000])
    except json.JSONDecodeError:
        print(r.text[:1500])
    return True


def _merge_lead_line_of_business_options(
    session: requests.Session,
    api_domain: str,
    desired_display: list[str],
    dry_run: bool,
) -> bool:
    """Append picklist options on Leads Line of business when CSV has new values."""
    payload = _crm_get_fields(session, api_domain, "Leads")
    f = _field_by_label(payload, LEAD_LINE_LABEL)
    if not f or not f.get("id"):
        return True
    fid = str(f["id"])
    existing = {
        (o.get("display_value") or "").strip()
        for o in (f.get("pick_list_values") or [])
        if not _is_system_none(o)
    }
    to_add = [d for d in desired_display if d not in existing]
    if not to_add:
        print(f"Leads: '{LEAD_LINE_LABEL}' already has all CSV values; skip PATCH.")
        return True
    new_opts = _build_pick_values(to_add)
    print(f"Leads: PATCH '{LEAD_LINE_LABEL}' — add options: {to_add}")
    if dry_run:
        return True
    # v8 expects a `fields` array; send merged pick_list_values to avoid wiping existing options.
    keep = [
        {
            "display_value": o.get("display_value"),
            "actual_value": o.get("actual_value") or o.get("display_value"),
            "id": str(o["id"]),
        }
        for o in (f.get("pick_list_values") or [])
        if o.get("id") and not _is_system_none(o)
    ]
    merged = keep + [
        {"display_value": x["display_value"], "actual_value": x["actual_value"]} for x in new_opts
    ]
    r = _crm(
        session,
        api_domain,
        "PATCH",
        f"/settings/fields/{fid}",
        params={"module": "Leads"},
        data=json.dumps({"fields": [{"id": fid, "pick_list_values": merged}]}),
        headers={**session.headers, "Content-Type": "application/json"},
    )
    if not r.ok:
        print(
            f"PATCH Leads picklist HTTP {r.status_code}: {r.text[:2000]}\n"
            "  If this fails, add the new values manually in Setup → Leads → Line of business.",
            file=sys.stderr,
        )
        return False
    try:
        print(json.dumps(r.json(), indent=2)[:2000])
    except json.JSONDecodeError:
        print(r.text[:1500])
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision Phase 2 picklist fields in Zoho CRM")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        access, api_domain = get_access_token_and_domain()
    except RuntimeError as e:
        print(e, file=sys.stderr)
        return 1

    session = requests.Session()
    session.headers.update(auth_headers(access))

    line_display = _read_picklist_csv(REPO_PICKLISTS / "line_of_business.csv")
    line_vals = _build_pick_values(line_display)
    lost_vals = _build_pick_values(_read_picklist_csv(REPO_PICKLISTS / "lost_reasons.csv"))
    comp_display = _read_picklist_csv(REPO_PICKLISTS / "competitors_template.csv")
    comp_vals = _build_pick_values(comp_display)

    lead_payload = _crm_get_fields(session, api_domain, "Leads")
    deal_payload = _crm_get_fields(session, api_domain, "Deals")
    lead_labels = _labels_lower(lead_payload)
    deal_labels = _labels_lower(deal_payload)

    lead_create: list[dict] = []
    if LEAD_LINE_LABEL.lower() not in lead_labels:
        lead_create.append(_picklist_field(LEAD_LINE_LABEL, line_vals))
    else:
        print(f"Skip Leads: '{LEAD_LINE_LABEL}' already exists.")

    deal_create: list[dict] = []
    if LEAD_LINE_LABEL.lower() not in deal_labels:
        deal_create.append(_picklist_field(LEAD_LINE_LABEL, line_vals))
    else:
        print(f"Skip Deals: '{LEAD_LINE_LABEL}' already exists.")

    if DEAL_LOST_LABEL.lower() not in deal_labels:
        deal_create.append(_picklist_field(DEAL_LOST_LABEL, lost_vals))
    else:
        print(f"Skip Deals: '{DEAL_LOST_LABEL}' already exists.")

    if DEAL_COMPETITOR_LABEL.lower() not in deal_labels:
        deal_create.append(_picklist_field(DEAL_COMPETITOR_LABEL, comp_vals))
    else:
        print(f"Skip Deals: '{DEAL_COMPETITOR_LABEL}' already exists.")

    ok = True
    if lead_create:
        ok = _post_fields(session, api_domain, "Leads", lead_create, args.dry_run) and ok
    if deal_create:
        ok = _post_fields(session, api_domain, "Deals", deal_create, args.dry_run) and ok

    if LEAD_LINE_LABEL.lower() in lead_labels or lead_create:
        ok = (
            _merge_lead_line_of_business_options(
                session, api_domain, line_display, args.dry_run
            )
            and ok
        )

    fid_deal_lob = _get_deals_line_of_business_field_id(session, api_domain)
    if fid_deal_lob:
        ok = (
            _merge_deal_line_of_business_options(
                session, api_domain, line_display, args.dry_run
            )
            and ok
        )
        ok = (
            _ensure_field_on_deals_layout(
                session, api_domain, fid_deal_lob, LEAD_LINE_LABEL, args.dry_run
            )
            and ok
        )
    elif args.dry_run and LEAD_LINE_LABEL.lower() not in deal_labels:
        print(
            "dry-run: would POST Line of business on Deals, then add it to Standard layout."
        )

    if DEAL_COMPETITOR_LABEL.lower() in deal_labels or any(
        fd.get("field_label") == DEAL_COMPETITOR_LABEL for fd in deal_create
    ):
        ok = _merge_deals_competitor_options(
            session, api_domain, comp_display, args.dry_run
        ) and ok

    if ok:
        print(
            "\nNext: open docs/zoho/PHASE2-AUTOMATED.md for the short UI follow-up "
            "(conversion mapping Line of business → Deal, closing date, Closed Lost rules, stage %)."
        )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
