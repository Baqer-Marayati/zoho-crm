#!/usr/bin/env python3
"""
Create Zoho CRM deal pipelines from pipelines_seed.json (Zoho CRM API v8).

The live seed uses a **single** default pipeline whose `display_value` matches Zoho’s UI name
(typically **Standard (Standard)**). Extra historical pipelines (e.g. Production / MPS) are removed
with Zoho’s **transfer-and-delete** API — see `docs/zoho/SALES-PIPELINE-AND-STAGES.md` §2.1.

Requires OAuth scopes that include at least:
  ZohoCRM.settings.layouts.READ
  ZohoCRM.settings.pipeline.READ
  ZohoCRM.settings.pipeline.CREATE
  ZohoCRM.settings.pipeline.UPDATE  (when using --sync)
(or use ZohoCRM.settings.ALL for development)

If your refresh token was created with modules-only scopes, generate a new grant with
settings scopes and update ZOHO_REFRESH_TOKEN in .env.

Usage:
  cd tools/zoho
  ./venv/bin/python provision_pipelines.py              # create missing pipelines only
  ./venv/bin/python provision_pipelines.py --sync       # create missing + update existing from seed
  ./venv/bin/python provision_pipelines.py --dry-run    # show plan only
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import requests

from zoho_tokens import auth_headers, get_access_token_and_domain

API_VER = "v8"
SCRIPT_DIR = Path(__file__).resolve().parent
SEED_PATH = SCRIPT_DIR / "pipelines_seed.json"


def _norm(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def _crm(session: requests.Session, api_domain: str, method: str, path: str, **kwargs):
    url = f"{api_domain.rstrip('/')}/crm/{API_VER}{path}"
    return session.request(method, url, timeout=90, **kwargs)


def _pick_deals_layout_id(layouts_payload: dict) -> str:
    layouts = layouts_payload.get("layouts") or []
    if not layouts:
        raise RuntimeError("No Deals layouts returned. Check module name and permissions.")
    for preferred in ("Standard",):
        for lo in layouts:
            if lo.get("status") == "active" and lo.get("name") == preferred:
                return str(lo["id"])
    for lo in layouts:
        if lo.get("status") == "active":
            return str(lo["id"])
    return str(layouts[0]["id"])


def _stage_lookup_from_pipelines(pipeline_payload: dict) -> dict[str, str]:
    """Map normalized display/actual label -> stage option id."""
    out: dict[str, str] = {}
    for pipe in pipeline_payload.get("pipeline") or []:
        for m in pipe.get("maps") or []:
            sid = str(m.get("id") or "")
            if not sid:
                continue
            for key in (m.get("display_value"), m.get("actual_value")):
                if key:
                    out[_norm(str(key))] = sid
    return out


def _stage_lookup_from_fields(fields_payload: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    fields = fields_payload.get("fields") or []
    for f in fields:
        if f.get("api_name") != "Stage":
            continue
        for opt in f.get("pick_list_values") or []:
            sid = str(opt.get("id") or "")
            display = opt.get("display_value") or opt.get("actual_value")
            if not sid or not display:
                continue
            out[_norm(str(display))] = sid
            if opt.get("actual_value"):
                out[_norm(str(opt["actual_value"]))] = sid
        break
    return out


def _get_stage_lookup(session: requests.Session, api_domain: str, layout_id: str) -> dict[str, str]:
    r = _crm(
        session,
        api_domain,
        "GET",
        f"/settings/pipeline?layout_id={layout_id}",
        headers=session.headers,
    )
    if r.status_code == 204:
        lookup: dict[str, str] = {}
    elif r.ok:
        lookup = _stage_lookup_from_pipelines(r.json())
    else:
        lookup = {}

    if len(lookup) < 3:
        r2 = _crm(
            session,
            api_domain,
            "GET",
            "/settings/fields?module=Deals",
            headers=session.headers,
        )
        if r2.ok:
            alt = _stage_lookup_from_fields(r2.json())
            for k, v in alt.items():
                lookup.setdefault(k, v)
        elif not r.ok:
            raise RuntimeError(
                f"Could not load pipelines (HTTP {r.status_code}) or fields (HTTP {r2.status_code}). "
                f"{r.text[:500]} / {r2.text[:500]}"
            )
    if not lookup:
        raise RuntimeError(
            "Could not resolve Deal Stage picklist IDs. "
            "Confirm Deals module and Stage field exist; token needs settings scopes."
        )
    return lookup


def _list_pipeline_names(pipeline_payload: dict) -> set[str]:
    names = set()
    for pipe in pipeline_payload.get("pipeline") or []:
        dv = pipe.get("display_value")
        if dv:
            names.add(str(dv).strip())
    return names


def _pipeline_id_by_name(pipeline_payload: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for pipe in pipeline_payload.get("pipeline") or []:
        dv = pipe.get("display_value")
        pid = pipe.get("id")
        if dv and pid:
            out[str(dv).strip()] = str(pid)
    return out


def _response_json(resp: requests.Response) -> dict | None:
    if resp.status_code == 204:
        return None
    text = (resp.text or "").strip()
    if not text:
        return None
    try:
        return resp.json()
    except json.JSONDecodeError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision Zoho CRM pipelines from pipelines_seed.json")
    parser.add_argument("--dry-run", action="store_true", help="Print actions only; no POST/PUT")
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Update pipelines that already exist (same display name) to match seed stages",
    )
    parser.add_argument(
        "--seed",
        type=Path,
        default=SEED_PATH,
        help=f"Path to seed JSON (default: {SEED_PATH})",
    )
    args = parser.parse_args()

    seed_path: Path = args.seed
    if not seed_path.is_file():
        print(f"Seed file not found: {seed_path}", file=sys.stderr)
        return 1

    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    pipelines_cfg = seed.get("pipelines") or []
    if not pipelines_cfg:
        print("No pipelines in seed file.", file=sys.stderr)
        return 1

    access, api_domain = get_access_token_and_domain()
    session = requests.Session()
    session.headers.update(auth_headers(access))
    session.headers["Content-Type"] = "application/json"

    r_layouts = _crm(session, api_domain, "GET", "/settings/layouts?module=Deals", headers=session.headers)
    if not r_layouts.ok:
        print(
            f"Layouts API failed HTTP {r_layouts.status_code}. "
            "Add ZohoCRM.settings.layouts.READ (or ZohoCRM.settings.ALL) and create a new refresh token.\n"
            f"{r_layouts.text[:1500]}",
            file=sys.stderr,
        )
        return 1

    layout_id = _pick_deals_layout_id(r_layouts.json())
    print(f"Using Deals layout_id={layout_id} ({api_domain})")

    lookup = _get_stage_lookup(session, api_domain, layout_id)
    print(f"Resolved {len(lookup)} Stage picklist key(s) from CRM metadata.")

    r_existing = _crm(
        session,
        api_domain,
        "GET",
        f"/settings/pipeline?layout_id={layout_id}",
        headers=session.headers,
    )
    existing_names: set[str] = set()
    existing_data = _response_json(r_existing)
    if existing_data is not None:
        existing_names = _list_pipeline_names(existing_data)
    elif r_existing.ok:
        print(
            f"Note: list pipelines HTTP {r_existing.status_code} but body was not JSON; "
            f"continuing without skip-if-exists. Snippet: {r_existing.text[:400]!r}",
            file=sys.stderr,
        )
    elif r_existing.status_code != 204:
        print(f"Warning: could not list pipelines HTTP {r_existing.status_code}", file=sys.stderr)

    pipeline_ids = _pipeline_id_by_name(existing_data or {})

    if args.sync and not pipeline_ids and not (existing_data and existing_data.get("pipeline")):
        print(
            "--sync needs a list of existing pipelines from Zoho; got none. "
            "Create pipelines once without --sync, then use --sync to update stages.",
            file=sys.stderr,
        )
        return 1

    missing_labels: list[str] = []
    body_pipelines: list[dict] = []

    for p in pipelines_cfg:
        name = str(p.get("display_value", "")).strip()
        stages = p.get("stages") or []
        if not name or not stages:
            print(f"Skip invalid entry: {p}", file=sys.stderr)
            continue
        maps = []
        for i, label in enumerate(stages, start=1):
            lid = lookup.get(_norm(str(label)))
            if not lid:
                missing_labels.append(f"{name}: '{label}'")
            else:
                maps.append({"sequence_number": i, "id": lid, "display_value": str(label)})
        body_pipelines.append(
            {
                "display_value": name,
                "default": bool(p.get("default", False)),
                "maps": maps,
            }
        )

    if missing_labels:
        print(
            "These stage labels are not in your org's Stage picklist (no ID match). "
            "Add them in Zoho (Setup → Customization → Modules and Fields → Deals → Stage) "
            "or edit pipelines_seed.json to use your exact labels.\n",
            file=sys.stderr,
        )
        for m in missing_labels:
            print(f"  - {m}", file=sys.stderr)
        return 2

    created = 0
    updated = 0
    skipped = 0

    for spec in body_pipelines:
        name = spec["display_value"]
        pid = pipeline_ids.get(name)

        if pid and args.sync:
            for m in spec["maps"]:
                m.setdefault("actual_value", m["display_value"])
            payload = {"pipeline": [spec]}
            print(f"Update pipeline: {name} ({len(spec['maps'])} stages) id={pid}")
            if args.dry_run:
                updated += 1
                continue
            r_put = _crm(
                session,
                api_domain,
                "PUT",
                f"/settings/pipeline/{pid}?layout_id={layout_id}",
                headers=session.headers,
                data=json.dumps(payload),
            )
            if not r_put.ok:
                print(f"PUT failed HTTP {r_put.status_code}: {r_put.text[:2000]}", file=sys.stderr)
                return 1
            try:
                print(json.dumps(r_put.json(), indent=2)[:2000])
            except json.JSONDecodeError:
                print(r_put.text[:2000])
            updated += 1
            continue

        if pid and not args.sync:
            print(f"Skip (already exists, use --sync to update): {name}")
            skipped += 1
            continue

        payload = {"pipeline": [spec]}
        print(f"Create pipeline: {name} ({len(spec['maps'])} stages)")
        if args.dry_run:
            created += 1
            continue
        r_post = _crm(
            session,
            api_domain,
            "POST",
            f"/settings/pipeline?layout_id={layout_id}",
            headers=session.headers,
            data=json.dumps(payload),
        )
        if not r_post.ok:
            print(f"POST failed HTTP {r_post.status_code}: {r_post.text[:2000]}", file=sys.stderr)
            try:
                err = r_post.json()
                for item in err.get("pipeline") or []:
                    if item.get("code") == "PIPELINE_LIMIT_EXCEEDED":
                        print(
                            "\nZoho rejected a new pipeline: pipeline limit for this org/edition. "
                            "Options: remove an unused pipeline in Zoho (Setup → Pipelines), "
                            "upgrade edition, or use a Deal Type field with fewer pipelines.",
                            file=sys.stderr,
                        )
                        break
            except json.JSONDecodeError:
                pass
            return 1
        try:
            print(json.dumps(r_post.json(), indent=2)[:2000])
        except json.JSONDecodeError:
            print(r_post.text[:2000])
        created += 1

    print(f"\nDone. created={created} updated={updated} skipped={skipped} dry_run={args.dry_run} sync={args.sync}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
