#!/usr/bin/env python3
"""
Align Deals **Stage** *display labels* on the Standard layout with agreed names (Zoho CRM API v8).

Zoho ties Stage options to the Deals layout. Renaming via **PATCH .../settings/fields** often
no-ops unless options are layout-associated; the reliable approach is **PATCH .../settings/layouts**
with the Stage field's **pick_list_values** (id + display_value) for exactly the active stages you
want on the layout. Any omitted Stage option is moved to Unused and disappears from Stage View.

Renames applied (display only; **actual_value** stays as in Zoho for API stability):

  Value Proposition      → Proposal / Quote
  Proposal/Price Quote   → Proposal / Quote
  Solution / Value       → Proposal / Quote (already-renamed orgs)
  Quote Sent             → Proposal / Quote (already-renamed orgs)
  Negotiation/Review     → Negotiation

When two layout options collapse to the same display, this script keeps the **first** picklist row Zoho returns and drops the duplicate key; **bulk-replace legacy Stage values** on open Deals before/after if any records still point at the merged-away id.

Requires: ZohoCRM.settings.layouts.UPDATE, ZohoCRM.settings.fields.READ (or settings.ALL).

  cd tools/zoho && ./venv/bin/python provision_deal_stage_picklist.py
  ./venv/bin/python provision_deal_stage_picklist.py --dry-run

Then: provision_pipelines.py --sync && provision_phase2_layouts.py

If the Standard layout id differs in another org, pass --layout-id (optional; defaults to API discovery).
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
SEED_PATH = SCRIPT_DIR / "pipelines_seed.json"
DEALS_MODULE = "Deals"

# Old label → new label (display in UI / pipeline). Match pipelines_seed.json.
STAGE_RENAME: dict[str, str] = {
    "Value Proposition": "Proposal / Quote",
    "Proposal/Price Quote": "Proposal / Quote",
    "Solution / Value": "Proposal / Quote",
    "Quote Sent": "Proposal / Quote",
    "Negotiation/Review": "Negotiation",
}


def _crm(session: requests.Session, api_domain: str, method: str, path: str, **kwargs):
    url = f"{api_domain.rstrip('/')}/crm/{API_VER}{path}"
    return session.request(method, url, timeout=120, **kwargs)


def _pick_standard_layout_id(layouts_payload: dict) -> str:
    layouts = layouts_payload.get("layouts") or []
    for lo in layouts:
        if lo.get("status") == "active" and lo.get("name") == "Standard":
            return str(lo["id"])
    for lo in layouts:
        if lo.get("status") == "active":
            return str(lo["id"])
    raise RuntimeError("No active Deals layout found.")


def _find_stage_field_on_layout(layout: dict) -> tuple[str, str] | None:
    """Return (section_id, field_row_id) for Stage on this layout."""
    for sec in layout.get("sections") or []:
        sid = sec.get("id")
        if not sid:
            continue
        for f in sec.get("fields") or []:
            if f.get("api_name") == "Stage" and f.get("id"):
                return str(sid), str(f["id"])
    return None


def _default_pipeline_stages(seed: dict) -> list[str]:
    for p in seed.get("pipelines") or []:
        if p.get("default") and p.get("stages"):
            return [str(s).strip() for s in p["stages"] if str(s).strip()]
    for p in seed.get("pipelines") or []:
        if p.get("stages"):
            return [str(s).strip() for s in p["stages"] if str(s).strip()]
    raise RuntimeError("pipelines_seed.json: no pipeline with stages")


def main() -> int:
    parser = argparse.ArgumentParser(description="Update Deals Stage display labels via Standard layout PATCH")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--seed", type=Path, default=SEED_PATH, help=f"Seed JSON (default: {SEED_PATH})")
    parser.add_argument("--layout-id", type=str, default="", help="Deals Standard layout id (default: discover via API)")
    args = parser.parse_args()

    if not args.seed.is_file():
        print(f"Seed not found: {args.seed}", file=sys.stderr)
        return 1

    seed = json.loads(args.seed.read_text(encoding="utf-8"))
    want_stages = _default_pipeline_stages(seed)

    try:
        access, api_domain = get_access_token_and_domain()
    except RuntimeError as e:
        print(e, file=sys.stderr)
        return 1

    session = requests.Session()
    session.headers.update(auth_headers(access))
    session.headers["Content-Type"] = "application/json"

    layout_id = (args.layout_id or "").strip()
    if not layout_id:
        r_lo = _crm(session, api_domain, "GET", "/settings/layouts", params={"module": DEALS_MODULE})
        if not r_lo.ok:
            print(f"GET layouts HTTP {r_lo.status_code}: {r_lo.text[:2000]}", file=sys.stderr)
            return 1
        layout_id = _pick_standard_layout_id(r_lo.json())

    r_lay = _crm(session, api_domain, "GET", f"/settings/layouts/{layout_id}", params={"module": DEALS_MODULE})
    if not r_lay.ok:
        print(f"GET layout HTTP {r_lay.status_code}: {r_lay.text[:2000]}", file=sys.stderr)
        return 1
    layout = (r_lay.json().get("layouts") or [None])[0]
    if not layout:
        print("Empty layout response.", file=sys.stderr)
        return 1

    found = _find_stage_field_on_layout(layout)
    if not found:
        print("Stage field not found on Standard Deals layout.", file=sys.stderr)
        return 1
    section_id, stage_field_row_id = found

    r_f = _crm(
        session,
        api_domain,
        "GET",
        f"/settings/fields/{stage_field_row_id}",
        params={"module": DEALS_MODULE},
    )
    if not r_f.ok:
        print(f"GET Stage field HTTP {r_f.status_code}: {r_f.text[:2000]}", file=sys.stderr)
        return 1
    fobj = (r_f.json().get("fields") or [r_f.json()])[0]
    raw_opts: list[dict[str, Any]] = list(fobj.get("pick_list_values") or [])

    stage_option_by_display: dict[str, dict[str, Any]] = {}
    duplicate_displays: set[str] = set()
    for o in raw_opts:
        oid = o.get("id")
        if not oid:
            continue
        dv = (o.get("display_value") or "").strip()
        new_dv = STAGE_RENAME.get(dv, dv)
        if new_dv in stage_option_by_display:
            duplicate_displays.add(new_dv)
            continue
        stage_option_by_display[new_dv] = o
        if new_dv != dv:
            print(f"  Layout label: {dv!r} → {new_dv!r} (id={oid})")

    if duplicate_displays:
        print(
            "  Warning: duplicate Stage display(s) after rename; using the first option for: "
            + ", ".join(sorted(duplicate_displays)),
            file=sys.stderr,
        )

    pick_list_values: list[dict[str, str]] = []
    missing = []
    for sequence_number, stage in enumerate(want_stages, start=1):
        opt = stage_option_by_display.get(stage)
        if not opt:
            missing.append(stage)
            continue
        pick_list_values.append(
            {
                "id": str(opt["id"]),
                "display_value": stage,
                "sequence_number": sequence_number,
            }
        )

    if missing:
        print(
            "  Warning: pipelines_seed stages not found as picklist options after renames: "
            + ", ".join(missing),
            file=sys.stderr,
        )
        return 2

    excluded = [
        display
        for display in stage_option_by_display
        if display not in set(want_stages)
    ]
    if excluded:
        print("  Moving unused Stage option(s) off this layout: " + ", ".join(excluded))

    if args.dry_run:
        print(f"Dry run: would PATCH layout {layout_id} with {len(pick_list_values)} Stage row(s).")
        return 0

    body = {
        "layouts": [
            {
                "id": layout_id,
                "sections": [
                    {
                        "id": section_id,
                        "fields": [{"id": stage_field_row_id, "pick_list_values": pick_list_values}],
                    }
                ],
            }
        ]
    }
    r_patch = _crm(
        session,
        api_domain,
        "PATCH",
        f"/settings/layouts/{layout_id}",
        params={"module": DEALS_MODULE},
        data=json.dumps(body),
    )
    if not r_patch.ok:
        print(f"PATCH layout HTTP {r_patch.status_code}: {r_patch.text[:2000]}", file=sys.stderr)
        return 1
    try:
        print(json.dumps(r_patch.json(), indent=2)[:2500])
    except json.JSONDecodeError:
        print(r_patch.text[:2000])
    print("Done. Next: provision_pipelines.py --sync && provision_phase2_layouts.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
