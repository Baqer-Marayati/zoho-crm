#!/usr/bin/env python3
"""
Zoho CRM — connectivity and OAuth scope diagnostic for repo automation.

Run from tools/zoho (uses .env and venv):

  ./venv/bin/python zoho_doctor.py
  # or: make zoho-doctor

Why this exists:
- Many "empty list" or mystery 401s are **missing OAuth scopes** on the refresh token.
- `GET /crm/v8/__apis` needs **ZohoCRM.apis.READ**; without it, you cannot even introspect APIs.
- Settings automation (fields, layouts, workflows, custom functions) needs **ZohoCRM.settings.***
  (or `ZohoCRM.settings.ALL`).

This script does not print secrets. It reports HTTP status and short error snippets only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from typing import Any

import requests

from zoho_tokens import auth_headers, get_access_token_and_domain

API = "v8"

KEYWORDS = re.compile(
    r"automation|function|workflow|blueprint|webhook|layout|field|map",
    re.I,
)


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    http_status: int = 0
    scope_hint: str = ""


@dataclass
class Report:
    api_domain: str
    checks: list[Check] = field(default_factory=list)


def _get(
    session: requests.Session, api_domain: str, path: str, version: str = API, **params: Any
) -> requests.Response:
    ver = (version or API).lstrip("v")
    url = f"{api_domain.rstrip('/')}/crm/v{ver}{path}"
    return session.get(url, params=params or None, timeout=120)


def _json(resp: requests.Response) -> Any:
    try:
        return resp.json()
    except json.JSONDecodeError:
        return None


def run_checks(verbose: bool) -> Report:
    access, dom = get_access_token_and_domain()
    session = requests.Session()
    session.headers.update(auth_headers(access))
    session.headers["Content-Type"] = "application/json"

    r: Report = Report(api_domain=dom)
    c: list[Check] = []

    # 1) Module data (ZohoCRM.modules.*) — v2 Leads; v8 often requires a `fields` list
    resp = _get(session, dom, "/Leads", version="2", per_page=1, page=1)
    j = _json(resp)
    c.append(
        Check(
            name="Read module records (Leads, 1 row)",
            ok=resp.ok,
            http_status=resp.status_code,
            detail=("ok" if resp.ok else (resp.text or "")[:400]),
            scope_hint="ZohoCRM.modules.ALL or ZohoCRM.modules.leads.READ" if not resp.ok else "",
        )
    )

    # 2) Settings — modules
    resp = _get(session, dom, "/settings/modules")
    c.append(
        Check(
            name="Settings: list modules",
            ok=resp.ok,
            http_status=resp.status_code,
            detail=("ok" if resp.ok else (resp.text or "")[:400]),
            scope_hint="ZohoCRM.settings.modules.READ or ZohoCRM.settings.ALL" if not resp.ok else "",
        )
    )

    # 3) Automation functions
    resp = _get(session, dom, "/settings/automation/functions", per_page=200, page=1)
    n_fn = 0
    if resp.ok:
        jf = _json(resp) or {}
        n_fn = len(jf.get("functions") or [])
    c.append(
        Check(
            name=f"List custom functions (count={n_fn if resp.ok else 'n/a'})",
            ok=resp.ok,
            http_status=resp.status_code,
            detail=(f"{n_fn} function(s) visible to this token" if resp.ok else (resp.text or "")[:400]),
            scope_hint="ZohoCRM.settings.automation_actions.READ or ZohoCRM.settings.ALL" if not resp.ok else "",
        )
    )

    # 4) Workflow rules (Quotes)
    resp = _get(session, dom, "/settings/automation/workflow_rules", module="Quotes", per_page=5)
    n_wf = 0
    if resp.ok:
        jw = _json(resp) or {}
        n_wf = len(jw.get("workflow_rules") or [])
    c.append(
        Check(
            name=f"List Quotes workflow rules (sample, count={n_wf if resp.ok else 'n/a'})",
            ok=resp.ok,
            http_status=resp.status_code,
            detail=(f"{n_wf} rule(s) in sample" if resp.ok else (resp.text or "")[:400]),
            scope_hint="ZohoCRM.settings.workflow_rules.READ or ZohoCRM.settings.ALL" if not resp.ok else "",
        )
    )

    # 5) __apis (needs ZohoCRM.apis.READ)
    resp = _get(session, dom, "/__apis")
    n_apis = 0
    interesting: list[str] = []
    if resp.ok:
        ja = _json(resp) or {}
        apis = ja.get("__apis") or []
        n_apis = len(apis)
        if verbose and apis:
            for a in apis:
                p = (a or {}).get("path") or ""
                if KEYWORDS.search(p):
                    interesting.append(p)
    c.append(
        Check(
            name=f"List API index /__apis (paths={n_apis if resp.ok else 'n/a'})",
            ok=resp.ok,
            http_status=resp.status_code,
            detail=(
                f"{n_apis} path(s) in index"
                if resp.ok
                else (resp.text or "")[:400]
            ),
            scope_hint="ZohoCRM.apis.READ (required for API discovery)" if not resp.ok else "",
        )
    )

    if resp.ok and verbose and interesting:
        c.append(
            Check(
                name="__apis paths matching automation/fields (subset)",
                ok=True,
                http_status=0,
                detail="\n".join(interesting[:40]),
            )
        )

    # 6) Optional: __apis filter settings scope (only if unfiltered /__apis succeeded)
    if resp.ok:
        filt = json.dumps(
            {
                "field": {"api_name": "operation_types.oauth_scope"},
                "comparator": "equals",
                "value": "settings",
            },
            separators=(",", ":"),
        )
        resp2 = _get(session, dom, "/__apis", filters=filt)
        c.append(
            Check(
                name="__apis filter oauth_scope=settings (sample)",
                ok=resp2.ok,
                http_status=resp2.status_code,
                detail=("ok (filtered)" if resp2.ok else (resp2.text or "")[:200]),
            )
        )

    r.checks = c
    return r


def _print_recommended_grant() -> None:
    print(
        "\n--- Recommended Zoho API Console 'Generate Code' scope string (automation) ---\n"
        "Paste as one comma-separated line when generating a new grant, then re-run connect:\n"
    )
    print(
        "ZohoCRM.modules.ALL,"
        "ZohoCRM.settings.ALL,"
        "ZohoCRM.users.ALL,"
        "ZohoCRM.apis.READ"
    )
    print(
        "\n(You can add/remove granular scopes later; a new grant gives a new refresh token.)\n"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print a subset of __apis paths that match automation/field keywords",
    )
    ap.add_argument(
        "--recommend-scopes",
        action="store_true",
        help="Print recommended OAuth scope list for a fresh grant and exit (no API calls)",
    )
    args = ap.parse_args()
    if args.recommend_scopes:
        _print_recommended_grant()
        return 0

    try:
        report = run_checks(verbose=args.verbose)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1

    print(f"API domain: {report.api_domain}\n")
    for ch in report.checks:
        if ch.ok:
            label = "OK "
        elif ch.name.startswith("List API index") or ch.name.startswith("__apis filter"):
            # Missing ZohoCRM.apis.READ: CRM still works; only discovery is limited
            label = "WARN"
        else:
            label = "FAIL"
        print(f"[{label}] {ch.name}")
        if ch.http_status and ch.name != "__apis paths matching automation/fields (subset)":
            print(f"         HTTP {ch.http_status}")
        d = (ch.detail or "").strip()
        if d and len(d) < 2000:
            for line in d.splitlines()[:8]:
                print(f"         {line}")
        elif d:
            print(f"         {d[:500]}…")
        if ch.scope_hint:
            print(f"         hint: {ch.scope_hint}")
        print()

    def _is_critical(name: str) -> bool:
        return name.startswith(
            (
                "Read module records",
                "Settings: list modules",
                "List custom functions",
                "List Quotes workflow rules",
            )
        )

    critical = [x for x in report.checks if _is_critical(x.name)]
    critical_ok = all(x.ok for x in critical)
    if not critical_ok:
        print("Critical checks failed. Regenerate a grant with broader CRM scopes, then re-run connect_zoho.\n")
        _print_recommended_grant()
        return 1

    apis_ch = next((x for x in report.checks if x.name.startswith("List API index")), None)
    if apis_ch and not apis_ch.ok:
        print("Optional: add ZohoCRM.apis.READ to your next grant so /crm/v8/__apis (API discovery) works.\n")
        _print_recommended_grant()
        return 0

    print("All checks passed (including __apis discovery).\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
