#!/usr/bin/env python3
"""
List / update Zoho **Client Script** for **Quotes** via
  GET /PUT  {api-domain}/crm/v8/settings/client_scripts/Quotes

Source file: ../../artifacts/zoho/client_scripts/quote_reference_autofill.js

**Org reality (Zoho v8, 2026):** this endpoint often returns **401 OAUTH_SCOPE_MISMATCH** unless the
Self Client includes a **client_scripts** settings scope. `ZohoCRM.settings.ALL` in the public scope
list does not enumerate `client_scripts`; the API Console may show it as a separate checkbox. Add
something like **ZohoCRM.settings.client_scripts.ALL** (or READ+UPDATE) and re-issue the refresh
token via `connect_zoho.py` / `exchange_grant.py`, then re-run this script.

**POST is not available** for this path (`INVALID_REQUEST_METHOD` for POST) — use GET + PUT when your
org allows it.

**Field layout (drag to bottom / hide):** not achievable via public REST; Zoho blocks `_delete` on
system-mandatory `Subject` in layouts.

  cd tools/zoho
  ./venv/bin/python provision_quote_client_script.py --get-only
  ./venv/bin/python provision_quote_client_script.py
  ./venv/bin/python provision_quote_client_script.py --dry-run
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

import requests

from zoho_tokens import auth_headers, get_access_token_and_domain

API_VER = "v8"
MODULE = "Quotes"
SCRIPT_KEY = "quote_reference_autofill"
SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "artifacts"
    / "zoho"
    / "client_scripts"
    / "quote_reference_autofill.js"
)


def _session():
    try:
        access, dom = get_access_token_and_domain()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return None, None
    s = requests.Session()
    s.headers.update({**auth_headers(access), "Content-Type": "application/json"})
    return s, dom


def _load_script() -> str:
    t = SCRIPT_PATH.read_text(encoding="utf-8")
    if not t.strip():
        raise SystemExit(f"Empty script: {SCRIPT_PATH}")
    return t.rstrip() + "\n"


def _set_script_in_entry(entry: dict, source: str) -> None:
    for k in ("script", "source", "source_code", "code", "javascript", "client_script_source"):
        if k in entry or k == "script":
            entry[k] = source
            return
    entry["script"] = source


def _find_list_key(payload: dict) -> tuple[str, list] | None:
    for k in (
        "client_scripts",
        "Client_Scripts",
        "clientScript",
    ):
        v = payload.get(k)
        if isinstance(v, list):
            return k, v
    if isinstance(payload.get("data"), list):
        return "data", payload["data"]
    return None


def _merge_client_script(
    get_payload: dict, display_name: str, source: str
) -> dict | None:
    p = copy.deepcopy(get_payload)
    key_list = _find_list_key(p)
    if not key_list:
        return None
    key, lst = key_list
    updated = [dict(x) for x in lst]
    found = False
    for i, ent in enumerate(updated):
        name = (ent.get("name") or ent.get("display_name") or "").strip()
        if display_name in name or name == display_name:
            _set_script_in_entry(ent, source)
            updated[i] = ent
            found = True
            break
    if not found:
        new_e: dict = {"name": display_name}
        _set_script_in_entry(new_e, source)
        updated.append(new_e)
    p[key] = updated
    return p


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--get-only", action="store_true", help="GET only; print JSON (or 401 help)"
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="With successful GET, print would-be PUT body but do not call PUT",
    )
    args = ap.parse_args()

    tok = _session()
    if not tok[0]:
        return 1
    s, dom = tok

    path = f"/settings/client_scripts/{MODULE}"
    url = f"{dom.rstrip('/')}/crm/{API_VER}{path}"
    r = s.get(url, timeout=120)
    print(f"GET {path} → {r.status_code}", flush=True)
    if r.status_code == 401:
        print(
            "  401: add a client_scripts OAuth scope for CRM Settings, regenerate refresh token, retry.\n"
            "  See script docstring; API Console may label it under Developer / Client Script.",
            file=sys.stderr,
            flush=True,
        )
        return 1
    if not r.ok:
        print((r.text or "")[:4000], file=sys.stderr)
        return 1
    try:
        data = r.json()
    except json.JSONDecodeError:
        print((r.text or "")[:4000], file=sys.stderr)
        return 1

    if args.get_only:
        print(json.dumps(data, indent=2)[:12000])
        return 0

    src = _load_script()
    merged = _merge_client_script(data, SCRIPT_KEY, src)
    if merged is None:
        print(
            "  Could not find a list in GET JSON; merge logic needs the real response shape.",
            file=sys.stderr,
        )
        print(json.dumps(data, indent=2)[:8000], file=sys.stderr)
        return 1

    if args.dry_run:
        print("--- would PUT (first 2k) ---")
        print(json.dumps(merged, indent=2)[:2000])
        return 0

    r2 = s.put(url, json=merged, timeout=120)
    print(f"PUT {path} → {r2.status_code}")
    print((r2.text or "")[:8000])
    return 0 if r2.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
