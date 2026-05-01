#!/usr/bin/env python3
"""
Deploy **Deals → progressive field visibility** Client Script from:
  ../../artifacts/zoho/client_scripts/deal_stage_field_visibility.js

Target: **Standard** Deals layout — hides late-stage fields while **Stage = Qualification**,
then reveals groups by pipeline position (same labels as `pipelines_seed.json`).

Historical public/API probe (v8, same pattern as `provision_lead_country_iraq_client_script.py`):
  GET  /settings/client_script_pages
  POST /settings/client_script_pages   (may return INVALID_REQUEST_METHOD in some orgs/builds)
  GET  /settings/client_scripts?client_script_page_id={page_id}
  POST /settings/client_scripts  |  PUT /settings/client_scripts/{id}

Org reality (2026-04-30): the working no-manual path used the admin browser session,
not the public v8 endpoint family. Use Safari with JavaScript from Apple Events enabled
and call Zoho's internal endpoints:

  GET/PUT  /crm/v2.2/settings/cscript_pages
  GET/POST/PUT /crm/v2.2/settings/cscript_snippets

Required browser-session headers:
  X-ZCSRF-TOKEN: crmcsrfparam=<crmcsr cookie>
  X-CRM-ORG: <org id>

Do not upload raw JS as `async_code`: compile the source with Zoho's own in-page helper:
  Lyte.registeredMixins['crm-cscript-global-mixin'].compile_script(source, [])

Then send `content.source_code`, compiled `content.async_code`, and `content.source_map`.
Client Script pages also require core static resources (`ZRC-1.0`, `Kernel`, `ZDK-1.0`,
`DotSDK-2.0`, `Concluder`), otherwise runtime state reports:
  issue with cscript info/static resource

For Deals, discover selector values from the UI because Zoho can internally route the
module as `Potentials`. Details: `docs/zoho/AUTOMATION-STACK.md` §4.1.

Events to attach (same JS for each row):
  - Deals → Create Page (Standard) → Page → onLoad
  - Deals → Create Page (Standard) → Page → onChange
  - Deals → Edit Page (Standard)   → Page → onLoad
  - Deals → Edit Page (Standard)   → Page → onChange

  cd tools/zoho
  ./venv/bin/python provision_deals_stage_visibility_client_script.py
  ./venv/bin/python provision_deals_stage_visibility_client_script.py --dry-run
  ./venv/bin/python provision_deals_stage_visibility_client_script.py --print-source
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import requests

from zoho_tokens import auth_headers, get_access_token_and_domain

API_VER = "v8"
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
SCRIPT_PATH = REPO_ROOT / "artifacts" / "zoho" / "client_scripts" / "deal_stage_field_visibility.js"

MODULE_API = "Deals"
LAYOUT_NAME = "Standard"
SCRIPT_BASENAME = "Deal stage field visibility"


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
        print(
            f"  POST client_script_pages HTTP {r.status_code}: {r.text[:4000]}\n"
            "  If this is INVALID_REQUEST_METHOD, create the Client Script page once in\n"
            "  Setup → Developer Space → Client Scripts (Deals, Standard layout), then re-run.",
            file=sys.stderr,
        )
        return None
    for item in r.json().get("client_script_pages") or []:
        details = item.get("details") or {}
        if item.get("code") == "SUCCESS" and details.get("id"):
            return str(details["id"])
        if item.get("id"):
            return str(item["id"])
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


def _set_script_in_entry(entry: dict, source: str) -> None:
    for k in ("script", "source", "source_code", "code", "javascript", "client_script_source"):
        if k in entry or k == "script":
            entry[k] = source
            return
    entry["script"] = source


def _upsert_script(
    session: requests.Session,
    api_domain: str,
    page_id: str,
    name: str,
    description: str,
    source: str,
    event_info: dict[str, Any],
    dry_run: bool,
) -> str | None:
    existing_id = None
    existing_event_match = None
    for script in _list_scripts(session, api_domain, page_id):
        if (script.get("name") or "").strip() == name:
            existing_id = str(script["id"])
            break
        existing_event = script.get("event_info") or {}
        if (
            existing_event.get("name") == event_info.get("name")
            and existing_event.get("type") == event_info.get("type")
        ):
            existing_event_match = str(script["id"])
    if not existing_id and existing_event_match:
        existing_id = existing_event_match

    def body(source_key: str) -> dict[str, Any]:
        script = {
            "name": name,
            "description": description,
            "client_script_page": {"id": page_id},
            "event_info": event_info,
            "state": "active",
            source_key: source,
        }
        return {"client_scripts": [script]}

    def metadata_body() -> dict[str, Any]:
        script = {
            "name": name,
            "description": description,
            "client_script_page": {"id": page_id},
            "event_info": event_info,
            "state": "active",
        }
        if existing_id:
            script["id"] = existing_id
        return {"client_scripts": [script]}

    def multipart_headers() -> dict[str, str]:
        return {k: v for k, v in session.headers.items() if k.lower() != "content-type"}

    if dry_run:
        print(f"--- dry-run {'PUT' if existing_id else 'POST'} script {name!r} ---")
        print(json.dumps(body("script"), indent=2)[:4500])
        return existing_id or "<new_client_script_id>"

    method = "PUT" if existing_id else "POST"
    path = f"/settings/client_scripts/{existing_id}" if existing_id else "/settings/client_scripts"
    last_text = ""
    for source_key in ("script", "source", "source_code", "code"):
        r = _crm(session, api_domain, method, path, json=body(source_key))
        last_text = r.text or ""
        if r.ok:
            for item in r.json().get("client_scripts") or []:
                details = item.get("details") or {}
                if item.get("code") == "SUCCESS" and details.get("id"):
                    return str(details["id"])
                if item.get("id"):
                    return str(item["id"])
            if existing_id:
                return existing_id
        if r.status_code not in (400, 422):
            break
    if "metadata" in last_text and "code" in last_text:
        files = {
            "code": ("deal_stage_field_visibility.js", source, "application/javascript"),
        }
        r = _crm(
            session,
            api_domain,
            method,
            path,
            data={"metadata": json.dumps(metadata_body())},
            files=files,
            headers=multipart_headers(),
        )
        last_text = r.text or ""
        if r.ok:
            for item in r.json().get("client_scripts") or []:
                details = item.get("details") or {}
                if item.get("code") == "SUCCESS" and details.get("id"):
                    return str(details["id"])
                if item.get("id"):
                    return str(item["id"])
            if existing_id:
                return existing_id
    print(f"  {method} client_scripts HTTP failed ({name}): {last_text[:5000]}", file=sys.stderr)
    return None


def _safari_internal_upsert(source: str, dry_run: bool) -> bool:
    """Use the logged-in Safari admin session and Zoho's internal cscript endpoints."""
    if dry_run:
        print("Dry run: would use Safari /crm/v2.2/settings/cscript_snippets fallback if public API fails.")
        return True

    def safari_js(script: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "osascript",
                "-e",
                f'tell application "Safari" to do JavaScript {json.dumps(script)} in current tab of front window',
            ],
            text=True,
            capture_output=True,
            timeout=120,
        )

    # Load Zoho's async compiler dependency into ordinary CRM pages before compiling.
    # `compile_script(...)` is async, but once this resource is loaded we can call AsyncAwait.compile synchronously.
    preload = """
(function(){
  if (typeof AsyncAwait !== 'undefined') { return 'ready'; }
  if (typeof Lyte === 'undefined' || !Lyte.injectResources || typeof networkUtils === 'undefined') {
    return 'missing-loader';
  }
  Lyte.injectResources([networkUtils.returnDependencyFiles(['cscript/convert-to-asyncawait.js'], ResourceConstants.CRMClient)]);
  return 'loading';
})()
"""
    preload_proc = safari_js(preload)
    if preload_proc.returncode != 0:
        print(preload_proc.stderr[:4000], file=sys.stderr)
        return False
    for _ in range(20):
        ready_proc = safari_js("typeof AsyncAwait !== 'undefined' ? 'ready' : 'loading'")
        if ready_proc.returncode == 0 and ready_proc.stdout.strip() == "ready":
            break
        time.sleep(0.5)
    else:
        print("Safari cscript fallback failed: AsyncAwait compiler did not load.", file=sys.stderr)
        return False

    js = f"""
(function(){{
  try {{
  var source = {json.dumps(source)};
  var csrf = (document.cookie.match(/(?:^|; )crmcsr=([^;]+)/)||[])[1];
  var org = (location.href.match(/org(\\d+)/)||[])[1];
  if (!csrf || !org) {{
    return JSON.stringify({{ok:false, error:'Missing Safari Zoho csrf/org context'}});
  }}
  function xhr(method, path, body) {{
    var x = new XMLHttpRequest();
    x.open(method, path, false);
    x.setRequestHeader('X-ZCSRF-TOKEN', 'crmcsrfparam=' + csrf);
    x.setRequestHeader('X-CRM-ORG', org);
    if (body !== undefined) {{
      x.setRequestHeader('Content-Type', 'application/json');
    }}
    x.send(body === undefined ? null : JSON.stringify(body));
    if (x.status < 200 || x.status >= 300) {{
      throw new Error(method + ' ' + path + ' HTTP ' + x.status + ': ' + x.responseText.slice(0, 1000));
    }}
    return x.responseText ? JSON.parse(x.responseText) : {{}};
  }}
  var compiled = AsyncAwait.compile(source + '\\n', {{
    functionScope: true,
    minify: false,
    sourceFileName: Math.random().toString(36).substring(2,15) + '-client-script.js',
    prefix: "'use strict';",
    excludeList: ['log']
  }});
  if (compiled.error) {{
    throw compiled.error;
  }}
  var pages = xhr('GET', '/crm/v2.2/settings/cscript_pages?include_extra_details=true').cscript_pages || [];
  var wantedPages = {{
    module_create: ['onLoad', 'onChange'],
    module_edit: ['onLoad', 'onChange']
  }};
  var results = [];
  pages.filter(function(page) {{
    return page.selectors &&
      page.selectors.Module &&
      page.selectors.Layout &&
      page.selectors.Module.value === 'Deals' &&
      page.selectors.Layout.value === 'Standard' &&
      wantedPages[page.definition_name];
  }}).forEach(function(page) {{
    var snippets = xhr('GET', '/crm/v2.2/settings/cscript_snippets?page_uuid=' + page.uuid).cscript_snippets || [];
    wantedPages[page.definition_name].forEach(function(eventName) {{
      var snippet = snippets.filter(function(item) {{
        return item.script_event && item.script_event.event === eventName && item.script_event.type === 'page';
      }})[0];
      var content = {{
        source_code: source,
        async_code: compiled.code,
        source_map: compiled.map
      }};
      if (!snippet) {{
        var createBody = {{
          cscript_snippets: [{{
            name: 'Deal Stage ' + page.definition_name.replace('module_', '') + ' ' + eventName,
            description: 'Show/hide Deal fields by Stage and block Proposal / Quote until discovery is complete.',
            active: true,
            cscript_page: {{
              id: page.id,
              uuid: page.uuid,
              definition_name: page.definition_name
            }},
            script_event: {{
              arguments: null,
              type: 'page',
              event: eventName
            }},
            content: content
          }}]
        }};
        var createResp = xhr('POST', '/crm/v2.2/settings/cscript_snippets', createBody);
        results.push({{
          ok: true,
          page: page.definition_name,
          event: eventName,
          id: ((createResp.cscript_snippets || [{{}}])[0].details || {{}}).id || ((createResp.cscript_snippets || [{{}}])[0].id),
          response: createResp
        }});
        return;
      }}
      snippet.description = 'Show/hide Deal fields by Stage and block Proposal / Quote until discovery is complete.';
      snippet.active = true;
      snippet.content = content;
      var resp = xhr('PUT', '/crm/v2.2/settings/cscript_snippets/' + snippet.uuid, {{cscript_snippets:[snippet]}});
      results.push({{
        ok: true,
        page: page.definition_name,
        event: eventName,
        id: snippet.id,
        uuid: snippet.uuid,
        response: resp
      }});
    }});
  }});
  return JSON.stringify({{ok: results.length === 4 && results.every(function(r){{return r.ok;}}), results: results}});
  }} catch (e) {{
    return JSON.stringify({{ok:false, error: String(e && (e.message || e)), stack: String(e && e.stack || '')}});
  }}
}})()
"""
    proc = safari_js(js)
    if proc.returncode != 0:
        print(proc.stderr[:4000], file=sys.stderr)
        return False
    text = proc.stdout.strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        print((text or "Safari cscript fallback returned empty output.")[:4000], file=sys.stderr)
        return False
    for result in payload.get("results") or []:
        if result.get("ok"):
            print(f"  Safari cscript updated: {result.get('page')} {result.get('event')} id={result.get('id')}")
        else:
            print(f"  Safari cscript failed: {result}", file=sys.stderr)
    if not payload.get("ok"):
        print(payload.get("error") or "Safari cscript fallback failed.", file=sys.stderr)
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="Print API payloads only.")
    ap.add_argument(
        "--print-source",
        action="store_true",
        help="Print the JS file path and contents (for manual paste).",
    )
    args = ap.parse_args()

    if not SCRIPT_PATH.is_file():
        print(f"Client script source not found: {SCRIPT_PATH}", file=sys.stderr)
        return 1
    source = SCRIPT_PATH.read_text(encoding="utf-8").rstrip() + "\n"

    if args.print_source:
        print(str(SCRIPT_PATH))
        print("---")
        print(source)
        return 0

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
    print(f"  Layout: {layout.get('name')} (id={layout['id']}) api_name={layout.get('api_name')}")

    page_defs: list[tuple[str, str]] = [
        ("module_create", "Create Page"),
        ("module_edit", "Edit Page"),
    ]
    events: list[tuple[str, dict[str, Any]]] = [
        ("OnLoad", {"name": "onLoad", "type": "page", "arguments": None}),
        (
            "OnChange-page",
            {"name": "onChange", "type": "page", "arguments": None},
        ),
    ]

    ok = True
    desc = (
        "Show/hide Deal fields by Stage (Qualification = minimal; see pipelines_seed.json)."
    )
    for definition, page_label in page_defs:
        page_id = _ensure_page(session, api_domain, definition, module, layout, args.dry_run)
        if not page_id:
            ok = False
            continue
        print(f"  Page:   {page_label} {definition} (id={page_id})")
        for ev_label, event_info in events:
            script_name = f"{SCRIPT_BASENAME} — {page_label} — {ev_label}"
            sid = _upsert_script(
                session,
                api_domain,
                page_id,
                script_name,
                desc,
                source,
                event_info,
                args.dry_run,
            )
            if not sid:
                ok = False
                continue
            print(f"  Script: {script_name} (id={sid})")

    if not ok:
        print("\nPublic client-script API failed; trying Safari admin-session fallback.")
        ok = _safari_internal_upsert(source, args.dry_run)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
