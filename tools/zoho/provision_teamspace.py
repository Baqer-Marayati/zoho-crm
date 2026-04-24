#!/usr/bin/env python3
"""
Create a Zoho CRM Next Gen teamspace from a JSON manifest (CRM API v8).

POST /crm/v8/settings/team_spaces

Requires OAuth scopes that allow team space settings (typically ZohoCRM.settings.ALL
or the documented settings scopes for team_spaces). Optional: ZohoCRM.users.ALL to
resolve the current user as admin when ZOHO_TEAMSPACE_ADMIN_ID is not set.

Manifest shape (see ../../artifacts/zoho/teamspace/direct_department.json):
  name, description, access_type (PUBLIC | SHARED), icon_color, folders[] with
  display_label and modules[] (module api_names, e.g. Leads, Deals).

Usage:
  cd tools/zoho
  ./venv/bin/python provision_teamspace.py --dry-run
  ./venv/bin/python provision_teamspace.py
  ./venv/bin/python provision_teamspace.py --manifest /path/to/manifest.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests

from zoho_tokens import auth_headers, get_access_token_and_domain

API_VER = "v8"
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_MANIFEST = SCRIPT_DIR.parent.parent / "artifacts" / "zoho" / "teamspace" / "direct_department.json"


def _crm(session: requests.Session, api_domain: str, method: str, path: str, **kwargs):
    url = f"{api_domain.rstrip('/')}/crm/{API_VER}{path}"
    return session.request(method, url, timeout=90, **kwargs)


def _load_manifest(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _module_id_by_api_name(session: requests.Session, api_domain: str) -> dict[str, str]:
    r = _crm(session, api_domain, "GET", "/settings/modules")
    if not r.ok:
        raise RuntimeError(f"GET /settings/modules failed HTTP {r.status_code}: {r.text[:1500]}")
    try:
        payload = r.json()
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Non-JSON modules response: {r.text[:500]}") from e
    out: dict[str, str] = {}
    for m in payload.get("modules") or []:
        api = str(m.get("api_name") or "").strip()
        mid = m.get("id")
        if api and mid is not None:
            out[api] = str(mid)
    return out


def _resolve_admin_user_id(session: requests.Session, api_domain: str) -> str:
    env_id = os.environ.get("ZOHO_TEAMSPACE_ADMIN_ID", "").strip()
    if env_id:
        return env_id
    r = _crm(session, api_domain, "GET", "/users", params={"type": "CurrentUser"})
    if not r.ok:
        raise RuntimeError(
            f"Could not resolve admin user (HTTP {r.status_code}). "
            f"Set ZOHO_TEAMSPACE_ADMIN_ID in .env or add ZohoCRM.users.ALL to your token. "
            f"Body: {r.text[:800]}"
        )
    try:
        data = r.json()
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Non-JSON users response: {r.text[:500]}") from e
    users = data.get("users") or []
    if not users:
        raise RuntimeError("No users in CurrentUser response; set ZOHO_TEAMSPACE_ADMIN_ID in .env")
    uid = users[0].get("id")
    if not uid:
        raise RuntimeError("User record missing id; set ZOHO_TEAMSPACE_ADMIN_ID in .env")
    return str(uid)


def _build_payload(manifest: dict, module_ids: dict[str, str], admin_id: str) -> dict:
    name = manifest.get("name", "").strip()
    if not name:
        raise RuntimeError("manifest.name is required")
    access_raw = (manifest.get("access_type") or "PUBLIC").strip().upper()
    if access_raw not in ("PUBLIC", "SHARED"):
        raise RuntimeError("manifest.access_type must be PUBLIC or SHARED")
    # Zoho expects lowercase for create; uppercase triggers INVALID_DATA on access_type.
    access_api = access_raw.lower()
    icon = (manifest.get("icon_color") or "#2430D0").strip()
    desc = (manifest.get("description") or "").strip()

    # API shape: one entry per module, each {"module": {"id": "..."}} — no "folder" key
    # (adding folder.name returns "Invalid Folder" in this org). Folder labels are UI-only.
    seen: set[str] = set()
    mappings: list[dict] = []
    for folder in manifest.get("folders") or []:
        for api_name in folder.get("modules") or []:
            key = str(api_name).strip()
            mid = module_ids.get(key)
            if not mid:
                raise RuntimeError(
                    f"Unknown module api_name {key!r}. "
                    f"Check spelling against GET /settings/modules (custom modules use their api_name)."
                )
            if mid in seen:
                continue
            seen.add(mid)
            mappings.append({"module": {"id": mid}})

    if not mappings:
        raise RuntimeError("manifest.folders must list at least one module")

    entry: dict = {
        "name": name,
        "admin": {"id": admin_id},
        "access_type": access_api,
        "other_props": {"icon_color": icon},
        "module_folder_mappings": mappings,
    }
    if desc:
        entry["description"] = desc

    if access_raw == "SHARED":
        entry["members"] = [{"id": admin_id, "role": "admin"}]

    return {"team_spaces": [entry]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Create Zoho CRM teamspace from manifest JSON.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help=f"Path to manifest (default: {DEFAULT_MANIFEST})",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print resolved payload only; no POST.")
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    if not manifest_path.is_file():
        print(f"Manifest not found: {manifest_path}", file=sys.stderr)
        return 1

    manifest = _load_manifest(manifest_path)

    try:
        access, api_domain = get_access_token_and_domain()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        if "too many requests" in str(e).lower() or "Access Denied" in str(e):
            print(
                "\nZoho accounts rate-limited token refresh. Wait several minutes and retry.",
                file=sys.stderr,
            )
        return 1

    session = requests.Session()
    session.headers.update(auth_headers(access))
    session.headers["Content-Type"] = "application/json"

    try:
        module_ids = _module_id_by_api_name(session, api_domain)
        admin_id = _resolve_admin_user_id(session, api_domain)
        body = _build_payload(manifest, module_ids, admin_id)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1

    print(json.dumps(body, indent=2))

    if args.dry_run:
        print("\n--dry-run: no POST.", file=sys.stderr)
        return 0

    r = _crm(session, api_domain, "POST", "/settings/team_spaces", json=body)
    if not r.ok:
        print(f"\nPOST /settings/team_spaces HTTP {r.status_code}", file=sys.stderr)
        print(r.text[:3000], file=sys.stderr)
        return 1

    try:
        out = r.json()
    except json.JSONDecodeError:
        print(r.text[:2000])
        return 0

    print(json.dumps(out, indent=2)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
