#!/usr/bin/env python3
"""
Provision the Deals + Quotes sales process agreed in docs/zoho/handoffs/AGENT-HANDOFF-DEALS-BLUEPRINT-WORKFLOWS.md.

This script is intentionally idempotent:
  - creates missing Deals / Quotes custom fields;
  - places fields on Standard layouts, creating sections where the Layout API allows it;
  - creates reusable workflow task actions;
  - creates workflow rules for stage follow-ups, quote rollup, owner guard, stale deals, and manager notification;
  - attempts Deluge custom function creation/lookup and reports any API-only gap honestly.
  - Developer Hub functions appear under GET /crm/v8/settings/functions; workflow rules still need the
    automation wrapper id (POST /settings/automation/functions with function.id = catalog id).

Blueprint definition creation is probed and documented, but Zoho CRM v8 public docs expose record
blueprint execution only, not settings blueprint definition creation.

Usage:
  cd tools/zoho
  ./venv/bin/python provision_deals_quotes_process.py --dry-run
  ./venv/bin/python provision_deals_quotes_process.py
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import requests

from zoho_tokens import auth_headers, get_access_token_and_domain

API_VER = "v8"
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DELUGE_DIR = REPO_ROOT / "artifacts" / "zoho" / "deluge"

DEALS = "Deals"
QUOTES = "Quotes"
LEADS = "Leads"
TASKS = "Tasks"

STAGES = [
    "Qualification",
    "Needs Analysis",
    "Proposal / Quote",
    "Negotiation",
    "Closed Won",
    "Closed Lost",
]

BUDGET_VALUES = [
    "Unknown",
    "Rough range",
    "Firm",
    "Financing needed",
    "Tender",
]

LOST_REASON_VALUES = [
    "Lost to competitor / bought elsewhere",
    "Price",
    "Timing",
    "Budget",
    "No decision",
    "Project paused",
    "Tender lost but future opportunities",
]

DISCOVERY_TASK_DESCRIPTION = "\n".join(
    [
        "Complete these discovery fields while the Deal is in Needs Analysis:",
        "- Discovery summary (Discovery_summary)",
        "- Current machines / setup (Current_machines_setup)",
        "- Applications (Applications)",
        "- Budget / financing status (Budget_financing_status)",
        "Budget / financing status must be selected from the picklist, not entered as prose.",
        "Proposal / Quote is blocked until these fields are complete.",
    ]
)

DEAL_FIELD_SPECS = [
    {"field_label": "Discovery summary", "data_type": "textarea", "textarea": {"type": "large"}},
    {"field_label": "Current machines / setup", "data_type": "textarea", "textarea": {"type": "large"}},
    {"field_label": "Applications", "data_type": "textarea", "textarea": {"type": "large"}},
    {
        "field_label": "Budget / financing status",
        "data_type": "picklist",
        "pick_list_values": [
            {"display_value": v, "actual_value": v.replace(" ", "_").replace("/", "_")}
            for v in BUDGET_VALUES
        ],
        "pick_list_values_sorted_lexically": False,
    },
    {"field_label": "Any quote shared with customer", "data_type": "boolean"},
    {"field_label": "Won / handoff notes", "data_type": "textarea", "textarea": {"type": "large"}},
    {"field_label": "Next try / follow-up date", "data_type": "date"},
]

QUOTE_FIELD_SPECS = [
    {"field_label": "Quote shared with customer", "data_type": "boolean"},
]

FUNCTIONS = [
    {
        "name": "quote_recompute_deal_shared",
        "module": QUOTES,
        "file": DELUGE_DIR / "quote_recompute_deal_shared.deluge",
    },
    {
        "name": "quote_shared_owner_guard",
        "module": QUOTES,
        "file": DELUGE_DIR / "quote_shared_owner_guard.deluge",
    },
    {
        "name": "deal_stage_gate_guard",
        "module": DEALS,
        "file": DELUGE_DIR / "deal_stage_gate_guard.deluge",
    },
]


def _crm(
    session: requests.Session,
    api_domain: str,
    method: str,
    path: str,
    **kwargs: Any,
) -> requests.Response:
    url = f"{api_domain.rstrip('/')}/crm/{API_VER}{path}"
    return session.request(method, url, timeout=120, **kwargs)


def _crm_version(
    session: requests.Session,
    api_domain: str,
    version: str,
    method: str,
    path: str,
    **kwargs: Any,
) -> requests.Response:
    url = f"{api_domain.rstrip('/')}/crm/{version}{path}"
    return session.request(method, url, timeout=120, **kwargs)


def _token_retry() -> tuple[str, str]:
    delays = (2, 10, 45, 120, 300)
    last: Exception | None = None
    for delay in delays:
        try:
            return get_access_token_and_domain()
        except RuntimeError as exc:
            last = exc
            text = str(exc).lower()
            if "too many requests" in text or "400" in text:
                print(f"  Token refresh rate-limited; waiting {delay}s...", file=sys.stderr)
                time.sleep(delay)
                continue
            raise
    assert last is not None
    raise last


def _module_map(session: requests.Session, api_domain: str) -> dict[str, dict[str, Any]]:
    r = _crm(session, api_domain, "GET", "/settings/modules")
    if not r.ok:
        raise RuntimeError(f"GET modules HTTP {r.status_code}: {r.text[:2000]}")
    return {
        str(m["api_name"]): m
        for m in r.json().get("modules") or []
        if m.get("api_name")
    }


def _get_fields(
    session: requests.Session,
    api_domain: str,
    module: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    page = 1
    while True:
        r = _crm(
            session,
            api_domain,
            "GET",
            "/settings/fields",
            params={"module": module, "type": "all", "per_page": 200, "page": page},
        )
        if not r.ok:
            raise RuntimeError(f"GET fields {module} HTTP {r.status_code}: {r.text[:2000]}")
        payload = r.json()
        out.extend(payload.get("fields") or [])
        if not (payload.get("info") or {}).get("more_records"):
            return out
        page += 1


def _by_api(fields: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(f["api_name"]): f for f in fields if f.get("api_name")}


def _by_label(fields: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(f["field_label"]).strip().casefold(): f
        for f in fields
        if f.get("field_label")
    }


def _field_by_label(fields: list[dict[str, Any]], label: str) -> dict[str, Any] | None:
    return _by_label(fields).get(label.strip().casefold())


def _api_name_guess(label: str) -> str:
    guessed = re.sub(r"[^0-9A-Za-z]+", "_", label.strip()).strip("_")
    return guessed[:100] if guessed else "Custom_Field"


def _add_dry_run_field(
    field_map: dict[str, dict[str, Any]],
    existing_fields: list[dict[str, Any]],
    module: str,
    label: str,
    data_type: str,
) -> None:
    if _field_by_label(existing_fields, label):
        return
    api_name = _api_name_guess(label)
    field_map.setdefault(
        api_name,
        {
            "id": f"DRYRUN_{module}_{api_name}",
            "api_name": api_name,
            "field_label": label,
            "data_type": data_type,
        },
    )


def _post_field(
    session: requests.Session,
    api_domain: str,
    module: str,
    field_def: dict[str, Any],
    dry_run: bool,
) -> str | None:
    print(f"  POST field {module}.{field_def['field_label']!r} ({field_def['data_type']})")
    if dry_run:
        return "dry_run"
    r = _crm(
        session,
        api_domain,
        "POST",
        "/settings/fields",
        params={"module": module},
        json={"fields": [field_def]},
    )
    if not r.ok:
        print(f"  HTTP {r.status_code}: {r.text[:4000]}", file=sys.stderr)
        return None
    print(json.dumps(r.json(), indent=2)[:2500])
    for item in r.json().get("fields") or []:
        fid = (item.get("details") or {}).get("id") or item.get("id")
        if item.get("code") == "SUCCESS" and fid:
            return str(fid)
    return None


def _merge_picklist_options(
    session: requests.Session,
    api_domain: str,
    module: str,
    field: dict[str, Any],
    desired_labels: list[str],
    dry_run: bool,
) -> list[str]:
    existing = {
        str(o.get("display_value") or "").strip()
        for o in field.get("pick_list_values") or []
        if str(o.get("display_value") or "").strip() not in ("", "-None-")
    }
    to_add = [x for x in desired_labels if x not in existing]
    if not to_add:
        return []
    # v8 update docs add new picklist options by sending only the new options.
    # Sending the full merged list can return SUCCESS while leaving the options unchanged.
    new_options = [
        {"display_value": x, "actual_value": x.replace(" ", "_").replace("/", "_")}
        for x in to_add
    ]
    fid = str(field["id"])
    print(f"  PATCH picklist {module}.{field.get('api_name')}: add {to_add}")
    if dry_run:
        return []
    r = _crm(
        session,
        api_domain,
        "PATCH",
        f"/settings/fields/{fid}",
        params={"module": module},
        json={"fields": [{"id": fid, "pick_list_values": new_options}]},
    )
    if not r.ok:
        print(f"  HTTP {r.status_code}: {r.text[:3000]}", file=sys.stderr)
        return to_add
    print(json.dumps(r.json(), indent=2)[:2000])
    refreshed = _get_fields(session, api_domain, module)
    ref_field = _field_by_label(refreshed, str(field.get("field_label") or ""))
    if not ref_field:
        return to_add
    refreshed_values = {
        str(o.get("display_value") or "").strip()
        for o in ref_field.get("pick_list_values") or []
    }
    still_missing = [x for x in desired_labels if x not in refreshed_values]
    if still_missing:
        print(
            f"  WARNING: Zoho returned SUCCESS but {module}.{field.get('api_name')} still lacks: {still_missing}",
            file=sys.stderr,
        )
    return still_missing


def _ensure_fields(
    session: requests.Session,
    api_domain: str,
    modules: dict[str, dict[str, Any]],
    dry_run: bool,
) -> tuple[dict[str, dict[str, dict[str, Any]]], list[str]]:
    print("\n== Fields ==")
    created: dict[tuple[str, str], str] = {}
    for module, specs in ((DEALS, DEAL_FIELD_SPECS), (QUOTES, QUOTE_FIELD_SPECS)):
        fields = _get_fields(session, api_domain, module)
        labels = _by_label(fields)
        for spec in specs:
            label = spec["field_label"]
            if label.strip().casefold() in labels:
                f = labels[label.strip().casefold()]
                print(f"  Skip {module}.{label!r}: exists api_name={f.get('api_name')} id={f.get('id')}")
                continue
            fid = _post_field(session, api_domain, module, spec, dry_run)
            if fid:
                created[(module, label)] = fid

    deal_fields = _get_fields(session, api_domain, DEALS)
    if not _field_by_label(deal_fields, "Primary Quote"):
        quotes_mod = modules[QUOTES]
        primary_spec = {
            "field_label": "Primary Quote",
            "data_type": "lookup",
            "lookup": {
                "module": {"api_name": QUOTES, "id": str(quotes_mod["id"])},
                "display_label": "Primary Deal",
            },
        }
        fid = _post_field(session, api_domain, DEALS, primary_spec, dry_run)
        if fid:
            created[(DEALS, "Primary Quote")] = fid
    else:
        f = _field_by_label(deal_fields, "Primary Quote")
        print(f"  Skip Deals.'Primary Quote': exists api_name={f.get('api_name')} id={f.get('id')}")

    deal_fields = _get_fields(session, api_domain, DEALS)
    lost = _field_by_label(deal_fields, "Lost Reason")
    gaps: list[str] = []
    if lost:
        missing_lost = _merge_picklist_options(session, api_domain, DEALS, lost, LOST_REASON_VALUES, dry_run)
        if missing_lost:
            gaps.append(
                "Deals Lost Reason picklist did not accept these API-added values despite SUCCESS responses: "
                + ", ".join(missing_lost)
            )
    else:
        print("  Warning: Deals Lost Reason field not found; run provision_phase2_fields.py first.", file=sys.stderr)

    deal_fields_final = _get_fields(session, api_domain, DEALS)
    quote_fields_final = _get_fields(session, api_domain, QUOTES)
    deal_map = _by_api(deal_fields_final)
    quote_map = _by_api(quote_fields_final)
    if dry_run:
        for spec in DEAL_FIELD_SPECS:
            _add_dry_run_field(
                deal_map,
                deal_fields_final,
                DEALS,
                str(spec["field_label"]),
                str(spec["data_type"]),
            )
        _add_dry_run_field(deal_map, deal_fields_final, DEALS, "Primary Quote", "lookup")
        for spec in QUOTE_FIELD_SPECS:
            _add_dry_run_field(
                quote_map,
                quote_fields_final,
                QUOTES,
                str(spec["field_label"]),
                str(spec["data_type"]),
            )
    return {DEALS: deal_map, QUOTES: quote_map}, gaps


def _standard_layout_id(session: requests.Session, api_domain: str, module: str) -> str:
    r = _crm(session, api_domain, "GET", "/settings/layouts", params={"module": module})
    if not r.ok:
        raise RuntimeError(f"GET layouts {module} HTTP {r.status_code}: {r.text[:2000]}")
    layouts = r.json().get("layouts") or []
    for layout in layouts:
        if layout.get("status") == "active" and layout.get("name") == "Standard":
            return str(layout["id"])
    for layout in layouts:
        if layout.get("status") == "active":
            return str(layout["id"])
    raise RuntimeError(f"No active {module} layout")


def _get_layout(session: requests.Session, api_domain: str, module: str, layout_id: str) -> dict[str, Any]:
    r = _crm(session, api_domain, "GET", f"/settings/layouts/{layout_id}", params={"module": module})
    if not r.ok:
        raise RuntimeError(f"GET layout {module}/{layout_id} HTTP {r.status_code}: {r.text[:2000]}")
    layouts = r.json().get("layouts") or []
    if not layouts:
        raise RuntimeError(f"Empty layout response for {module}/{layout_id}")
    return layouts[0]


def _find_section(layout: dict[str, Any], name: str) -> dict[str, Any] | None:
    wanted = name.strip().casefold()
    for sec in layout.get("sections") or []:
        sec_name = str(sec.get("name") or sec.get("display_label") or "").strip().casefold()
        if sec_name == wanted:
            return sec
    for sec in layout.get("sections") or []:
        sec_name = str(sec.get("name") or sec.get("display_label") or "").strip().casefold()
        if wanted in sec_name:
            return sec
    return None


def _field_on_layout(layout: dict[str, Any], field_id: str) -> str | None:
    for sec in layout.get("sections") or []:
        for fld in sec.get("fields") or []:
            if str(fld.get("id")) == str(field_id):
                return str(sec.get("name") or sec.get("display_label") or sec.get("id"))
    return None


def _ensure_section(
    session: requests.Session,
    api_domain: str,
    module: str,
    layout_id: str,
    section_name: str,
    dry_run: bool,
) -> str | None:
    layout = _get_layout(session, api_domain, module, layout_id)
    sec = _find_section(layout, section_name)
    if sec and sec.get("id"):
        return str(sec["id"])
    print(f"  PATCH layout {module}/{layout_id}: create section {section_name!r}")
    if dry_run:
        return "dry_run_section"
    r = _crm(
        session,
        api_domain,
        "PATCH",
        f"/settings/layouts/{layout_id}",
        params={"module": module},
        json={"layouts": [{"sections": [{"display_label": section_name}]}]},
    )
    if not r.ok:
        print(f"  Section create failed HTTP {r.status_code}: {r.text[:2500]}", file=sys.stderr)
        return None
    layout = _get_layout(session, api_domain, module, layout_id)
    sec = _find_section(layout, section_name)
    return str(sec["id"]) if sec and sec.get("id") else None


def _first_editable_section(layout: dict[str, Any]) -> str | None:
    for sec in layout.get("sections") or []:
        if sec.get("id") and sec.get("fields") is not None:
            return str(sec["id"])
    return None


def _add_field_to_layout(
    session: requests.Session,
    api_domain: str,
    module: str,
    layout_id: str,
    section_id: str,
    field: dict[str, Any],
    dry_run: bool,
    *,
    read_only: bool = False,
) -> bool:
    field_id = str(field["id"])
    layout = _get_layout(session, api_domain, module, layout_id)
    existing = _field_on_layout(layout, field_id)
    if existing:
        print(f"  Skip layout: {module}.{field.get('field_label')} already in {existing!r}")
        return True
    row: dict[str, Any] = {"id": field_id}
    if read_only:
        row["read_only"] = True
    patch = {"layouts": [{"sections": [{"id": str(section_id), "fields": [row]}]}]}
    print(f"  PATCH layout {module}/{layout_id}: add {field.get('field_label')!r} to section {section_id}")
    if dry_run:
        return True
    r = _crm(
        session,
        api_domain,
        "PATCH",
        f"/settings/layouts/{layout_id}",
        params={"module": module},
        json=patch,
    )
    if not r.ok and read_only:
        row.pop("read_only", None)
        r = _crm(
            session,
            api_domain,
            "PATCH",
            f"/settings/layouts/{layout_id}",
            params={"module": module},
            json=patch,
        )
    if not r.ok:
        print(f"  HTTP {r.status_code}: {r.text[:2500]}", file=sys.stderr)
        return False
    return True


def _ensure_layouts(
    session: requests.Session,
    api_domain: str,
    fields: dict[str, dict[str, dict[str, Any]]],
    dry_run: bool,
) -> bool:
    print("\n== Layouts ==")
    ok = True
    deal_layout_id = _standard_layout_id(session, api_domain, DEALS)
    quote_layout_id = _standard_layout_id(session, api_domain, QUOTES)
    print(f"  Deals Standard layout_id={deal_layout_id}")
    print(f"  Quotes Standard layout_id={quote_layout_id}")

    discovery_sec = _ensure_section(session, api_domain, DEALS, deal_layout_id, "Discovery", dry_run)
    quote_sec = _ensure_section(session, api_domain, DEALS, deal_layout_id, "Quote Management", dry_run)
    close_sec = _ensure_section(session, api_domain, DEALS, deal_layout_id, "Close Details", dry_run)
    layout = _get_layout(session, api_domain, DEALS, deal_layout_id)
    fallback_sec = _first_editable_section(layout)
    discovery_sec = discovery_sec or fallback_sec
    quote_sec = quote_sec or fallback_sec
    close_sec = close_sec or fallback_sec
    if not discovery_sec or not quote_sec or not close_sec:
        print("  No Deals section available for field placement.", file=sys.stderr)
        return False

    deal_by_label = _by_label(list(fields[DEALS].values()))
    for label in (
        "Discovery summary",
        "Current machines / setup",
        "Applications",
        "Budget / financing status",
    ):
        ok = _add_field_to_layout(session, api_domain, DEALS, deal_layout_id, discovery_sec, deal_by_label[label.casefold()], dry_run) and ok
    for label, ro in (
        ("Primary Quote", False),
        ("Any quote shared with customer", True),
    ):
        ok = _add_field_to_layout(session, api_domain, DEALS, deal_layout_id, quote_sec, deal_by_label[label.casefold()], dry_run, read_only=ro) and ok
    for label in ("Won / handoff notes", "Next try / follow-up date"):
        ok = _add_field_to_layout(session, api_domain, DEALS, deal_layout_id, close_sec, deal_by_label[label.casefold()], dry_run) and ok

    quote_layout = _get_layout(session, api_domain, QUOTES, quote_layout_id)
    qsec = _find_section(quote_layout, "Quote Information")
    qsec_id = str(qsec["id"]) if qsec and qsec.get("id") else _first_editable_section(quote_layout)
    quote_by_label = _by_label(list(fields[QUOTES].values()))
    ok = _add_field_to_layout(
        session,
        api_domain,
        QUOTES,
        quote_layout_id,
        str(qsec_id),
        quote_by_label["quote shared with customer"],
        dry_run,
    ) and ok
    return ok


def _strip_deluge_comments(src: str) -> str:
    out: list[str] = []
    for line in src.splitlines():
        if line.strip().startswith("//"):
            continue
        out.append(line)
    return "\n".join(out).strip() + "\n"


def _normalize_deluge_source(src: str) -> str:
    return re.sub(r"\s+", "", src or "").strip()


def _function_argument(spec_name: str) -> dict[str, str]:
    if spec_name == "deal_stage_gate_guard":
        return {"name": "dealId", "type": "String"}
    return {"name": "quoteId", "type": "String"}


def _norm_function_label(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _crm_function_row_matches_spec(fn: dict[str, Any], spec_name: str) -> bool:
    """Match automation.spec name (underscore style) to api_name, display name, etc."""
    spec = (spec_name or "").strip()
    if not spec:
        return False
    candidates: list[str] = []
    for key in ("api_name", "name", "display_name", "Display_Name"):
        v = fn.get(key)
        if v is not None and str(v).strip():
            candidates.append(str(v).strip())
    for c in candidates:
        if c == spec:
            return True
        if _norm_function_label(c) == _norm_function_label(spec):
            return True
        if _norm_function_label(c).replace(" ", "_") == _norm_function_label(spec).replace(" ", "_"):
            return True
    return False


def _find_settings_functions_catalog_id(
    session: requests.Session, api_domain: str, spec_name: str
) -> str | None:
    """
    Developer Hub functions (and the canonical function catalog) are listed under
    GET /crm/v8/settings/functions. Older docs and scripts used only
    /settings/automation/functions, which returns wrapper rows and often omits Hub-created functions.
    """
    page = 1
    while True:
        r = _crm(
            session,
            api_domain,
            "GET",
            "/settings/functions",
            params={"page": page, "per_page": 200},
        )
        if not r.ok:
            print(f"  GET /settings/functions HTTP {r.status_code}: {r.text[:1000]}", file=sys.stderr)
            return None
        if r.status_code == 204 or not (r.text or "").strip():
            return None
        data = r.json()
        for fn in data.get("functions") or []:
            if _crm_function_row_matches_spec(fn, spec_name) and fn.get("id"):
                return str(fn["id"])
        if not (data.get("info") or {}).get("more_records"):
            return None
        page += 1


def _get_settings_function_detail(
    session: requests.Session,
    api_domain: str,
    identifier: str,
) -> tuple[dict[str, Any] | None, str | None]:
    r = _crm(session, api_domain, "GET", f"/settings/functions/{identifier}")
    if not r.ok:
        return None, f"GET /settings/functions/{identifier} HTTP {r.status_code}: {r.text[:1000]}"
    if r.status_code == 204 or not (r.text or "").strip():
        return None, f"GET /settings/functions/{identifier} HTTP 204/empty"
    return (r.json().get("functions") or [None])[0], None


def _get_settings_function_code(
    session: requests.Session,
    api_domain: str,
    identifier: str,
) -> tuple[str | None, str | None]:
    r = _crm(session, api_domain, "GET", f"/settings/functions/{identifier}/code")
    if not r.ok:
        return None, f"GET /settings/functions/{identifier}/code HTTP {r.status_code}: {r.text[:1000]}"
    return r.text or "", None


def _function_update_metadata(detail: dict[str, Any] | None, spec: dict[str, Any]) -> dict[str, Any]:
    name = str(spec["name"])
    detail = detail or {}
    metadata: dict[str, Any] = {
        "name": detail.get("name") or name.replace("_", " "),
        "api_name": detail.get("api_name") or name,
        "return_type": detail.get("return_type") or "void",
        "runtime": detail.get("runtime") or "Deluge 1.0",
        "category": detail.get("category") or "Automation",
        "arguments": detail.get("arguments") or [_function_argument(name)],
    }
    if detail.get("description"):
        metadata["description"] = detail["description"]
    return metadata


def _put_settings_function_code(
    session: requests.Session,
    api_domain: str,
    spec: dict[str, Any],
    metadata: dict[str, Any],
    source: str,
) -> requests.Response:
    """
    Zoho's v8 function update endpoint expects multipart form data:
    a JSON metadata part and a Deluge source file with a .ds extension.
    """
    old_content_type = session.headers.pop("Content-Type", None)
    try:
        return _crm(
            session,
            api_domain,
            "PUT",
            f"/settings/functions/{spec['name']}",
            data={"metadata": json.dumps(metadata)},
            files={"code": (f"{spec['name']}.ds", source, "text/plain")},
        )
    finally:
        if old_content_type is not None:
            session.headers["Content-Type"] = old_content_type


def _post_settings_function_code(
    session: requests.Session,
    api_domain: str,
    spec: dict[str, Any],
    metadata: dict[str, Any],
    source: str,
) -> requests.Response:
    old_content_type = session.headers.pop("Content-Type", None)
    try:
        return _crm(
            session,
            api_domain,
            "POST",
            "/settings/functions",
            data={"metadata": json.dumps(metadata)},
            files={"code": (f"{spec['name']}.ds", source, "text/plain")},
        )
    finally:
        if old_content_type is not None:
            session.headers["Content-Type"] = old_content_type


def _publish_settings_function(
    session: requests.Session,
    api_domain: str,
    name: str,
) -> str | None:
    r = _crm(session, api_domain, "POST", f"/settings/functions/{name}/actions/publish")
    if r.ok:
        return None
    return f"POST /settings/functions/{name}/actions/publish HTTP {r.status_code}: {r.text[:1000]}"


def _create_settings_function(
    session: requests.Session,
    api_domain: str,
    spec: dict[str, Any],
) -> tuple[str | None, list[str]]:
    name = str(spec["name"])
    path = Path(spec["file"])
    if not path.is_file():
        return None, [f"Custom function {name} source file is missing: {path}"]
    desired = path.read_text(encoding="utf-8")
    metadata = _function_update_metadata(None, spec)
    print(f"  POST Developer Hub function {name!r}")
    r = _post_settings_function_code(session, api_domain, spec, metadata, desired)
    if not r.ok:
        msg = f"POST /settings/functions HTTP {r.status_code}: {r.text[:2000]}"
        print(f"  {msg}", file=sys.stderr)
        return None, [f"Custom function {name} catalog create failed via API: {msg}"]
    print(json.dumps(r.json(), indent=2)[:2000])
    catalog_id = _find_settings_functions_catalog_id(session, api_domain, name)
    if not catalog_id:
        return None, [f"Custom function {name} was created but not found in /settings/functions catalog."]
    detail, detail_error = _get_settings_function_detail(session, api_domain, name)
    if detail_error:
        print(f"  {detail_error}", file=sys.stderr)
    if detail and (detail.get("has_draft") or str(detail.get("state") or "").lower() != "active"):
        publish_error = _publish_settings_function(session, api_domain, name)
        if publish_error:
            print(f"  {publish_error}", file=sys.stderr)
            return catalog_id, [f"Custom function {name} publish failed via API: {publish_error}"]
    gaps = _ensure_settings_function_source(session, api_domain, spec, dry_run=False)
    return catalog_id, gaps


def _ensure_settings_function_source(
    session: requests.Session,
    api_domain: str,
    spec: dict[str, Any],
    dry_run: bool,
) -> list[str]:
    name = str(spec["name"])
    path = Path(spec["file"])
    if not path.is_file():
        return [f"Custom function {name} source file is missing: {path}"]
    desired = path.read_text(encoding="utf-8")
    detail, detail_error = _get_settings_function_detail(session, api_domain, name)
    current, code_error = _get_settings_function_code(session, api_domain, name)
    if detail_error:
        print(f"  {detail_error}", file=sys.stderr)
    if code_error:
        print(f"  {code_error}", file=sys.stderr)
        return [f"Custom function {name} source could not be read via API: {code_error}"]
    if _normalize_deluge_source(current or "") == _normalize_deluge_source(desired):
        print(f"  Function source ok: {name}")
        return []
    print(f"  Function source drift detected: {name}")
    if dry_run:
        print(f"  [dry-run] Would PUT /settings/functions/{name} with {path.name}")
        return []
    metadata = _function_update_metadata(detail, spec)
    r = _put_settings_function_code(session, api_domain, spec, metadata, desired)
    if not r.ok:
        msg = f"PUT /settings/functions/{name} HTTP {r.status_code}: {r.text[:2000]}"
        print(f"  {msg}", file=sys.stderr)
        return [f"Custom function {name} source update failed via API: {msg}"]
    print(json.dumps(r.json(), indent=2)[:2000])
    refreshed, refresh_error = _get_settings_function_code(session, api_domain, name)
    if refresh_error or _normalize_deluge_source(refreshed or "") != _normalize_deluge_source(desired):
        msg = refresh_error or "refetched source still differs from artifact"
        print(f"  Function source verification failed for {name}: {msg}", file=sys.stderr)
        return [f"Custom function {name} source update could not be verified via API: {msg}"]
    print(f"  Function source repaired: {name}")
    return []


def _find_automation_function_wrapper_id(
    session: requests.Session, api_domain: str, spec_name: str
) -> str | None:
    """Legacy: workflow action id is the outer row id on /settings/automation/functions."""
    page = 1
    while True:
        r = _crm(
            session,
            api_domain,
            "GET",
            "/settings/automation/functions",
            params={"page": page, "per_page": 200},
        )
        if not r.ok:
            print(f"  GET /settings/automation/functions HTTP {r.status_code}: {r.text[:1000]}", file=sys.stderr)
            return None
        if r.status_code == 204 or not (r.text or "").strip():
            return None
        data = r.json()
        for fn in data.get("functions") or []:
            if _crm_function_row_matches_spec(fn, spec_name) and fn.get("id"):
                return str(fn["id"])
        if not (data.get("info") or {}).get("more_records"):
            return None
        page += 1


def _resolve_workflow_functions_action_id(
    session: requests.Session, api_domain: str, catalog_function_id: str
) -> str:
    """
    Workflow instant_actions(type=functions) expect the automation-table id when Zoho created a
    wrapper row; that row's nested function.id matches /settings/functions id. If there is no
    wrapper (typical for Developer Hub-only creates), use the catalog id as returned.
    """
    cid = str(catalog_function_id).strip()
    page = 1
    while True:
        r = _crm(
            session,
            api_domain,
            "GET",
            "/settings/automation/functions",
            params={"page": page, "per_page": 200},
        )
        if not r.ok or r.status_code == 204 or not (r.text or "").strip():
            break
        data = r.json()
        for fn in data.get("functions") or []:
            outer = str(fn.get("id") or "").strip()
            inner = str((fn.get("function") or {}).get("id") or "").strip()
            if outer == cid:
                return outer
            if inner and inner == cid:
                return outer
        if not (data.get("info") or {}).get("more_records"):
            break
        page += 1
    return cid


def _create_automation_wrapper_from_catalog(
    session: requests.Session,
    api_domain: str,
    modules: dict[str, dict[str, Any]],
    spec_name: str,
    module_api_name: str,
    catalog_function_id: str,
) -> str | None:
    """
    Workflow rules accept only action ids from /settings/automation/functions. Developer Hub
    (and /settings/functions) scripts get a usable id by POSTing a thin wrapper row that
    points at the existing catalog function — no raw Deluge body required.
    """
    body = {
        "functions": [
            {
                "name": spec_name,
                "feature_type": "workflow",
                "language": "deluge",
                "module": {
                    "api_name": module_api_name,
                    "id": str(modules[module_api_name]["id"]),
                },
                "function": {"id": str(catalog_function_id)},
            }
        ]
    }
    print(f"  POST automation wrapper for catalog function {spec_name!r} ({module_api_name})")
    r = _crm(session, api_domain, "POST", "/settings/automation/functions", json=body)
    if not r.ok:
        print(f"  POST automation/functions (wrapper) HTTP {r.status_code}: {r.text[:4000]}", file=sys.stderr)
        return None
    for item in r.json().get("functions") or []:
        if item.get("code") == "SUCCESS":
            wid = (item.get("details") or {}).get("id")
            if wid:
                return str(wid)
    return _resolve_workflow_functions_action_id(session, api_domain, catalog_function_id)


def _create_function(
    session: requests.Session,
    api_domain: str,
    modules: dict[str, dict[str, Any]],
    spec: dict[str, Any],
    dry_run: bool,
) -> tuple[str | None, list[str]]:
    name = spec["name"]
    module = spec["module"]
    gaps: list[str] = []
    catalog_id = _find_settings_functions_catalog_id(session, api_domain, name)
    if catalog_id:
        gaps.extend(_ensure_settings_function_source(session, api_domain, spec, dry_run))
        action_id = _resolve_workflow_functions_action_id(session, api_domain, catalog_id)
        if action_id != catalog_id:
            print(f"  Function exists: {name} workflow_action_id={action_id}")
            return action_id, gaps
        if dry_run:
            print(
                f"  [dry-run] Would POST automation wrapper for Developer Hub function "
                f"{name!r} (catalog id={catalog_id})"
            )
            return None, gaps
        action_id = _create_automation_wrapper_from_catalog(
            session, api_domain, modules, name, module, catalog_id
        )
        if action_id:
            print(f"  Linked automation wrapper: {name} workflow_action_id={action_id}")
        return action_id, gaps

    existing_wrap = _find_automation_function_wrapper_id(session, api_domain, name)
    if existing_wrap:
        print(f"  Function exists: {name} workflow_action_id={existing_wrap}")
        return existing_wrap, gaps

    if dry_run:
        print(f"  [dry-run] Would POST Developer Hub function {name!r} from {spec['file']}")
    else:
        catalog_id, create_gaps = _create_settings_function(session, api_domain, spec)
        gaps.extend(create_gaps)
        if catalog_id:
            action_id = _create_automation_wrapper_from_catalog(
                session, api_domain, modules, name, module, catalog_id
            )
            if action_id:
                print(f"  Linked automation wrapper: {name} workflow_action_id={action_id}")
                return action_id, gaps

    path = Path(spec["file"])
    if not path.is_file():
        print(f"  Missing Deluge file: {path}", file=sys.stderr)
        return None, gaps
    module = spec["module"]
    body = {
        "functions": [
            {
                "name": name,
                "module": {"api_name": module, "id": str(modules[module]["id"])},
                "language": "deluge",
                "function": _strip_deluge_comments(path.read_text(encoding="utf-8")),
            }
        ]
    }
    print(f"  POST function {name!r} ({module})")
    if dry_run:
        print(json.dumps(body, indent=2)[:2500])
        return "dry_run", gaps
    r = _crm(session, api_domain, "POST", "/settings/automation/functions", json=body)
    if not r.ok:
        print(f"  POST functions HTTP {r.status_code}: {r.text[:4000]}", file=sys.stderr)
        return None, gaps
    print(json.dumps(r.json(), indent=2)[:2500])
    for item in r.json().get("functions") or []:
        fid = (item.get("details") or {}).get("id") or item.get("id")
        if item.get("code") == "SUCCESS" and fid:
            return str(fid), gaps
    return None, gaps


def _ensure_functions(
    session: requests.Session,
    api_domain: str,
    modules: dict[str, dict[str, Any]],
    dry_run: bool,
) -> tuple[dict[str, str], list[str]]:
    print("\n== Custom Functions ==")
    ids: dict[str, str] = {}
    gaps: list[str] = []
    for spec in FUNCTIONS:
        fid, source_gaps = _create_function(session, api_domain, modules, spec, dry_run)
        gaps.extend(source_gaps)
        if fid:
            ids[spec["name"]] = fid
        else:
            gaps.append(
                f"Custom function {spec['name']} could not be created/found via API; "
                f"Deluge artifact is {spec['file']}"
            )
    return ids, gaps


def _find_automation_task_id(
    session: requests.Session,
    api_domain: str,
    name: str,
    module: str,
) -> str | None:
    page = 1
    while True:
        r = _crm(
            session,
            api_domain,
            "GET",
            "/settings/automation/tasks",
            params={"feature_type": "workflow", "module": module, "per_page": 200, "page": page},
        )
        if not r.ok:
            print(f"  GET automation tasks HTTP {r.status_code}: {r.text[:1000]}", file=sys.stderr)
            return None
        if r.status_code == 204 or not (r.text or "").strip():
            return None
        data = r.json()
        for task in data.get("tasks") or []:
            if str(task.get("name") or "").strip() == name and task.get("id"):
                return str(task["id"])
        if not (data.get("info") or {}).get("more_records"):
            return None
        page += 1


def _task_field(fields: dict[str, dict[str, Any]], api_name: str) -> dict[str, str]:
    field = fields[api_name]
    return {"api_name": api_name, "id": str(field["id"])}


def _task_mapping_static(task_fields: dict[str, dict[str, Any]], api: str, value: Any) -> dict[str, Any]:
    return {"field": _task_field(task_fields, api), "type": "static", "value": value}


def _task_mapping_merge(task_fields: dict[str, dict[str, Any]], api: str, value: str) -> dict[str, Any]:
    return {"field": _task_field(task_fields, api), "type": "merge_field", "value": value}


def _task_mapping_due_offset(task_fields: dict[str, dict[str, Any]], days: int) -> dict[str, Any]:
    return {
        "field": _task_field(task_fields, "Due_Date"),
        "type": "execution_time",
        "value": {
            "period": "days",
            "unit": str(days),
            "trigger_field": "${CURRENTTIME}",
            "sign": "plus",
        },
    }


def _task_field_mappings(
    task_fields: dict[str, dict[str, Any]],
    *,
    subject: str,
    due_days: int | None = None,
    due_merge_field: str | None = None,
    owner_merge_field: str | None = None,
    priority: str = "Normal",
    description: str = "",
) -> list[dict[str, Any]]:
    mappings = [
        _task_mapping_static(task_fields, "Subject", subject),
        _task_mapping_static(task_fields, "Status", "Not Started"),
        _task_mapping_static(task_fields, "Priority", priority),
    ]
    if due_merge_field:
        # Zoho v8 currently rejects merge-field values for Tasks.Due_Date automation mappings
        # in this org. Keep the intent in Description and use an immediate task.
        mappings.append(_task_mapping_due_offset(task_fields, 0))
    elif due_days is not None:
        mappings.append(_task_mapping_due_offset(task_fields, due_days))
    if owner_merge_field:
        # In this org, Zoho's Automation Task API accepts but drops Description and
        # owner merge-field mappings. Use Deluge-created tasks when those details matter.
        pass
    return mappings


def _automation_task_detail(
    session: requests.Session,
    api_domain: str,
    task_id: str,
) -> dict[str, Any] | None:
    r = _crm(session, api_domain, "GET", f"/settings/automation/tasks/{task_id}")
    if not r.ok or r.status_code == 204 or not (r.text or "").strip():
        if not r.ok:
            print(f"  GET automation task {task_id} HTTP {r.status_code}: {r.text[:1000]}", file=sys.stderr)
        return None
    return (r.json().get("tasks") or [None])[0]


def _normalized_task_mapping_signature(mappings: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for mapping in mappings:
        field = mapping.get("field") or {}
        if str(field.get("api_name") or "") == "Description":
            # Zoho preserves/drops Automation Task Description mappings inconsistently.
            # Needs Analysis uses Deluge task creation for the required checklist.
            continue
        value = mapping.get("value")
        if isinstance(value, dict):
            value_text = json.dumps(value, sort_keys=True, separators=(",", ":"))
        elif isinstance(value, list):
            value_text = json.dumps(value, sort_keys=True, separators=(",", ":"))
        else:
            value_text = "" if value is None else str(value)
        out.append((str(field.get("api_name") or ""), str(mapping.get("type") or ""), value_text))
    return sorted(out)


def _update_task_action_if_needed(
    session: requests.Session,
    api_domain: str,
    *,
    task_id: str,
    name: str,
    mappings: list[dict[str, Any]],
    dry_run: bool,
) -> str | None:
    detail = _automation_task_detail(session, api_domain, task_id)
    if detail:
        current = detail.get("field_mappings") or []
        if _normalized_task_mapping_signature(current) == _normalized_task_mapping_signature(mappings):
            print(f"  Automation task current: {name} id={task_id}")
            return None

    body = {"tasks": [{"field_mappings": mappings}]}
    print(f"  PUT automation task {name!r} id={task_id}")
    if dry_run:
        print(json.dumps(body, indent=2)[:3000])
        return None
    r = _crm(session, api_domain, "PUT", f"/settings/automation/tasks/{task_id}", json=body)
    if not r.ok:
        print(f"  PUT automation task HTTP {r.status_code}: {r.text[:4000]}", file=sys.stderr)
        return f"Automation task {name} could not be updated via API: HTTP {r.status_code} {r.text[:1000]}"
    print(json.dumps(r.json(), indent=2)[:2000])
    refreshed = _automation_task_detail(session, api_domain, task_id)
    if refreshed and _normalized_task_mapping_signature(refreshed.get("field_mappings") or []) == _normalized_task_mapping_signature(mappings):
        return None
    return f"Automation task {name} update response was successful but verification did not match desired field mappings."


def _ensure_task_action(
    session: requests.Session,
    api_domain: str,
    modules: dict[str, dict[str, Any]],
    task_fields: dict[str, dict[str, Any]],
    *,
    module: str,
    name: str,
    subject: str,
    due_days: int | None = None,
    due_merge_field: str | None = None,
    owner_merge_field: str | None = None,
    priority: str = "Normal",
    description: str = "",
    dry_run: bool,
) -> tuple[str | None, str | None]:
    existing = _find_automation_task_id(session, api_domain, name, module) or _find_automation_task_id(
        session, api_domain, subject, module
    )
    mappings = _task_field_mappings(
        task_fields,
        subject=subject,
        due_days=due_days,
        due_merge_field=due_merge_field,
        owner_merge_field=owner_merge_field,
        priority=priority,
        description=description,
    )
    if existing:
        gap = _update_task_action_if_needed(
            session,
            api_domain,
            task_id=existing,
            name=name,
            mappings=mappings,
            dry_run=dry_run,
        )
        return existing, gap
    body = {
        "tasks": [
            {
                "name": name,
                "module": {"api_name": module, "id": str(modules[module]["id"])},
                "feature_type": "workflow",
                "field_mappings": mappings,
            }
        ]
    }
    print(f"  POST automation task {name!r}")
    if dry_run:
        print(json.dumps(body, indent=2)[:3000])
        return "dry_run", None
    r = _crm(session, api_domain, "POST", "/settings/automation/tasks", json=body)
    if not r.ok:
        print(f"  POST automation tasks HTTP {r.status_code}: {r.text[:4000]}", file=sys.stderr)
        return None, f"Automation task {name} could not be created via API: HTTP {r.status_code} {r.text[:1000]}"
    print(json.dumps(r.json(), indent=2)[:2000])
    for item in r.json().get("tasks") or []:
        tid = (item.get("details") or {}).get("id") or item.get("id")
        if item.get("code") == "SUCCESS" and tid:
            return str(tid), None
    return None, f"Automation task {name} create response did not include an id."


def _criterion(field: dict[str, Any], comparator: str, value: Any) -> dict[str, Any]:
    return {
        "comparator": comparator,
        "field": {"api_name": field["api_name"], "id": str(field["id"])},
        "type": "value",
        "value": value,
    }


def _and(criteria: list[dict[str, Any]]) -> dict[str, Any]:
    return {"group_operator": "AND", "group": criteria}


def _find_workflow_id(
    session: requests.Session,
    api_domain: str,
    module: str,
    name: str,
) -> str | None:
    filt = json.dumps({"field": {"api_name": "name"}, "comparator": "contains", "value": name})
    r = _crm(
        session,
        api_domain,
        "GET",
        "/settings/automation/workflow_rules",
        params={"module": module, "filter": filt, "per_page": 200},
    )
    if not r.ok:
        print(f"  GET workflow_rules HTTP {r.status_code}: {r.text[:1000]}", file=sys.stderr)
        return None
    if r.status_code == 204 or not (r.text or "").strip():
        return None
    for workflow in r.json().get("workflow_rules") or []:
        if workflow.get("name") == name and workflow.get("id"):
            return str(workflow["id"])
    return None


def _find_field_update_id(
    session: requests.Session,
    api_domain: str,
    module: str,
    name: str,
) -> str | None:
    r = _crm(
        session,
        api_domain,
        "GET",
        "/settings/automation/field_updates",
        params={"module": module, "feature_type": "workflow", "per_page": 200},
    )
    if not r.ok:
        print(f"  GET field_updates HTTP {r.status_code}: {r.text[:1000]}", file=sys.stderr)
        return None
    if r.status_code == 204 or not (r.text or "").strip():
        return None
    for update in r.json().get("field_updates") or []:
        if update.get("name") == name and update.get("id"):
            return str(update["id"])
    return None


def _ensure_stage_rollback_field_update(
    session: requests.Session,
    api_domain: str,
    modules: dict[str, dict[str, Any]],
    deal_fields: dict[str, dict[str, Any]],
    dry_run: bool,
) -> str | None:
    """Shared field update used by native rollback workflows.

    This is the canonical Proposal / Quote gate in the current org because Kanban/API
    stage edits bypass Client Scripts and the workflow function wrapper has no dealId mapping.
    """
    name = "Deal gate rollback to Needs Analysis"
    existing = _find_field_update_id(session, api_domain, DEALS, name)
    if existing:
        print(f"  Field update exists: {name} id={existing}")
        return existing
    body = {
        "field_updates": [
            {
                "name": name,
                "module": {"api_name": DEALS, "id": str(modules[DEALS]["id"])},
                "field": {"api_name": "Stage", "id": str(deal_fields["Stage"]["id"])},
                "type": "static",
                "value": "Needs Analysis",
                "feature_type": "workflow",
            }
        ]
    }
    print(f"  POST field update {name!r}")
    if dry_run:
        print(json.dumps(body, indent=2)[:2500])
        return "dry_run"
    r = _crm(session, api_domain, "POST", "/settings/automation/field_updates", json=body)
    if not r.ok:
        print(f"  POST field_updates HTTP {r.status_code}: {r.text[:4000]}", file=sys.stderr)
        return None
    print(json.dumps(r.json(), indent=2)[:2000])
    for item in r.json().get("field_updates") or []:
        fid = (item.get("details") or {}).get("id") or item.get("id")
        if item.get("code") == "SUCCESS" and fid:
            return str(fid)
    return None


def _create_workflow(
    session: requests.Session,
    api_domain: str,
    module: str,
    body: dict[str, Any],
    dry_run: bool,
) -> str | None:
    name = body["workflow_rules"][0]["name"]
    existing = _find_workflow_id(session, api_domain, module, name)
    if existing:
        # Zoho may reject PUTs to existing workflow criteria with duplicate-condition or
        # condition-limit errors. Only the legacy aggregate guard is updated in place.
        if name != "Deal - stage gate guard":
            print(f"  Workflow exists: {name} id={existing}")
            return existing
        print(f"  PUT workflow {name!r} id={existing}")
        if dry_run:
            print(json.dumps(body, indent=2)[:5000])
            return existing
        r = _crm(session, api_domain, "PUT", f"/settings/automation/workflow_rules/{existing}", json=body)
        if not r.ok:
            print(f"  PUT workflow_rules HTTP {r.status_code}: {r.text[:6000]}", file=sys.stderr)
            return None
        print(json.dumps(r.json(), indent=2)[:2500])
        return existing
    print(f"  POST workflow {name!r}")
    if dry_run:
        print(json.dumps(body, indent=2)[:5000])
        return "dry_run"
    r = _crm(session, api_domain, "POST", "/settings/automation/workflow_rules", json=body)
    if not r.ok:
        print(f"  POST workflow_rules HTTP {r.status_code}: {r.text[:6000]}", file=sys.stderr)
        return None
    print(json.dumps(r.json(), indent=2)[:2500])
    for item in r.json().get("workflow_rules") or []:
        wid = (item.get("details") or {}).get("id") or item.get("id")
        if item.get("code") == "SUCCESS" and wid:
            return str(wid)
    return None


def _workflow_base(
    modules: dict[str, dict[str, Any]],
    module: str,
    name: str,
    description: str,
    execute_when: dict[str, Any],
    actions: list[dict[str, str]],
    criteria: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "workflow_rules": [
            {
                "execute_when": execute_when,
                "module": {"api_name": module, "id": str(modules[module]["id"])},
                "name": name,
                "description": description,
                "status": {"active": True},
                "conditions": [
                    {
                        "sequence_number": 1,
                        "criteria_details": {"criteria": criteria},
                        "instant_actions": {"actions": actions},
                    }
                ],
            }
        ]
    }


def _create_trigger(modules: dict[str, dict[str, Any]], module: str) -> dict[str, Any]:
    return {"type": "create", "details": {"trigger_module": {"api_name": module, "id": str(modules[module]["id"])}}}


def _stage_update_trigger(
    modules: dict[str, dict[str, Any]],
    fields: dict[str, dict[str, Any]],
    stage_value: str,
    *,
    repeat: bool = False,
) -> dict[str, Any]:
    stage = fields["Stage"]
    return {
        "type": "field_update",
        "details": {
            "trigger_module": {"api_name": DEALS, "id": str(modules[DEALS]["id"])},
            "criteria": _criterion(stage, "equal", stage_value),
            "repeat": repeat,
            "match_all": True,
        },
    }


def _field_any_update_trigger(
    modules: dict[str, dict[str, Any]],
    module: str,
    field: dict[str, Any],
    *,
    repeat: bool = False,
) -> dict[str, Any]:
    return {
        "type": "field_update",
        "details": {
            "trigger_module": {"api_name": module, "id": str(modules[module]["id"])},
            "criteria": {
                "comparator": "${ANYVALUE}",
                "field": {"api_name": field["api_name"], "id": str(field["id"])},
                "value": "${ANYVALUE}",
            },
            "repeat": repeat,
            "match_all": True,
        },
    }


def _ensure_workflows(
    session: requests.Session,
    api_domain: str,
    modules: dict[str, dict[str, Any]],
    fields: dict[str, dict[str, dict[str, Any]]],
    function_ids: dict[str, str],
    dry_run: bool,
) -> tuple[bool, list[str]]:
    print("\n== Workflow Task Actions ==")
    task_fields = _by_api(_get_fields(session, api_domain, TASKS))
    required_task_fields = ["Subject", "Due_Date", "Owner", "Status", "Priority", "Description"]
    missing_task_fields = [x for x in required_task_fields if x not in task_fields]
    if missing_task_fields:
        raise RuntimeError(f"Tasks fields missing from metadata: {missing_task_fields}")

    task_ids: dict[str, str] = {}
    gaps: list[str] = []
    task_specs = [
        (LEADS, "Lead - contact same day task", "Contact lead", 0, None, "${!Leads.Owner}", "High", "Contact the new lead and qualify interest."),
        (DEALS, "Deal - schedule discovery task", "Schedule discovery / confirm opportunity", 2, None, "${!Deals.Owner}", "Normal", "Qualification follow-up."),
        (
            DEALS,
            "Deal - complete discovery task",
            "Complete discovery on Deal - Needs Analysis",
            3,
            None,
            "${!Deals.Owner}",
            "Normal",
            DISCOVERY_TASK_DESCRIPTION,
        ),
        (
            DEALS,
            "Deal - proposal quote task",
            "Finalize proposal / quote — create Quote(s); set Primary Quote; follow up",
            3,
            None,
            "${!Deals.Owner}",
            "Normal",
            "Complete official quote(s) in Zoho Quotes, set Primary Quote, then follow up with the customer.",
        ),
        (DEALS, "Deal - negotiation timeline task", "Confirm decision timeline; address objections", 3, None, "${!Deals.Owner}", "Normal", "Negotiation follow-up."),
        (DEALS, "Deal - handoff kickoff task", "Handoff / delivery kickoff", 1, None, "${!Deals.Owner}", "High", "Closed Won delivery handoff."),
        (DEALS, "Deal - revisit closed lost task", "Revisit closed-lost opportunity", None, "${!Deals.Next_try_follow_up_date}", "${!Deals.Owner}", "Normal", "Follow up on the next try date captured at Closed Lost."),
        (DEALS, "Deal - stale open review task", "Review stale open deal", 0, None, "${!Deals.Owner}", "Normal", "Open deal has not been modified for 14 days. Check stage and log meaningful customer activity."),
        (DEALS, "Deal - fix negotiation quote share task", "Fix quote shared flags or move stage back", 0, None, "${!Deals.Owner}", "High", "Deal is in Negotiation but no linked Quote is currently marked shared with customer."),
        (DEALS, "Deal - closed won manager notification task", "Closed Won: manager review", 0, None, "${!Deals.Owner.Reporting_To}", "High", "Sales manager notification for Closed Won. Review amount, deal, and Primary Quote."),
    ]
    for module, name, subject, due_days, due_merge, owner_merge, priority, desc in task_specs:
        tid, task_gap = _ensure_task_action(
            session,
            api_domain,
            modules,
            task_fields,
            module=module,
            name=name,
            subject=subject,
            due_days=due_days,
            due_merge_field=due_merge,
            owner_merge_field=owner_merge,
            priority=priority,
            description=desc,
            dry_run=dry_run,
        )
        if task_gap:
            gaps.append(task_gap)
        if tid:
            task_ids[name] = tid

    print("\n== Workflow Rules ==")
    ok = True
    deal_fields = fields[DEALS]
    quote_fields = fields[QUOTES]
    stage = deal_fields["Stage"]
    rollback_field_update_id = _ensure_stage_rollback_field_update(
        session, api_domain, modules, deal_fields, dry_run
    )
    if not rollback_field_update_id:
        gaps.append(
            "Proposal / Quote server-side rollback workflows could not be created because "
            "the Stage rollback field update action failed."
        )

    def task_action(name: str) -> dict[str, str]:
        tid = task_ids.get(name)
        if not tid:
            raise RuntimeError(f"Required automation task action was not created: {name}")
        return {"type": "tasks", "id": tid}

    workflow_specs: list[tuple[str, dict[str, Any]]] = [
        (
            LEADS,
            _workflow_base(
                modules,
                LEADS,
                "Lead - contact same day",
                "Auto-create a same-day contact task when a Lead is registered.",
                _create_trigger(modules, LEADS),
                [task_action("Lead - contact same day task")],
            ),
        ),
        (
            DEALS,
            _workflow_base(
                modules,
                DEALS,
                "Deal stage - Qualification task",
                "Create initial discovery scheduling task when a Deal is created in Qualification.",
                _create_trigger(modules, DEALS),
                [task_action("Deal - schedule discovery task")],
                _criterion(stage, "equal", "Qualification"),
            ),
        ),
    ]

    if "deal_stage_gate_guard" in function_ids:
        needs_analysis_actions = [
            task_action("Deal - complete discovery task"),
            {"type": "functions", "id": function_ids["deal_stage_gate_guard"]},
        ]
    else:
        needs_analysis_actions = [task_action("Deal - complete discovery task")]
        gaps.append(
            "Needs Analysis task workflow fell back to an Automation Task action because "
            "deal_stage_gate_guard is unavailable; Zoho may omit the task Description checklist."
        )

    stage_action_map = {
        "Needs Analysis": needs_analysis_actions,
        "Proposal / Quote": [task_action("Deal - proposal quote task")],
        "Negotiation": [task_action("Deal - negotiation timeline task")],
        "Closed Won": [task_action("Deal - handoff kickoff task")],
    }
    for stage_value, actions in stage_action_map.items():
        workflow_specs.append(
            (
                DEALS,
                _workflow_base(
                    modules,
                    DEALS,
                    f"Deal stage - {stage_value} task",
                    f"Auto-create stakeholder-agreed follow-up task when Deal enters {stage_value}.",
                    _stage_update_trigger(modules, deal_fields, stage_value),
                    actions,
                ),
            )
        )

    if rollback_field_update_id:
        proposal_required_fields = [
            ("Discovery summary", "Discovery_summary"),
            ("Current machines setup", "Current_machines_setup"),
            ("Applications", "Applications"),
            ("Budget financing status", "Budget_financing_status"),
            ("Amount", "Amount"),
            ("Primary Quote", "Primary_Quote"),
        ]
        for label, api_name in proposal_required_fields:
            required_field = deal_fields.get(api_name)
            if not required_field:
                gaps.append(f"Proposal / Quote rollback workflow skipped missing Deals.{api_name}.")
                continue
            workflow_specs.append(
                (
                    DEALS,
                    _workflow_base(
                        modules,
                        DEALS,
                        f"Deal gate rollback - Proposal missing {label}",
                        f"Server-side rollback to Needs Analysis when Proposal / Quote is missing {label}.",
                        _stage_update_trigger(modules, deal_fields, "Proposal / Quote", repeat=True),
                        [{"type": "field_updates", "id": rollback_field_update_id}],
                        _and(
                            [
                                _criterion(stage, "equal", "Proposal / Quote"),
                                _criterion(required_field, "equal", "${EMPTY}"),
                            ]
                        ),
                    ),
                )
            )
        budget_field = deal_fields.get("Budget_financing_status")
        if budget_field:
            workflow_specs.append(
                (
                    DEALS,
                    _workflow_base(
                        modules,
                        DEALS,
                        "Deal gate rollback - Proposal budget none",
                        "Server-side rollback to Needs Analysis when Budget / financing status is -None-.",
                        _stage_update_trigger(modules, deal_fields, "Proposal / Quote", repeat=True),
                        [{"type": "field_updates", "id": rollback_field_update_id}],
                        _and(
                            [
                                _criterion(stage, "equal", "Proposal / Quote"),
                                _criterion(budget_field, "equal", "-None-"),
                            ]
                        ),
                    ),
                )
            )

    next_try_field = deal_fields.get("Next_try_follow_up_date")
    if next_try_field:
        workflow_specs.append(
            (
                DEALS,
                _workflow_base(
                    modules,
                    DEALS,
                    "Deal stage - Closed Lost revisit task",
                    "Create revisit task when Closed Lost has a next try date.",
                    _stage_update_trigger(modules, deal_fields, "Closed Lost"),
                    [task_action("Deal - revisit closed lost task")],
                    _criterion(next_try_field, "equal", "${NOTEMPTY}"),
                ),
            )
        )

    any_shared = deal_fields.get("Any_quote_shared_with_customer")
    if any_shared:
        workflow_specs.append(
            (
                DEALS,
                _workflow_base(
                    modules,
                    DEALS,
                    "Deal integrity - Negotiation without shared quote",
                    "Alert owner if a Deal in Negotiation no longer has any linked Quote marked shared.",
                    _field_any_update_trigger(modules, DEALS, any_shared),
                    [task_action("Deal - fix negotiation quote share task")],
                    _and([
                        _criterion(stage, "equal", "Negotiation"),
                        _criterion(any_shared, "equal", "false"),
                    ]),
                ),
            )
        )

    if "Modified_Time" in deal_fields:
        workflow_specs.append(
            (
                DEALS,
                _workflow_base(
                    modules,
                    DEALS,
                    "Deal stale open - 14 day review",
                    "Practical v1 stale rule: open Deal Modified Time +14 days creates review task.",
                    {
                        "type": "date_or_datetime",
                        "details": {
                            "trigger_module": {"api_name": DEALS, "id": str(modules[DEALS]["id"])},
                            "field": {"api_name": "Modified_Time", "id": str(deal_fields["Modified_Time"]["id"])},
                            "unit": 14,
                            "period": "days",
                            "execute_at": "09:00:00+03:00",
                            "recur_cycle": "once",
                        },
                    },
                    [task_action("Deal - stale open review task")],
                    _and([
                        _criterion(stage, "not_equal", "Closed Won"),
                        _criterion(stage, "not_equal", "Closed Lost"),
                    ]),
                ),
            )
        )
    else:
        gaps.append("Stale open Deal workflow skipped because Modified_Time was not exposed in Deals fields metadata.")

    workflow_specs.append(
        (
            DEALS,
            _workflow_base(
                modules,
                DEALS,
                "Deal Closed Won - manager notification",
                "Notify sales manager through a workflow task assigned to Deal Owner.Reporting_To.",
                _stage_update_trigger(modules, deal_fields, "Closed Won"),
                [task_action("Deal - closed won manager notification task")],
            ),
        )
    )

    if "quote_recompute_deal_shared" in function_ids:
        workflow_specs.append(
            (
                QUOTES,
                _workflow_base(
                    modules,
                    QUOTES,
                    "Quote - recompute Deal shared rollup",
                    "Recompute Deal Any quote shared with customer whenever a Quote is created or edited.",
                    {
                        "type": "create_or_edit",
                        "details": {
                            "trigger_module": {"api_name": QUOTES, "id": str(modules[QUOTES]["id"])},
                            "repeat": True,
                        },
                    },
                    [{"type": "functions", "id": function_ids["quote_recompute_deal_shared"]}],
                ),
            )
        )
    else:
        gaps.append("Quote shared rollup workflow skipped because quote_recompute_deal_shared function is unavailable.")

    quote_shared = quote_fields.get("Quote_shared_with_customer")
    if quote_shared and "quote_shared_owner_guard" in function_ids:
        workflow_specs.append(
            (
                QUOTES,
                _workflow_base(
                    modules,
                    QUOTES,
                    "Quote - shared checkbox owner guard",
                    "When Quote shared with customer changes, reset unauthorized true values set by non-owners.",
                    _field_any_update_trigger(modules, QUOTES, quote_shared),
                    [{"type": "functions", "id": function_ids["quote_shared_owner_guard"]}],
                ),
            )
        )
    else:
        gaps.append("Quote Owner-only checkbox guard skipped because field or function is unavailable.")

    if "deal_stage_gate_guard" in function_ids:
        workflow_specs.append(
            (
                DEALS,
                _workflow_base(
                    modules,
                    DEALS,
                    "Deal - stage gate guard",
                    "Post-save guard for Proposal / Quote, Negotiation, Closed Won, and Closed Lost rules where Blueprint definition API is unavailable.",
                    _field_any_update_trigger(modules, DEALS, stage, repeat=True),
                    [{"type": "functions", "id": function_ids["deal_stage_gate_guard"]}],
                ),
            )
        )
    else:
        gaps.append("Deal stage gate guard workflow skipped because deal_stage_gate_guard function is unavailable.")

    for module, body in workflow_specs:
        wid = _create_workflow(session, api_domain, module, body, dry_run)
        ok = bool(wid) and ok
    return ok, gaps


def _probe_api_limits(session: requests.Session, api_domain: str) -> list[str]:
    print("\n== API Limit Probes ==")
    gaps: list[str] = []
    r = _crm(session, api_domain, "GET", "/settings/blueprints")
    print(f"  GET /settings/blueprints -> HTTP {r.status_code}")
    if not r.ok and r.status_code != 204:
        print(f"    {r.text[:1000]}")
    gaps.append(
        "Zoho CRM exposes Blueprint setup in the UI at Setup > Process Management > Blueprint, "
        "but the public APIs found here expose record transition execution, not definition create/update."
    )

    rv = _crm(session, api_domain, "GET", "/settings/validation_rules", params={"module": DEALS})
    print(f"  GET /settings/validation_rules?module=Deals -> HTTP {rv.status_code}")
    if rv.ok and rv.status_code != 204 and (rv.text or "").strip():
        print("    Validation rules endpoint is readable, but this script does not yet know a documented create payload.")
        gaps.append("Validation rules endpoint was readable but no documented create/update payload was found in v8 docs.")
    else:
        print(f"    {rv.text[:1000] if rv.text else '(empty)'}")
        gaps.append(
            "No public/working v8 Settings Validation Rules create endpoint was found for API-only hard blocking; "
            "post-save Deluge guards and workflow tasks are used instead."
        )

    apis = _crm(session, api_domain, "GET", "/__apis")
    if apis.ok:
        paths = [str(x.get("path") or "") for x in (apis.json().get("__apis") or [])]
        bp_create = [p for p in paths if "blueprint" in p.lower() and "settings" in p.lower()]
        validation = [p for p in paths if "validation" in p.lower()]
        bp_record = [p for p in paths if p.lower().endswith("/actions/blueprint")]
        print(f"  /__apis blueprint settings paths: {bp_create[:10] or 'none'}")
        print(f"  /__apis record blueprint action paths: {bp_record[:5] or 'none'}")
        print(f"  /__apis validation paths: {validation[:10] or 'none'}")
    else:
        print(f"  GET /__apis -> HTTP {apis.status_code} ({apis.text[:500] if apis.text else 'empty'})")

    apis_v9 = _crm_version(session, api_domain, "v9", "GET", "/__apis")
    print(f"  GET /crm/v9/__apis -> HTTP {apis_v9.status_code}")
    if apis_v9.ok:
        paths_v9 = [str(x.get("path") or "") for x in (apis_v9.json().get("__apis") or [])]
        bp_settings_v9 = [p for p in paths_v9 if "blueprint" in p.lower() and "settings" in p.lower()]
        bp_record_v9 = [p for p in paths_v9 if p.lower().endswith("/actions/blueprint")]
        print(f"  v9 /__apis blueprint settings paths: {bp_settings_v9[:10] or 'none'}")
        print(f"  v9 /__apis record blueprint action paths: {bp_record_v9[:5] or 'none'}")
    else:
        print(f"    {apis_v9.text[:500] if apis_v9.text else '(empty)'}")

    bp_v9 = _crm_version(session, api_domain, "v9", "GET", "/settings/blueprints")
    print(f"  GET /crm/v9/settings/blueprints -> HTTP {bp_v9.status_code}")
    if not bp_v9.ok and bp_v9.status_code != 204:
        print(f"    {bp_v9.text[:1000] if bp_v9.text else '(empty)'}")
    return gaps


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print planned writes without changing Zoho.")
    args = parser.parse_args()

    try:
        access, api_domain = _token_retry()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    session = requests.Session()
    session.headers.update(auth_headers(access))
    session.headers["Content-Type"] = "application/json"

    try:
        modules = _module_map(session, api_domain)
        for required in (DEALS, QUOTES, LEADS, TASKS):
            if required not in modules:
                raise RuntimeError(f"Required module missing from metadata: {required}")
        api_gaps = _probe_api_limits(session, api_domain)
        fields, field_gaps = _ensure_fields(session, api_domain, modules, args.dry_run)
        ok_layouts = _ensure_layouts(session, api_domain, fields, args.dry_run)
        function_ids, function_gaps = _ensure_functions(session, api_domain, modules, args.dry_run)
        ok_workflows, workflow_gaps = _ensure_workflows(
            session,
            api_domain,
            modules,
            fields,
            function_ids,
            args.dry_run,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    gaps = api_gaps + field_gaps + function_gaps + workflow_gaps
    print("\n== Result ==")
    print(f"  Layout provisioning: {'ok' if ok_layouts else 'FAILED'}")
    print(f"  Workflow provisioning: {'ok' if ok_workflows else 'FAILED'}")
    if gaps:
        print("  Manual/API gaps to report:")
        for gap in gaps:
            print(f"    - {gap}")
    else:
        print("  No API gaps detected by this run.")
    return 0 if ok_layouts and ok_workflows else 1


if __name__ == "__main__":
    raise SystemExit(main())
