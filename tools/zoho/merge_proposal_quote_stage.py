#!/usr/bin/env python3
"""
Finish the live-org merge of Deal stages:

  Solution / Value + Quote Sent -> Proposal / Quote

This script is intentionally narrow and idempotent:
  - bulk-updates Deals still sitting on old stage labels to Proposal / Quote;
  - deactivates old Deals workflow rules whose criteria point at the removed stage labels.

Run after:
  provision_deal_stage_picklist.py
  provision_pipelines.py --sync
  provision_deals_quotes_process.py
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import requests

from zoho_tokens import auth_headers, get_access_token_and_domain

API_VER = "v8"
DEALS = "Deals"
NEW_STAGE = "Proposal / Quote"
OLD_STAGE_VALUES = (
    "Solution / Value",
    "Quote Sent",
    "Value Proposition",
    "Proposal/Price Quote",
)
OLD_WORKFLOW_NAMES = (
    "Deal stage - Solution / Value task",
    "Deal stage - Quote Sent task",
)


def _crm(
    session: requests.Session,
    api_domain: str,
    method: str,
    path: str,
    **kwargs: Any,
) -> requests.Response:
    url = f"{api_domain.rstrip('/')}/crm/{API_VER}{path}"
    return session.request(method, url, timeout=120, **kwargs)


def _stage_labels(session: requests.Session, api_domain: str) -> set[str]:
    r = _crm(
        session,
        api_domain,
        "GET",
        "/settings/fields",
        params={"module": DEALS, "type": "all", "per_page": 200},
    )
    if not r.ok:
        raise RuntimeError(f"GET Deals fields HTTP {r.status_code}: {r.text[:2000]}")
    for field in r.json().get("fields") or []:
        if field.get("api_name") != "Stage":
            continue
        labels: set[str] = set()
        for option in field.get("pick_list_values") or []:
            if str(option.get("type") or "").lower() == "unused":
                continue
            for key in ("display_value", "actual_value"):
                val = str(option.get(key) or "").strip()
                if val:
                    labels.add(val)
        return labels
    raise RuntimeError("Deals Stage field not found.")


def _coql(session: requests.Session, api_domain: str, query: str) -> dict[str, Any]:
    r = _crm(session, api_domain, "POST", "/coql", json={"select_query": query})
    if r.status_code == 204:
        return {"data": [], "info": {"more_records": False}}
    if not r.ok:
        raise RuntimeError(f"COQL HTTP {r.status_code}: {r.text[:2000]}\nQuery: {query}")
    return r.json()


def _search_deals_by_stage(
    session: requests.Session,
    api_domain: str,
    stage: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    page = 1
    while True:
        r = _crm(
            session,
            api_domain,
            "GET",
            f"/{DEALS}/search",
            params={
                "criteria": f"(Stage:equals:{stage})",
                "fields": "id,Deal_Name,Stage",
                "per_page": 200,
                "page": page,
            },
        )
        if r.status_code == 204:
            return out
        if not r.ok:
            raise RuntimeError(
                f"GET {DEALS}/search Stage={stage!r} HTTP {r.status_code}: {r.text[:2000]}"
            )
        payload = r.json()
        out.extend(payload.get("data") or [])
        if not (payload.get("info") or {}).get("more_records"):
            return out
        page += 1


def _old_stage_deals_via_search(
    session: requests.Session,
    api_domain: str,
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for stage in OLD_STAGE_VALUES:
        for deal in _search_deals_by_stage(session, api_domain, stage):
            did = str(deal.get("id") or "")
            if did:
                by_id[did] = deal
    return list(by_id.values())


def _old_stage_deals(session: requests.Session, api_domain: str) -> list[dict[str, Any]]:
    conditions = " or ".join(f"Stage = '{stage}'" for stage in OLD_STAGE_VALUES)
    records: list[dict[str, Any]] = []
    offset = 0
    while True:
        query = (
            "select id, Deal_Name, Stage from Deals "
            f"where ({conditions}) "
            f"limit 200 offset {offset}"
        )
        try:
            payload = _coql(session, api_domain, query)
        except RuntimeError as exc:
            if "OAUTH_SCOPE_MISMATCH" not in str(exc):
                raise
            print("  COQL scope unavailable; falling back to Deals search API.")
            return _old_stage_deals_via_search(session, api_domain)
        batch = payload.get("data") or []
        records.extend(batch)
        if not (payload.get("info") or {}).get("more_records"):
            return records
        offset += 200


def _update_deals_stage(
    session: requests.Session,
    api_domain: str,
    deals: list[dict[str, Any]],
    dry_run: bool,
) -> bool:
    if not deals:
        print("  No Deals found on old stage labels.")
        return True
    print(f"  Updating {len(deals)} Deal(s) to Stage={NEW_STAGE!r}.")
    if dry_run:
        for deal in deals[:20]:
            print(f"    dry-run: {deal.get('id')} {deal.get('Deal_Name')!r} ({deal.get('Stage')!r})")
        if len(deals) > 20:
            print(f"    ... {len(deals) - 20} more")
        return True

    ok = True
    for start in range(0, len(deals), 100):
        chunk = deals[start : start + 100]
        body = {
            "data": [{"id": str(deal["id"]), "Stage": NEW_STAGE} for deal in chunk],
            "trigger": [],
        }
        r = _crm(session, api_domain, "PUT", f"/{DEALS}", json=body)
        if not r.ok:
            print(f"  PUT Deals HTTP {r.status_code}: {r.text[:4000]}", file=sys.stderr)
            ok = False
            continue
        for item in r.json().get("data") or []:
            if item.get("status") != "success":
                print(f"  Deal update failed: {json.dumps(item)[:1000]}", file=sys.stderr)
                ok = False
    return ok


def _workflow_rules(session: requests.Session, api_domain: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    page = 1
    while True:
        r = _crm(
            session,
            api_domain,
            "GET",
            "/settings/automation/workflow_rules",
            params={"module": DEALS, "per_page": 200, "page": page},
        )
        if r.status_code == 204:
            return out
        if not r.ok:
            raise RuntimeError(f"GET workflow_rules HTTP {r.status_code}: {r.text[:2000]}")
        payload = r.json()
        out.extend(payload.get("workflow_rules") or [])
        if not (payload.get("info") or {}).get("more_records"):
            return out
        page += 1


def _is_active(workflow: dict[str, Any]) -> bool:
    status = workflow.get("status")
    if isinstance(status, dict):
        return bool(status.get("active"))
    if isinstance(status, str):
        return status.strip().lower() in {"active", "true"}
    return bool(status)


def _deactivate_workflow(
    session: requests.Session,
    api_domain: str,
    workflow: dict[str, Any],
    dry_run: bool,
) -> bool:
    wid = str(workflow.get("id") or "")
    name = str(workflow.get("name") or "")
    if not wid:
        print(f"  Workflow {name!r} has no id; cannot deactivate.", file=sys.stderr)
        return False
    if not _is_active(workflow):
        print(f"  Workflow already inactive: {name} id={wid}")
        return True
    print(f"  Deactivating workflow: {name} id={wid}")
    if dry_run:
        return True

    body = {"workflow_rules": [{"id": wid, "status": {"active": False, "delete_schedule_action": False}}]}
    r = _crm(session, api_domain, "PUT", f"/settings/automation/workflow_rules/{wid}", json=body)
    if not r.ok:
        print(f"  PUT workflow_rules/{wid} HTTP {r.status_code}: {r.text[:4000]}", file=sys.stderr)
        return False
    for item in r.json().get("workflow_rules") or []:
        if item.get("status") == "success" or item.get("code") == "SUCCESS":
            return True
    print(f"  Workflow deactivate response: {r.text[:2000]}")
    return True


def _deactivate_old_workflows(
    session: requests.Session,
    api_domain: str,
    dry_run: bool,
) -> bool:
    workflows = _workflow_rules(session, api_domain)
    old_by_name = {
        str(workflow.get("name") or ""): workflow
        for workflow in workflows
        if str(workflow.get("name") or "") in OLD_WORKFLOW_NAMES
    }
    if not old_by_name:
        print("  No old Solution / Value or Quote Sent workflow rules found.")
        return True
    ok = True
    for name in OLD_WORKFLOW_NAMES:
        workflow = old_by_name.get(name)
        if workflow:
            ok = _deactivate_workflow(session, api_domain, workflow, dry_run) and ok
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview only; do not write to Zoho.")
    args = parser.parse_args()

    access, api_domain = get_access_token_and_domain()
    session = requests.Session()
    session.headers.update(auth_headers(access))
    session.headers["Content-Type"] = "application/json"

    print(f"Using Zoho API domain: {api_domain}")
    labels = _stage_labels(session, api_domain)
    if NEW_STAGE not in labels:
        print(
            f"Active Stage label {NEW_STAGE!r} not found. "
            "Run provision_deal_stage_picklist.py first.",
            file=sys.stderr,
        )
        return 2

    print("\n== Deal stage migration ==")
    deals = _old_stage_deals(session, api_domain)
    deals_ok = _update_deals_stage(session, api_domain, deals, args.dry_run)

    print("\n== Old workflow cleanup ==")
    workflows_ok = _deactivate_old_workflows(session, api_domain, args.dry_run)

    if not (deals_ok and workflows_ok):
        return 1
    print("\nDone. Live org no longer needs manual old-stage cleanup.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
