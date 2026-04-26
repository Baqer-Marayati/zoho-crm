#!/usr/bin/env python3
"""
Deploy the Leads Client Script that sets **Address - Country / Region** (`Country`) to Iraq
on the Standard Lead create/edit forms.

This complements `provision_lead_country_iraq_workflow.py`:
- Client Script: makes the form show Iraq immediately.
- Workflow Field Update: enforces Iraq after every save.

Zoho exposes this through an undocumented v8 shape in this org:
  GET/POST /settings/client_script_pages
  GET/POST /settings/client_scripts?client_script_page_id={page_id}

  cd tools/zoho
  ./venv/bin/python provision_lead_country_iraq_client_script.py
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import requests

from zoho_tokens import auth_headers, get_access_token_and_domain

API_VER = "v8"
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
SCRIPT_PATH = REPO_ROOT / "artifacts" / "zoho" / "client_scripts" / "lead_country_iraq_lock.js"

MODULE_API = "Leads"
LAYOUT_NAME = "Standard"
SCRIPT_NAME_PREFIX = "Lead Country Iraq Lock"
SCRIPT_DESCRIPTION = "Set and lock Address Country / Region to Iraq on the Lead form."

PAGE_DEFINITIONS = {
    "module_create": "Create Page",
    "module_edit": "Edit Page",
}


def _crm(session: requests.Session, api_domain: str, method: str, path: str, **kwargs: Any) -> requests.Response:
    url = f"{api_domain.rstrip('/')}/crm/{API_VER}{path}"
    return session.request(method, url, timeout=120, **kwargs)


def _get_token_retry() -> tuple[str, str]:
    delays = (30, 60, 120, 300, 600)
    last: Exception | None = None
    for d in (0, *delays):
        if d:
            print(f"  Token refresh rate-limited; waiting {d}s...", file=sys.stderr)
            time.sleep(d)
        try:
            return get_access_token_and_domain()
        except RuntimeError as e:
            last = e
            msg = str(e).lower()
            if "too many requests" in msg or "access denied" in msg or "400" in msg:
                continue
            raise
    assert last is not None
    raise last


def _module_meta(session: requests.Session, api_domain: str) -> dict[str, Any]:
    r = _crm(session, api_domain, "GET", "/settings/modules")
    r.raise_for_status()
    for module in r.json().get("modules") or []:
        if module.get("api_name") == MODULE_API:
            return module
    raise RuntimeError(f"Module not found: {MODULE_API}")


def _layout_meta(session: requests.Session, api_domain: str) -> dict[str, Any]:
    r = _crm(session, api_domain, "GET", "/settings/layouts", params={"module": MODULE_API})
    r.raise_for_status()
    layouts = r.json().get("layouts") or []
    for layout in layouts:
        if layout.get("status") == "active" and layout.get("name") == LAYOUT_NAME:
            return layout
    for layout in layouts:
        if layout.get("status") == "active":
            return layout
    if layouts:
        return layouts[0]
    raise RuntimeError(f"No layouts returned for {MODULE_API}")


def _page_matches(page: dict[str, Any], definition: str, module_id: str, layout_id: str) -> bool:
    selectors = page.get("selectors") or {}
    mod = selectors.get("module") or {}
    layout = selectors.get("layout") or {}
    return (
        page.get("definition") == definition
        and str(mod.get("id", "")) == str(module_id)
        and str(layout.get("id", "")) == str(layout_id)
    )


def _list_pages(session: requests.Session, api_domain: str) -> list[dict[str, Any]]:
    r = _crm(session, api_domain, "GET", "/settings/client_script_pages")
    r.raise_for_status()
    return r.json().get("client_script_pages") or []


def _ensure_page(
    session: requests.Session,
    api_domain: str,
    definition: str,
    module: dict[str, Any],
    layout: dict[str, Any],
    dry_run: bool,
) -> str | None:
    module_id = str(module["id"])
    layout_id = str(layout["id"])
    for page in _list_pages(session, api_domain):
        if _page_matches(page, definition, module_id, layout_id):
            return str(page["id"])

    body = {
        "client_script_pages": [
            {
                "definition": definition,
                "selectors": {
                    "module": {
                        "api_name": MODULE_API,
                        "id": module_id,
                    },
                    "layout": {
                        "api_name": layout.get("api_name") or "Standard__s",
                        "id": layout_id,
                    },
                },
            }
        ]
    }
    if dry_run:
        print("--- dry-run POST /settings/client_script_pages ---")
        print(json.dumps(body, indent=2))
        return "<new_client_script_page_id>"

    r = _crm(session, api_domain, "POST", "/settings/client_script_pages", json=body)
    if not r.ok:
        print(f"  POST client_script_pages HTTP {r.status_code}: {r.text[:4000]}", file=sys.stderr)
        return None
    for item in r.json().get("client_script_pages") or []:
        details = item.get("details") or {}
        if item.get("code") == "SUCCESS" and details.get("id"):
            return str(details["id"])
        if item.get("id"):
            return str(item["id"])

    # Some Zoho responses only return a generic success; re-read pages.
    for page in _list_pages(session, api_domain):
        if _page_matches(page, definition, module_id, layout_id):
            return str(page["id"])
    print(json.dumps(r.json(), indent=2)[:3000], file=sys.stderr)
    return None


def _list_scripts(session: requests.Session, api_domain: str, page_id: str) -> list[dict[str, Any]]:
    r = _crm(
        session,
        api_domain,
        "GET",
        "/settings/client_scripts",
        params={"client_script_page_id": page_id},
    )
    if not r.ok:
        print(f"  GET client_scripts page={page_id} HTTP {r.status_code}: {r.text[:3000]}", file=sys.stderr)
        return []
    return r.json().get("client_scripts") or []


def _script_body(page_id: str, name: str, source: str, source_key: str) -> dict[str, Any]:
    script = {
        "name": name,
        "description": SCRIPT_DESCRIPTION,
        "client_script_page": {"id": page_id},
        "event_info": {
            "name": "onLoad",
            "type": "page",
            "arguments": None,
        },
        "state": "active",
        source_key: source,
    }
    return {"client_scripts": [script]}


def _upsert_script(
    session: requests.Session,
    api_domain: str,
    page_id: str,
    name: str,
    source: str,
    dry_run: bool,
) -> str | None:
    existing_id = None
    for script in _list_scripts(session, api_domain, page_id):
        if (script.get("name") or "").strip() == name:
            existing_id = str(script["id"])
            break

    if dry_run:
        print(f"--- dry-run {'PUT' if existing_id else 'POST'} /settings/client_scripts ---")
        print(json.dumps(_script_body(page_id, name, source, "script"), indent=2)[:5000])
        return existing_id or "<new_client_script_id>"

    method = "PUT" if existing_id else "POST"
    path = f"/settings/client_scripts/{existing_id}" if existing_id else "/settings/client_scripts"
    last_text = ""
    for source_key in ("script", "source", "source_code", "code"):
        body = _script_body(page_id, name, source, source_key)
        r = _crm(session, api_domain, method, path, json=body)
        last_text = r.text
        if r.ok:
            for item in r.json().get("client_scripts") or []:
                details = item.get("details") or {}
                if item.get("code") == "SUCCESS" and details.get("id"):
                    return str(details["id"])
                if item.get("id"):
                    return str(item["id"])
            if existing_id:
                return existing_id
        # Try the alternate source key only for payload-shape errors.
        if r.status_code not in (400, 422):
            break
    print(f"  {method} client_scripts HTTP failed: {last_text[:5000]}", file=sys.stderr)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="Print API payloads only.")
    args = ap.parse_args()

    if not SCRIPT_PATH.is_file():
        print(f"Client script source not found: {SCRIPT_PATH}", file=sys.stderr)
        return 1
    source = SCRIPT_PATH.read_text(encoding="utf-8").rstrip() + "\n"

    try:
        access, api_domain = _get_token_retry()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1

    session = requests.Session()
    session.headers.update({**auth_headers(access), "Content-Type": "application/json"})

    try:
        module = _module_meta(session, api_domain)
        layout = _layout_meta(session, api_domain)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1

    print(f"  Module: {MODULE_API} (id={module['id']})")
    print(f"  Layout: {layout.get('name')} (id={layout['id']})")

    ok = True
    for definition, page_label in PAGE_DEFINITIONS.items():
        script_name = f"{SCRIPT_NAME_PREFIX} - {page_label} OnLoad"
        page_id = _ensure_page(session, api_domain, definition, module, layout, args.dry_run)
        if not page_id:
            ok = False
            continue
        print(f"  Page:   {page_label} {definition} (id={page_id})")
        script_id = _upsert_script(session, api_domain, page_id, script_name, source, args.dry_run)
        if not script_id:
            ok = False
            continue
        print(f"  Script: {script_name} (id={script_id})")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
