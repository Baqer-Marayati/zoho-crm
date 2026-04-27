#!/usr/bin/env python3
"""
Create / verify Zoho CRM automation for dynamic quote-line descriptions.

The workflow runs on Quotes (create/edit), iterates the Quoted_Items subform, and updates each
line's standard Description from Product + Model / speed + Configuration 1 + Configuration 2.
Product master data is never modified.

API notes:
  - This script verifies the required Quoted_Items fields before creating automation.
  - Many Zoho orgs reject raw Deluge uploads through POST /settings/automation/functions. If that
    happens, create the function once in the UI with the same name and re-run this script; it will
    find the function and attach the workflow.

Usage:
  cd tools/zoho
  ./venv/bin/python provision_quote_line_description_workflow.py --dry-run
  ./venv/bin/python provision_quote_line_description_workflow.py
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
DELUGE_PATH = REPO_ROOT / "artifacts" / "zoho" / "deluge" / "quoted_items_build_line_description.deluge"

FUNCTION_DISPLAY_NAME = "quoted_items_build_line_description"
WF_RULE_NAME = "Quote build configured line descriptions"
FUNCTION_HOME_MODULE_API = "Quotes"
WF_MODULE_API = "Quotes"
LINE_MODULE_API = "Quoted_Items"

REQUIRED_LINE_FIELDS = {
    "Product_Name": "Product Name",
    "Description": "Description",
    "Machine_SKU": "Product (Machine)",
    "Model_speed": "Model / speed",
    "Finisher_line": "Configuration 1",
    "POD_paper_module_line": "Configuration 2",
}


def _crm(
    session: requests.Session, api_domain: str, method: str, path: str, **kwargs
) -> requests.Response:
    url = f"{api_domain.rstrip('/')}/crm/{API_VER}{path}"
    return session.request(method, url, timeout=120, **kwargs)


def _strip_deluge_comments(src: str) -> str:
    out: list[str] = []
    for line in src.splitlines():
        if line.strip().startswith("//"):
            continue
        out.append(line)
    return "\n".join(out).strip() + "\n"


def _get_token_retry() -> tuple[str, str]:
    delays = (2, 10, 45, 120, 300)
    last_err: Exception | None = None
    for delay in delays:
        try:
            return get_access_token_and_domain()
        except RuntimeError as e:
            last_err = e
            msg = str(e).lower()
            if "too many requests" in msg or "400" in msg:
                print(f"  Token refresh rate-limited; waiting {delay}s...", file=sys.stderr)
                time.sleep(delay)
                continue
            raise
    assert last_err is not None
    raise last_err


def _module_meta(session: requests.Session, api_domain: str, api_name: str) -> dict:
    r = _crm(session, api_domain, "GET", "/settings/modules")
    r.raise_for_status()
    for module in r.json().get("modules") or []:
        if module.get("api_name") == api_name:
            return module
    raise RuntimeError(f"Module not found: {api_name}")


def _field_map_by_api(session: requests.Session, api_domain: str, module: str) -> dict[str, dict]:
    r = _crm(
        session,
        api_domain,
        "GET",
        "/settings/fields",
        params={"module": module, "type": "all"},
    )
    if not r.ok:
        raise RuntimeError(f"GET fields {module} HTTP {r.status_code}: {r.text[:2000]}")
    return {
        f.get("api_name"): f
        for f in r.json().get("fields") or []
        if f.get("api_name")
    }


def _verify_line_fields(session: requests.Session, api_domain: str) -> bool:
    fields = _field_map_by_api(session, api_domain, LINE_MODULE_API)
    missing: list[str] = []
    for api_name, label in REQUIRED_LINE_FIELDS.items():
        field = fields.get(api_name)
        if not field:
            missing.append(f"{api_name} ({label})")
            continue
        print(
            f"  OK field {LINE_MODULE_API}.{api_name}: "
            f"{field.get('field_label')!r} [{field.get('data_type')}]"
        )
    if missing:
        print(
            "  Missing required Quoted_Items fields: " + ", ".join(missing),
            file=sys.stderr,
        )
        print(
            "  Run provision_quoted_line_dependencies.py first, then re-run this script.",
            file=sys.stderr,
        )
        return False
    desc_type = (fields.get("Description") or {}).get("data_type")
    if desc_type != "textarea":
        print(
            f"  Warning: Quoted_Items.Description data_type is {desc_type!r}, expected textarea.",
            file=sys.stderr,
        )
    return True


def _find_function_id(
    session: requests.Session, api_domain: str, name: str
) -> str | None:
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
            names = {
                (fn.get("name") or "").strip(),
                (fn.get("api_name") or "").strip(),
                (fn.get("display_name") or fn.get("Display_Name") or "").strip(),
            }
            if name in names:
                fid = fn.get("id")
                if fid:
                    return str(fid)
        if not (data.get("info") or {}).get("more_records"):
            return None
        page += 1


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
        params={"module": module_api, "filter": filt, "per_page": 200},
    )
    if not r.ok:
        print(f"  GET workflow_rules HTTP {r.status_code}: {r.text[:800]}", file=sys.stderr)
        return None
    for workflow in r.json().get("workflow_rules") or []:
        if workflow.get("name") == name:
            wid = workflow.get("id")
            return str(wid) if wid else None
    return None


def _create_function_via_api(
    session: requests.Session,
    api_domain: str,
    quotes_mod: dict,
    deluge_body: str,
    dry_run: bool,
) -> str | None:
    payload = {
        "functions": [
            {
                "name": FUNCTION_DISPLAY_NAME,
                "module": {
                    "api_name": FUNCTION_HOME_MODULE_API,
                    "id": str(quotes_mod["id"]),
                },
                "language": "deluge",
                "function": deluge_body,
            }
        ]
    }
    if dry_run:
        print("--- dry-run POST /settings/automation/functions ---")
        print(json.dumps(payload, indent=2)[:6000])
        return "dry_run"
    r = _crm(
        session,
        api_domain,
        "POST",
        "/settings/automation/functions",
        json=payload,
    )
    if not r.ok:
        print(f"  POST functions HTTP {r.status_code}: {r.text[:4000]}", file=sys.stderr)
        return None
    try:
        resp = r.json()
    except json.JSONDecodeError:
        print(r.text[:2000], file=sys.stderr)
        return None
    for item in resp.get("functions") or []:
        details = (item or {}).get("details") or {}
        fid = details.get("id") or item.get("id")
        if item.get("code") == "SUCCESS" and fid:
            return str(fid)
    print(json.dumps(resp, indent=2)[:3000], file=sys.stderr)
    return None


def _build_workflow_payload(quote_mod: dict, function_id: str) -> dict:
    quote_id = str(quote_mod["id"])
    return {
        "workflow_rules": [
            {
                "execute_when": {
                    "type": "create_or_edit",
                    "details": {
                        "trigger_module": {
                            "api_name": WF_MODULE_API,
                            "id": quote_id,
                        },
                        "repeat": True,
                    },
                },
                "module": {
                    "api_name": WF_MODULE_API,
                    "id": quote_id,
                },
                "name": WF_RULE_NAME,
                "description": (
                    "Builds each quote line Description from Product, Model/speed, "
                    "Configuration 1, and Configuration 2. Product records are not modified."
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
        print(f"  POST workflow_rules HTTP {r.status_code}: {r.text[:6000]}", file=sys.stderr)
        return None
    try:
        resp = r.json()
    except json.JSONDecodeError:
        print(r.text[:3000], file=sys.stderr)
        return None
    for workflow in resp.get("workflow_rules") or []:
        if workflow.get("code") == "SUCCESS":
            wid = (workflow.get("details") or {}).get("id")
            if wid:
                return str(wid)
    print(json.dumps(resp, indent=2)[:4000], file=sys.stderr)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print payloads only.")
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Print Deluge + sample payloads without Zoho API calls.",
    )
    parser.add_argument(
        "--function-id",
        default="",
        help="Use this existing function id and skip function create/lookup.",
    )
    parser.add_argument(
        "--skip-create-function",
        action="store_true",
        help="Do not POST /settings/automation/functions; use --function-id or lookup by name.",
    )
    parser.add_argument(
        "--deluge-file",
        type=Path,
        default=DELUGE_PATH,
        help="Path to Deluge source.",
    )
    args = parser.parse_args()

    if not args.deluge_file.is_file():
        print(f"Deluge file not found: {args.deluge_file}", file=sys.stderr)
        return 1
    deluge_body = _strip_deluge_comments(args.deluge_file.read_text(encoding="utf-8"))
    if not deluge_body.strip():
        print("Deluge file is empty after comment strip.", file=sys.stderr)
        return 1

    if args.print_only:
        print("=== Deluge body ===\n")
        print(deluge_body)
        print("\n=== Function payload shape ===\n")
        print(
            json.dumps(
                {
                    "functions": [
                        {
                            "name": FUNCTION_DISPLAY_NAME,
                            "module": {"api_name": FUNCTION_HOME_MODULE_API, "id": "<Quotes module id>"},
                            "language": "deluge",
                            "function": deluge_body,
                        }
                    ]
                },
                indent=2,
            )[:12000]
        )
        print("\n=== Workflow payload shape ===\n")
        print(_build_workflow_payload({"id": "<Quotes module id>"}, "<function id>"))
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
        _module_meta(session, api_domain, LINE_MODULE_API)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1

    print(f"  Function home module: {FUNCTION_HOME_MODULE_API} (id={quotes['id']})")
    print(f"  Workflow module:      {WF_MODULE_API} (id={quotes['id']})")
    print("\n=== Verify line fields ===")
    if not _verify_line_fields(session, api_domain):
        return 1

    function_id: str | None = None
    if args.function_id.strip():
        function_id = args.function_id.strip()
        print(f"  Using --function-id={function_id}")
    else:
        function_id = _find_function_id(session, api_domain, FUNCTION_DISPLAY_NAME)
        if function_id:
            print(f"  Custom function found: {FUNCTION_DISPLAY_NAME} (id={function_id})")

    if not function_id and not args.skip_create_function:
        function_id = _create_function_via_api(
            session,
            api_domain,
            quotes,
            deluge_body,
            args.dry_run,
        )
        if function_id and function_id != "dry_run" and not args.dry_run:
            print(f"  Created function id: {function_id}")

    if args.dry_run and (not function_id or function_id == "dry_run"):
        function_id = "DRYRUN_PLACEHOLDER"
    elif not function_id or function_id == "dry_run":
        print(
            f"  No custom function {FUNCTION_DISPLAY_NAME!r} in the org, and the API did not "
            "create one. Create it in Zoho UI, paste the Deluge artifact, associate it with "
            f"Quotes, then re-run this script or pass --function-id=<id>.",
            file=sys.stderr,
        )
        return 1

    workflow_id = _find_workflow_by_name(
        session,
        api_domain,
        WF_MODULE_API,
        WF_RULE_NAME,
    )
    if workflow_id:
        print(f"  Workflow rule already exists: {WF_RULE_NAME!r} (id={workflow_id})")
        return 0

    workflow_body = _build_workflow_payload(quotes, function_id)
    workflow_id = _create_workflow(session, api_domain, workflow_body, args.dry_run)
    if not workflow_id:
        return 1
    if workflow_id != "dry_run":
        print(f"  Created workflow rule id: {workflow_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
