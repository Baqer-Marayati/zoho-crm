#!/usr/bin/env python3
"""
Create / update Zoho CRM automation for quote lines:
  1) Custom function (Deluge) that iterates a Quote's subform and sets Machine SKU on every line.
  2) Workflow rule on **Quotes** (create or edit, every time) that runs the function above with
     `quoteId = ${Quotes.id}`.

The Deluge source file lives at:
  ../../artifacts/zoho/deluge/quoted_items_sync_machine_sku.deluge

API notes:
  - POST /settings/automation/functions in many orgs rejects the raw `function` body
    (INVALID_DATA on `arguments.function`). The Deluge function must be created **once** in
    the Zoho UI (paste the artifact above; argument: `quoteId` String → Quotes.Quote Id).
    This script then finds it by name and attaches the workflow.
  - The workflow is registered on **Quotes** (not the Quoted_Items subform) because subform
    modules are not valid workflow trigger modules in the public API and the new function
    handles every line in one pass.
  - OAuth: ZohoCRM.settings.workflow_rules.CREATE (or .ALL).

Usage:
  cd tools/zoho
  ./venv/bin/python provision_quoted_line_machine_sku_workflow.py --dry-run
  ./venv/bin/python provision_quoted_line_machine_sku_workflow.py

[1] https://www.zoho.com/crm/developer/docs/api/v8/
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests

from zoho_tokens import auth_headers, get_access_token_and_domain

API_VER = "v8"
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DELUGE_PATH = REPO_ROOT / "artifacts" / "zoho" / "deluge" / "quoted_items_sync_machine_sku.deluge"

FUNCTION_DISPLAY_NAME = "quoted_items_sync_machine_sku"
WF_RULE_NAME = "Quote sync Machine SKU on lines"
# Function lives under Quotes; workflow also fires on Quotes (every create/edit).
FUNCTION_HOME_MODULE_API = "Quotes"
WF_MODULE_API = "Quotes"
LINE_MODULE_API = "Quoted_Items"


def _crm(
    session: requests.Session, api_domain: str, method: str, path: str, **kwargs
) -> requests.Response:
    url = f"{api_domain.rstrip('/')}/crm/{API_VER}{path}"
    return session.request(method, url, timeout=120, **kwargs)


def _strip_deluge_comments(src: str) -> str:
    out: list[str] = []
    for line in src.splitlines():
        s = line.strip()
        if s.startswith("//"):
            continue
        out.append(line)
    return "\n".join(out).strip() + "\n"


def _get_token_retry() -> tuple[str, str]:
    """Refresh access token; back off on Zoho rate limiting."""
    delays = (2, 10, 45, 120, 300)
    last_err: Exception | None = None
    for d in delays:
        try:
            return get_access_token_and_domain()
        except RuntimeError as e:
            last_err = e
            msg = str(e)
            if "too many requests" in msg.lower() or "400" in msg:
                print(f"  Token refresh rate-limited; waiting {d}s…", file=sys.stderr)
                time.sleep(d)
                continue
            raise
    assert last_err is not None
    raise last_err


def _module_meta(session: requests.Session, api_domain: str, api_name: str) -> dict:
    r = _crm(session, api_domain, "GET", "/settings/modules")
    r.raise_for_status()
    for m in r.json().get("modules") or []:
        if m.get("api_name") == api_name:
            return m
    raise RuntimeError(f"Module not found: {api_name}")


def _field_id(
    session: requests.Session, api_domain: str, module: str, api_name: str
) -> tuple[str, str]:
    r = _crm(
        session, api_domain, "GET", "/settings/fields", params={"module": module}
    )
    r.raise_for_status()
    for f in r.json().get("fields") or []:
        if f.get("api_name") == api_name:
            return str(f.get("id", "")), f.get("field_label") or api_name
    raise RuntimeError(f"Field {module}.{api_name} not found")


def _find_function_id(
    session: requests.Session, api_domain: str, name: str
) -> str | None:
    """Match by `name` or `api_name` (Zoho may expose either in list responses)."""
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
            print(f"  GET functions HTTP {r.status_code}: {r.text[:800]}", file=sys.stderr)
            return None
        data = r.json()
        for fn in data.get("functions") or []:
            n = (fn.get("name") or "").strip()
            an = (fn.get("api_name") or "").strip()
            disp = (fn.get("display_name") or fn.get("Display_Name") or "").strip()
            if n == name or an == name or disp == name:
                fid = fn.get("id")
                if fid:
                    return str(fid)
        info = data.get("info") or {}
        if not info.get("more_records"):
            break
        page += 1
    return None


def _find_workflow_by_name(
    session: requests.Session, api_domain: str, module_api: str, name: str
) -> str | None:
    filt = json.dumps(
        {"field": {"api_name": "name"}, "comparator": "contains", "value": name}
    )
    r = _crm(
        session,
        api_domain,
        "GET",
        "/settings/automation/workflow_rules",
        params={
            "module": module_api,
            "filter": filt,
            "per_page": 200,
        },
    )
    if not r.ok:
        return None
    for w in r.json().get("workflow_rules") or []:
        if w.get("name") == name:
            return str(w.get("id", ""))
    return None


def _create_function_via_api(
    session: requests.Session,
    api_domain: str,
    quotes_mod: dict,
    deluge_body: str,
    dry_run: bool,
) -> str | None:
    """
    POST raw Deluge to /settings/automation/functions.

    As of 2026-04, many orgs return INVALID_DATA for the `function` string (Zoho-side
    validation of `arguments.function`). In that case, create the function once in
    the CRM UI (paste the .deluge file) and re-run; we will find it by name via GET.
    """
    mid = str(quotes_mod["id"])
    payload = {
        "functions": [
            {
                "name": FUNCTION_DISPLAY_NAME,
                "module": {"api_name": FUNCTION_HOME_MODULE_API, "id": mid},
                "language": "deluge",
                "function": deluge_body,
            }
        ]
    }
    if dry_run:
        print("--- dry-run POST /settings/automation/functions ---")
        print(json.dumps(payload, indent=2)[:4000])
        return "dry_run"
    r = _crm(
        session, api_domain, "POST", "/settings/automation/functions", json=payload
    )
    if not r.ok:
        print(
            f"  POST functions HTTP {r.status_code}: {r.text[:4000]}",
            file=sys.stderr,
        )
        return None
    try:
        resp = r.json()
    except json.JSONDecodeError:
        print(r.text[:2000], file=sys.stderr)
        return None
    items = resp.get("functions") or []
    for item in items:
        det = (item or {}).get("details") or {}
        fid = det.get("id")
        if item.get("code") == "SUCCESS" and fid:
            return str(fid)
    print(json.dumps(resp, indent=2)[:3000], file=sys.stderr)
    return None


def _build_workflow_payload(
    quote_mod: dict,
    function_id: str,
) -> dict:
    """Quote-level workflow, every create/edit, no condition; runs the function."""
    qid = str(quote_mod["id"])
    return {
        "workflow_rules": [
            {
                "execute_when": {
                    "type": "create_or_edit",
                    "details": {
                        "trigger_module": {
                            "api_name": WF_MODULE_API,
                            "id": qid,
                        },
                        "repeat": True,
                    },
                },
                "module": {
                    "api_name": WF_MODULE_API,
                    "id": qid,
                },
                "name": WF_RULE_NAME,
                "description": (
                    "Iterates Quoted_Items: sets Product (Machine) from Product when only the "
                    "lookup is set, or sets the Product lookup from the Product (Machine) picklist "
                    "so Model/speed and Config 1/2 map_dependency picklists stay aligned."
                ),
                "status": {"active": True},
                "conditions": [
                    {
                        "sequence_number": 1,
                        "instant_actions": {
                            "actions": [
                                {
                                    "type": "functions",
                                    "id": function_id,
                                }
                            ]
                        },
                    }
                ],
            }
        ]
    }


def _create_workflow(
    session: requests.Session, api_domain: str, body: dict, dry_run: bool
) -> str | None:
    if dry_run:
        print("--- dry-run POST /settings/automation/workflow_rules ---")
        print(json.dumps(body, indent=2)[:8000])
        return "dry_run"
    r = _crm(
        session,
        api_domain,
        "POST",
        "/settings/automation/workflow_rules",
        json=body,
    )
    if not r.ok:
        print(
            f"  POST workflow_rules HTTP {r.status_code}: {r.text[:6000]}",
            file=sys.stderr,
        )
        return None
    try:
        resp = r.json()
    except json.JSONDecodeError:
        print(r.text[:3000], file=sys.stderr)
        return None
    for wr in resp.get("workflow_rules") or []:
        if wr.get("code") == "SUCCESS":
            did = (wr.get("details") or {}).get("id")
            if did:
                return str(did)
    print(json.dumps(resp, indent=2)[:4000], file=sys.stderr)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print payloads only; do not call POST.",
    )
    ap.add_argument(
        "--print-only",
        action="store_true",
        help="Print Deluge (comment-stripped) and sample JSON only; no Zoho API calls.",
    )
    ap.add_argument(
        "--function-id",
        type=str,
        default="",
        help="Use this custom function id (skip create + skip lookup by name).",
    )
    ap.add_argument(
        "--skip-create-function",
        action="store_true",
        help="Do not POST /settings/automation/functions; use --function-id or list by name.",
    )
    ap.add_argument(
        "--deluge-file",
        type=Path,
        default=DELUGE_PATH,
        help="Path to Deluge source (default: repo artifact).",
    )
    args = ap.parse_args()
    if not args.deluge_file.is_file():
        print(f"Deluge file not found: {args.deluge_file}", file=sys.stderr)
        return 1

    raw = args.deluge_file.read_text(encoding="utf-8")
    deluge_body = _strip_deluge_comments(raw)
    if not deluge_body.strip():
        print("Deluge file is empty after comment strip.", file=sys.stderr)
        return 1

    if args.print_only:
        print("=== Deluge body (for POST /settings/automation/functions) ===\n")
        print(deluge_body)
        pl_fn = {
            "functions": [
                {
                    "name": FUNCTION_DISPLAY_NAME,
                    "module": {
                        "api_name": "Quotes",
                        "id": "<get from GET /settings/modules>",
                    },
                    "language": "deluge",
                    "function": deluge_body,
                }
            ]
        }
        pl_wf = _build_workflow_payload(
            {
                "id": "<Quotes module id>",
                "api_name": WF_MODULE_API,
            },
            "<function id from create response>",
        )
        print("\n=== Sample POST /settings/automation/functions ===\n")
        print(json.dumps(pl_fn, indent=2)[:12000])
        print("\n=== Sample POST /settings/automation/workflow_rules ===\n")
        print(json.dumps(pl_wf, indent=2)[:12000])
        print(
            "\n(Replace placeholders, or run this script without --print-only when "
            "OAuth is not rate-limited.)",
            file=sys.stderr,
        )
        return 0

    try:
        access, api_domain = _get_token_retry()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1

    session = requests.Session()
    session.headers.update(auth_headers(access))
    session.headers["Content-Type"] = "application/json"

    try:
        quotes = _module_meta(session, api_domain, FUNCTION_HOME_MODULE_API)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1

    print(f"  Function home module: {FUNCTION_HOME_MODULE_API} (id={quotes['id']})")
    print(f"  Workflow module:      {WF_MODULE_API} (id={quotes['id']})")

    function_id: str | None = None
    if (args.function_id or "").strip():
        function_id = args.function_id.strip()
        print(f"  Using --function-id={function_id}")
    else:
        existing_fn = _find_function_id(session, api_domain, FUNCTION_DISPLAY_NAME)
        if existing_fn:
            function_id = existing_fn
            print(
                f"  Custom function found by name: {FUNCTION_DISPLAY_NAME} (id={function_id})"
            )
    if not function_id and not args.skip_create_function:
        function_id = _create_function_via_api(
            session, api_domain, quotes, deluge_body, args.dry_run
        )
        if function_id and function_id not in ("dry_run",) and not args.dry_run:
            print(f"  Created function id: {function_id}")
    if args.dry_run and (not function_id or function_id == "dry_run"):
        function_id = "DRYRUN_PLACEHOLDER"
    elif not function_id or function_id == "dry_run":
        print(
            f"  No custom function {FUNCTION_DISPLAY_NAME!r} in the org, and the API did not "
            "create one. Create it in Zoho: Setup → Automation → Functions (paste the "
            f"Deluge from {args.deluge_file}; associate with **Quotes** or the line module). "
            "Then re-run, or use --function-id=… or --skip-create-function after creating it in UI.\n"
            "  If the function exists in the UI but GET /settings/automation/functions is empty, "
            "run `./venv/bin/python zoho_doctor.py` (OAuth scopes) and pass the id from the "
            "function URL: --function-id=<id>.",
            file=sys.stderr,
        )
        return 1

    ex_wf = _find_workflow_by_name(
        session, api_domain, WF_MODULE_API, WF_RULE_NAME
    )
    if ex_wf:
        print(
            f"  Workflow rule already exists: {WF_RULE_NAME!r} (id={ex_wf}). "
            "Delete or rename it in Zoho to recreate, or update manually."
        )
        return 0

    wf_body = _build_workflow_payload(quotes, function_id)
    wf_id = _create_workflow(session, api_domain, wf_body, args.dry_run)
    if not wf_id:
        return 1
    if wf_id and wf_id != "dry_run":
        print(f"  Created workflow rule id: {wf_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
