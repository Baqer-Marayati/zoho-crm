#!/usr/bin/env python3
"""
Leads — Industry picklist (OCRD list) + custom **Sector** (Private / Government).

1) **Industry** (standard field `Industry`): `PATCH` new picklist rows, then
   `PATCH` the **Standard** layout so only `-None-` and the file’s values stay *used*;
   previous options move to *unused* (Zoho does not hard-delete options).

2) **Sector**: create picklist if missing (API name `Sector`), options Private & Government;
   if the field already exists, merge missing options. Zoho usually places new fields on the
   active layout; if not, add this script’s layout `PATCH` with field `id` only.

  cd tools/zoho
  ./venv/bin/python provision_leads_industry_sector.py
  ./venv/bin/python provision_leads_industry_sector.py --dry-run
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import requests

from zoho_tokens import auth_headers, get_access_token_and_domain

API_VER = "v8"
MODULE = "Leads"
INDUSTRY_API = "Industry"
# Live org: Standard Leads layout + Lead Information (main block)
LAYOUT_ID = "7353692000000091055"
LEAD_INFO_SECTION_ID = "7353692000000209001"
FIELD_INDUSTRY_ID = "7353692000000002613"  # verify via GET if org differs
PICKLIST_FILE = (
    Path(__file__).resolve().parent.parent.parent
    / "artifacts"
    / "zoho"
    / "picklists"
    / "leads_industry_ocrh.txt"
)
SECTOR_LABEL = "Sector"
SECTOR_OPTIONS = ("Private", "Government")


def _crm(session: requests.Session, api_domain: str, method: str, path: str, **kwargs):
    url = f"{api_domain.rstrip('/')}/crm/{API_VER}{path}"
    return session.request(method, url, timeout=120, **kwargs)


def _slug(s: str) -> str:
    s2 = re.sub(r"[^a-zA-Z0-9]+", "_", s.strip()).strip("_")
    return s2[:100] if s2 else "value"


def _load_industry_values(path: Path) -> list[str]:
    out: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        t = line.split("#", 1)[0].strip()
        if t:
            out.append(t)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="Print actions only; no API writes.")
    args = ap.parse_args()

    if not PICKLIST_FILE.is_file():
        print(f"Missing picklist file: {PICKLIST_FILE}", file=sys.stderr)
        return 1
    industry_vals = _load_industry_values(PICKLIST_FILE)
    if not industry_vals:
        print("No industry values in file.", file=sys.stderr)
        return 1

    try:
        access, domain = get_access_token_and_domain()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1
    s = requests.Session()
    s.headers.update({**auth_headers(access), "Content-Type": "application/json"})

    # Resolve Industry id from API (override constant if org differs)
    r = _crm(s, domain, "GET", "/settings/fields", params={"module": MODULE, "type": "all"})
    if not r.ok:
        print(f"GET fields HTTP {r.status_code}: {r.text[:2000]}", file=sys.stderr)
        return 1
    industry_f = next(
        (f for f in r.json().get("fields", []) if f.get("api_name") == INDUSTRY_API), None
    )
    if not industry_f or not industry_f.get("id"):
        print("Industry field not found on Leads.", file=sys.stderr)
        return 1
    ind_id = str(industry_f["id"])

    if args.dry_run:
        print(f"Would add missing picklist options to Industry (id={ind_id}), then layout {LAYOUT_ID}")
        print("Values:", industry_vals)
        print(f"Would ensure Sector: {SECTOR_OPTIONS}")
        return 0

    # 1) Merge new Industry options
    r0 = _crm(s, domain, "GET", f"/settings/fields/{ind_id}", params={"module": MODULE})
    r0.raise_for_status()
    f0 = (r0.json().get("fields") or [r0.json()])[0]
    ex = {p.get("display_value") for p in (f0.get("pick_list_values") or [])}
    to_add = [v for v in industry_vals if v not in ex]
    if to_add:
        pvs_add = [{"display_value": v, "actual_value": _slug(v)} for v in to_add]
        r1 = _crm(
            s,
            domain,
            "PATCH",
            f"/settings/fields/{ind_id}",
            params={"module": MODULE},
            json={"fields": [{"id": ind_id, "pick_list_values": pvs_add}]},
        )
        if not r1.ok:
            print(f"PATCH Industry add HTTP {r1.status_code}: {r1.text[:3000]}", file=sys.stderr)
            return 1
        print(f"  Industry: added {len(to_add)} new option(s).")
    else:
        print("  Industry: all file values already present in field.")

    # 2) Layout: keep -None- + file values only
    r2 = _crm(s, domain, "GET", f"/settings/fields/{ind_id}", params={"module": MODULE})
    r2.raise_for_status()
    f1 = (r2.json().get("fields") or [r2.json()])[0]
    by_dv = {p.get("display_value"): p for p in (f1.get("pick_list_values") or [])}
    keep: list[dict] = []
    if "-None-" in by_dv:
        p = by_dv["-None-"]
        keep.append({"id": str(p["id"]), "display_value": "-None-"})
    for v in industry_vals:
        p = by_dv.get(v)
        if p:
            keep.append({"id": str(p["id"]), "display_value": v})
        else:
            print(f"  ERROR: missing option after add: {v!r}", file=sys.stderr)
            return 1

    body = {
        "layouts": [
            {
                "id": LAYOUT_ID,
                "sections": [
                    {
                        "id": LEAD_INFO_SECTION_ID,
                        "fields": [
                            {
                                "id": ind_id,
                                "pick_list_values": keep,
                            }
                        ],
                    }
                ],
            }
        ]
    }
    r3 = _crm(
        s,
        domain,
        "PATCH",
        f"/settings/layouts/{LAYOUT_ID}",
        params={"module": MODULE},
        json=body,
    )
    if not r3.ok:
        print(f"PATCH layout Industry HTTP {r3.status_code}: {r3.text[:3000]}", file=sys.stderr)
        return 1
    print(
        f"  Industry: Standard layout now exposes {len(keep)} values (-None- + {len(industry_vals)}). "
        "Other options are unused in Zoho."
    )

    # 3) Sector
    r4 = _crm(s, domain, "GET", "/settings/fields", params={"module": MODULE, "type": "all"})
    r4.raise_for_status()
    sec_f = None
    for f in r4.json().get("fields", []):
        if f.get("data_type") == "picklist" and (f.get("field_label") or "").strip() == SECTOR_LABEL:
            sec_f = f
            break
    if sec_f:
        sid = str(sec_f["id"])
        dvs = {p.get("display_value") for p in (sec_f.get("pick_list_values") or [])}
        missing = [x for x in SECTOR_OPTIONS if x not in dvs]
        if missing:
            add = [{"display_value": x, "actual_value": x} for x in missing]
            r5 = _crm(
                s,
                domain,
                "PATCH",
                f"/settings/fields/{sid}",
                params={"module": MODULE},
                json={"fields": [{"id": sid, "pick_list_values": add}]},
            )
            if not r5.ok:
                print(f"PATCH Sector HTTP {r5.status_code}: {r5.text[:2000]}", file=sys.stderr)
                return 1
            print(f"  Sector: merged options {missing}.")
        else:
            print("  Sector: field exists with Private & Government.")
        print(f"  Sector: id={sid} api_name={sec_f.get('api_name')}")
        return 0

    r6 = _crm(
        s,
        domain,
        "POST",
        "/settings/fields",
        params={"module": MODULE},
        json={
            "fields": [
                {
                    "field_label": SECTOR_LABEL,
                    "data_type": "picklist",
                    "pick_list_values": [
                        {"display_value": a, "actual_value": a} for a in SECTOR_OPTIONS
                    ],
                    "pick_list_values_sorted_lexically": True,
                    "enable_colour_code": False,
                }
            ]
        },
    )
    if not r6.ok:
        print(f"POST Sector HTTP {r6.status_code}: {r6.text[:3000]}", file=sys.stderr)
        return 1
    it = (r6.json().get("fields") or [{}])[0]
    det = (it.get("details") or {})
    new_id = det.get("id") or it.get("id")
    print(f"  Sector: created id={new_id} api_name=Sector (confirm in GET fields if renamed).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
