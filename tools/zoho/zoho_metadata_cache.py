#!/usr/bin/env python3
"""
Local Zoho CRM metadata cache + compact summary.

Purpose:
  - Reduce repeated Zoho API metadata calls during automation work.
  - Reduce AI context/token usage by producing a small, readable summary.
  - Keep live org snapshots out of git (`.cache/zoho/` is ignored).

This script fetches metadata only (fields, layouts, Deals pipeline/map dependencies).
It does not fetch customer records.

Usage:
  cd tools/zoho
  ./venv/bin/python zoho_metadata_cache.py summary
  ./venv/bin/python zoho_metadata_cache.py refresh --force
  ./venv/bin/python zoho_metadata_cache.py status
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from zoho_tokens import auth_headers, get_access_token_and_domain

API_VER = "v8"
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_CACHE_DIR = REPO_ROOT / ".cache" / "zoho"
DEFAULT_MODULES = ("Leads", "Deals", "Accounts", "Contacts", "Products", "Quotes")

RAW_JSON = "metadata.raw.json"
SUMMARY_JSON = "metadata.summary.json"
SUMMARY_MD = "metadata.summary.md"


@dataclass
class ApiCall:
    label: str
    path: str
    status_code: int
    credits_remaining: str | None


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _cache_age_seconds(summary_path: Path) -> float | None:
    payload = _read_json(summary_path)
    if not payload:
        return None
    generated_at = payload.get("generated_at_epoch")
    try:
        return time.time() - float(generated_at)
    except (TypeError, ValueError):
        return None


def _is_fresh(summary_path: Path, ttl_hours: float) -> bool:
    age = _cache_age_seconds(summary_path)
    if age is None:
        return False
    return age <= ttl_hours * 3600


def _crm(
    session: requests.Session,
    api_domain: str,
    method: str,
    path: str,
    calls: list[ApiCall],
    label: str,
    **kwargs: Any,
) -> dict[str, Any]:
    url = f"{api_domain.rstrip('/')}/crm/{API_VER}{path}"
    resp = session.request(method, url, timeout=120, **kwargs)
    calls.append(
        ApiCall(
            label=label,
            path=path,
            status_code=resp.status_code,
            credits_remaining=resp.headers.get("X-API-CREDITS-REMAINING"),
        )
    )
    if resp.status_code == 204 or not resp.text.strip():
        return {}
    if not resp.ok:
        raise RuntimeError(f"{label}: HTTP {resp.status_code}: {resp.text[:1500]}")
    try:
        return resp.json()
    except json.JSONDecodeError as e:
        raise RuntimeError(f"{label}: non-JSON response: {resp.text[:500]}") from e


def _active_layouts(layout_payload: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for lo in layout_payload.get("layouts") or []:
        if lo.get("status") == "active":
            out.append(
                {
                    "name": str(lo.get("name") or ""),
                    "id": str(lo.get("id") or ""),
                    "api_name": str(lo.get("api_name") or ""),
                }
            )
    return out


def _pick_standard_layout_id(layout_payload: dict[str, Any]) -> str | None:
    active = _active_layouts(layout_payload)
    for lo in active:
        if lo["name"] == "Standard":
            return lo["id"]
    return active[0]["id"] if active else None


def _field_by_api(fields_payload: dict[str, Any], api_name: str) -> dict[str, Any] | None:
    for f in fields_payload.get("fields") or []:
        if f.get("api_name") == api_name:
            return f
    return None


def _field_by_label(fields_payload: dict[str, Any], label: str) -> dict[str, Any] | None:
    wanted = label.strip().casefold()
    for f in fields_payload.get("fields") or []:
        if str(f.get("field_label") or "").strip().casefold() == wanted:
            return f
    return None


def _picklist_values(field: dict[str, Any] | None, *, include_unused: bool = False) -> list[str]:
    if not field:
        return []
    out: list[str] = []
    for opt in field.get("pick_list_values") or []:
        if not include_unused and str(opt.get("type") or "").lower() == "unused":
            continue
        display = str(opt.get("display_value") or "").strip()
        if display and display != "-None-":
            out.append(display)
    return out


def _count_fields(fields_payload: dict[str, Any]) -> dict[str, int]:
    fields = fields_payload.get("fields") or []
    return {
        "total": len(fields),
        "custom": sum(1 for f in fields if f.get("custom_field")),
        "picklists": sum(1 for f in fields if f.get("data_type") in ("picklist", "multiselectpicklist")),
        "system_mandatory": sum(1 for f in fields if f.get("system_mandatory")),
    }


def _important_fields(module: str, fields_payload: dict[str, Any]) -> list[dict[str, Any]]:
    important_by_module = {
        "Leads": (
            "Company",
            "First_Name",
            "Last_Name",
            "Phone",
            "Industry",
            "Sector",
            "Line_of_business",
            "Country",
            "State",
            "City",
        ),
        "Deals": (
            "Deal_Name",
            "Stage",
            "Pipeline",
            "Amount",
            "Closing_Date",
            "Line_of_business",
            "Lost_Reason",
            "Reason_For_Loss__s",
            "Competitor",
        ),
        "Quotes": (
            "Subject",
            "Deal_Name",
            "Quote_Stage",
            "Valid_Till",
            "Quoted_Items",
            "Product_Details",
        ),
        "Products": (
            "Product_Name",
            "Product_Code",
            "Unit_Price",
            "Description",
        ),
    }
    out: list[dict[str, Any]] = []
    for api_name in important_by_module.get(module, ()):
        f = _field_by_api(fields_payload, api_name)
        if not f:
            continue
        item: dict[str, Any] = {
            "api_name": str(f.get("api_name") or ""),
            "label": str(f.get("field_label") or ""),
            "data_type": str(f.get("data_type") or ""),
            "id": str(f.get("id") or ""),
            "custom": bool(f.get("custom_field")),
            "system_mandatory": bool(f.get("system_mandatory")),
        }
        if f.get("data_type") in ("picklist", "multiselectpicklist"):
            item["picklist_values"] = _picklist_values(f)
        out.append(item)
    return out


def _summarize_deals(raw: dict[str, Any]) -> dict[str, Any]:
    deals = raw["modules"].get("Deals") or {}
    fields = deals.get("fields") or {}
    layouts = deals.get("layouts") or {}
    stage_field = _field_by_api(fields, "Stage")
    line_field = _field_by_api(fields, "Line_of_business")
    lost_field = _field_by_api(fields, "Lost_Reason") or _field_by_api(fields, "Reason_For_Loss__s")
    competitor_field = _field_by_api(fields, "Competitor")

    pipelines = []
    for pipe in (deals.get("pipelines") or {}).get("pipeline") or []:
        pipelines.append(
            {
                "name": str(pipe.get("display_value") or ""),
                "default": bool(pipe.get("default")),
                "id": str(pipe.get("id") or ""),
                "stages": [
                    {
                        "sequence": m.get("sequence_number"),
                        "display": m.get("display_value"),
                        "actual": m.get("actual_value"),
                        "id": str(m.get("id") or ""),
                    }
                    for m in (pipe.get("maps") or [])
                ],
            }
        )

    active_stage_options: list[dict[str, Any]] = []
    unused_stage_options: list[str] = []
    for opt in (deals.get("stage_pick_list_values") or {}).get("pick_list_values") or []:
        display = str(opt.get("display_value") or "").strip()
        if not display:
            continue
        if opt.get("layout_associations"):
            active_stage_options.append(
                {
                    "sequence": opt.get("sequence_number"),
                    "display": display,
                    "actual": opt.get("actual_value"),
                    "id": str(opt.get("id") or ""),
                }
            )
        elif str(opt.get("type") or "").lower() == "unused":
            unused_stage_options.append(display)

    active_stage_options.sort(key=lambda x: (x.get("sequence") is None, x.get("sequence") or 9999))

    return {
        "active_layouts": _active_layouts(layouts),
        "standard_layout_id": _pick_standard_layout_id(layouts),
        "pipelines": pipelines,
        "active_stage_options": active_stage_options,
        "unused_stage_options": unused_stage_options,
        "line_of_business_values": _picklist_values(line_field),
        "lost_reason_values": _picklist_values(lost_field),
        "competitor_values_count": len(_picklist_values(competitor_field)),
        "map_dependencies": [
            {
                "id": str(md.get("id") or ""),
                "parent": (md.get("parent") or {}).get("api_name"),
                "child": (md.get("child") or {}).get("api_name"),
                "parent_values": len(md.get("pick_list_values") or []),
            }
            for md in (deals.get("map_dependencies") or {}).get("map_dependency") or []
        ],
        "stage_field_id": str((stage_field or {}).get("id") or ""),
    }


def _build_summary(raw: dict[str, Any], calls: list[ApiCall]) -> dict[str, Any]:
    modules_summary: dict[str, Any] = {}
    for module, payload in raw.get("modules", {}).items():
        fields_payload = payload.get("fields") or {}
        layouts_payload = payload.get("layouts") or {}
        modules_summary[module] = {
            "field_counts": _count_fields(fields_payload),
            "active_layouts": _active_layouts(layouts_payload),
            "standard_layout_id": _pick_standard_layout_id(layouts_payload),
            "important_fields": _important_fields(module, fields_payload),
        }

    return {
        "generated_at": raw["generated_at"],
        "generated_at_epoch": raw["generated_at_epoch"],
        "api_domain": raw["api_domain"],
        "modules": modules_summary,
        "deals": _summarize_deals(raw),
        "api_calls": [
            {
                "label": c.label,
                "path": c.path,
                "status_code": c.status_code,
                "credits_remaining": c.credits_remaining,
            }
            for c in calls
        ],
        "api_call_count": len(calls),
        "estimated_credit_floor": len(calls),
        "note": "Metadata only; no customer records. Custom-field/layout updates are not included here.",
    }


def _markdown(summary: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Zoho CRM Metadata Cache Summary")
    lines.append("")
    lines.append(f"- Generated: `{summary['generated_at']}`")
    lines.append(f"- API domain: `{summary['api_domain']}`")
    lines.append(f"- API calls used for refresh: `{summary['api_call_count']}`")
    lines.append(f"- Estimated credit floor: `{summary['estimated_credit_floor']}`")
    remaining = [c.get("credits_remaining") for c in summary.get("api_calls") or [] if c.get("credits_remaining")]
    if remaining:
        lines.append(f"- Last reported credits remaining: `{remaining[-1]}`")
    lines.append("")

    deals = summary.get("deals") or {}
    lines.append("## Deals Pipeline")
    for pipe in deals.get("pipelines") or []:
        default = " (default)" if pipe.get("default") else ""
        lines.append(f"- `{pipe.get('name')}`{default}:")
        for st in pipe.get("stages") or []:
            lines.append(f"  - {st.get('sequence')}. `{st.get('display')}`")
    if deals.get("unused_stage_options"):
        hidden = ", ".join(f"`{x}`" for x in deals["unused_stage_options"])
        lines.append(f"- Unused Stage values: {hidden}")
    lines.append("")

    lines.append("## Deal Fields")
    lines.append(f"- Standard layout id: `{deals.get('standard_layout_id')}`")
    if deals.get("line_of_business_values"):
        vals = ", ".join(f"`{x}`" for x in deals["line_of_business_values"])
        lines.append(f"- Line of business: {vals}")
    lines.append(f"- Competitor picklist values: `{deals.get('competitor_values_count')}`")
    if deals.get("lost_reason_values"):
        vals = ", ".join(f"`{x}`" for x in deals["lost_reason_values"])
        lines.append(f"- Lost reasons: {vals}")
    lines.append("")

    lines.append("## Modules")
    for module, meta in (summary.get("modules") or {}).items():
        counts = meta.get("field_counts") or {}
        layout_names = ", ".join(
            f"`{x.get('name')}`:{x.get('id')}" for x in (meta.get("active_layouts") or [])
        )
        lines.append(
            f"- `{module}`: fields `{counts.get('total')}`, custom `{counts.get('custom')}`, "
            f"picklists `{counts.get('picklists')}`, layouts {layout_names or '`none`'}"
        )
    lines.append("")
    lines.append("## Agent Use")
    lines.append("- Read this file first for CRM context before calling Zoho metadata APIs.")
    lines.append("- Refresh only when stale or after metadata changes: `make zoho-cache-refresh`.")
    lines.append("- Raw cache is local and gitignored: `.cache/zoho/metadata.raw.json`.")
    lines.append("")
    return "\n".join(lines)


def refresh(cache_dir: Path, modules: list[str]) -> dict[str, Any]:
    calls: list[ApiCall] = []
    access, api_domain = get_access_token_and_domain()
    session = requests.Session()
    session.headers.update(auth_headers(access))
    session.headers["Content-Type"] = "application/json"

    raw: dict[str, Any] = {
        "generated_at": _now_iso(),
        "generated_at_epoch": time.time(),
        "api_domain": api_domain,
        "modules": {},
    }

    for module in modules:
        module = module.strip()
        if not module:
            continue
        fields = _crm(
            session,
            api_domain,
            "GET",
            "/settings/fields",
            calls,
            f"{module} fields",
            params={"module": module, "type": "all", "per_page": 200},
        )
        layouts = _crm(
            session,
            api_domain,
            "GET",
            "/settings/layouts",
            calls,
            f"{module} layouts",
            params={"module": module},
        )
        raw["modules"][module] = {"fields": fields, "layouts": layouts}

    deals = raw["modules"].get("Deals")
    if deals:
        layout_id = _pick_standard_layout_id(deals.get("layouts") or {})
        if layout_id:
            deals["pipelines"] = _crm(
                session,
                api_domain,
                "GET",
                "/settings/pipeline",
                calls,
                "Deals pipelines",
                params={"layout_id": layout_id},
            )
            deals["map_dependencies"] = _crm(
                session,
                api_domain,
                "GET",
                f"/settings/layouts/{layout_id}/map_dependency",
                calls,
                "Deals map dependencies",
                params={"module": "Deals"},
            )
        stage_field = _field_by_api(deals.get("fields") or {}, "Stage")
        if stage_field and stage_field.get("id"):
            deals["stage_pick_list_values"] = _crm(
                session,
                api_domain,
                "GET",
                f"/settings/fields/{stage_field['id']}/pick_list_values",
                calls,
                "Deals Stage picklist associations",
                params={"module": "Deals"},
            )

    summary = _build_summary(raw, calls)
    _write_json(cache_dir / RAW_JSON, raw)
    _write_json(cache_dir / SUMMARY_JSON, summary)
    _write_text(cache_dir / SUMMARY_MD, _markdown(summary))
    return summary


def ensure_summary(cache_dir: Path, ttl_hours: float, force: bool, modules: list[str]) -> dict[str, Any]:
    summary_path = cache_dir / SUMMARY_JSON
    if force or not _is_fresh(summary_path, ttl_hours):
        return refresh(cache_dir, modules)
    cached = _read_json(summary_path)
    if not cached:
        return refresh(cache_dir, modules)
    return cached


def print_status(cache_dir: Path, ttl_hours: float) -> int:
    summary_path = cache_dir / SUMMARY_JSON
    summary = _read_json(summary_path)
    if not summary:
        print(f"No cache found at {summary_path}")
        return 1
    age = _cache_age_seconds(summary_path)
    age_text = "unknown" if age is None else f"{age / 3600:.2f}h"
    print(f"Cache: {summary_path}")
    print(f"Generated: {summary.get('generated_at')}")
    print(f"Age: {age_text}")
    print(f"Fresh (ttl={ttl_hours}h): {_is_fresh(summary_path, ttl_hours)}")
    print(f"Summary markdown: {cache_dir / SUMMARY_MD}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Cache Zoho CRM metadata and write compact summaries")
    parser.add_argument(
        "command",
        choices=("summary", "refresh", "status", "path"),
        nargs="?",
        default="summary",
        help="summary auto-refreshes when stale; refresh always fetches; path prints summary path",
    )
    parser.add_argument("--force", action="store_true", help="Force refresh before printing summary")
    parser.add_argument("--ttl-hours", type=float, default=24.0, help="Cache freshness window")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument(
        "--modules",
        default=",".join(DEFAULT_MODULES),
        help="Comma-separated modules to cache (default: core CRM modules)",
    )
    args = parser.parse_args()

    cache_dir = args.cache_dir
    modules = [x.strip() for x in args.modules.split(",") if x.strip()]

    try:
        if args.command == "path":
            print(cache_dir / SUMMARY_MD)
            return 0
        if args.command == "status":
            return print_status(cache_dir, args.ttl_hours)
        if args.command == "refresh":
            summary = refresh(cache_dir, modules)
        else:
            summary = ensure_summary(cache_dir, args.ttl_hours, args.force, modules)
        print(f"Wrote: {cache_dir / SUMMARY_JSON}")
        print(f"Wrote: {cache_dir / SUMMARY_MD}")
        print(f"API calls in last refresh: {summary.get('api_call_count')}")
        print(f"Read summary first: {cache_dir / SUMMARY_MD}")
        return 0
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
