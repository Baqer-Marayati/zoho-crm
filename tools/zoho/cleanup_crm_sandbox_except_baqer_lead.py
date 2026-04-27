#!/usr/bin/env python3
"""
Delete CRM sample / test data, keeping a single real lead for Baqer (or the id you pass).

Default behavior:
  1. If a lead matches the preserve name (Baqer + Marayati in name fields), that id is kept;
     all other Leads are deleted.
  2. If no lead matches, all Leads are deleted and one new lead is **created** for Baqer
     (so you still end with one lead to experiment on).
  3. Deletes all Deals, Accounts, Contacts, Quotes; also Tasks, Events, Calls (org-wide).
  Does **not** delete Products, Vendors, Users, Pipelines, or settings.

  cd tools/zoho && ./venv/bin/python cleanup_crm_sandbox_except_baqer_lead.py
  ./venv/bin/python cleanup_crm_sandbox_except_baqer_lead.py --dry-run
  ./venv/bin/python cleanup_crm_sandbox_except_baqer_lead.py --preserve-lead-id 7353692000000XXXX

OAuth: ZohoCRM.modules.ALL (or per-module .DELETE) + ZohoCRM.modules.CREATE (to create the lead
if none matched).

**Irreversible** for the deleted records (they go to Zoho Recycle Bin per your org policy).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from typing import Any

import requests

from zoho_tokens import auth_headers, get_access_token_and_domain

API_VER = "v8"
DELETE_CHUNK = 100

# Default: keep a lead for this name (any match: first+last or full name contains these substrings)
DEFAULT_PRESERVE_FIRST = "baqer"
DEFAULT_PRESERVE_LAST = "marayati"

# Delete order: child / transactional records first, then account hierarchy, then leads.
# Modules not in your org return 400 — skipped.
_MODULE_ORDER: tuple[str, ...] = (
    "Quotes",
    "Deals",
    "Sales_Orders",
    "Invoices",
    "Cases",
    "Tasks",
    "Events",
    "Calls",
    "Contacts",
    "Accounts",
)


def _crm(
    session: requests.Session, api_domain: str, method: str, path: str, **kwargs: Any
):
    return session.request(
        method, f"{api_domain.rstrip('/')}/crm/{API_VER}{path}", timeout=120, **kwargs
    )


def _token() -> tuple[requests.Session, str]:
    access, api_domain = get_access_token_and_domain()
    s = requests.Session()
    s.headers.update(auth_headers(access))
    s.headers["Content-Type"] = "application/json"
    return s, api_domain


def _get_all_ids(
    s: requests.Session, api_domain: str, module: str
) -> list[str]:
    """List every record id in module (GET pagination)."""
    ids: list[str] = []
    page = 1
    while True:
        r = _crm(
            s,
            api_domain,
            "GET",
            f"/{module}",
            params={"fields": "id", "per_page": 200, "page": page},
        )
        if r.status_code == 204:
            break
        if r.status_code == 400:
            try:
                j = r.json()
                print(
                    f"  {module}: skip GET (400) {j.get('code') or j.get('message') or r.text[:200]}",
                    file=sys.stderr,
                )
            except json.JSONDecodeError:
                print(f"  {module}: skip GET HTTP 400", file=sys.stderr)
            return []
        r.raise_for_status()
        j = r.json()
        for row in j.get("data") or []:
            rid = row.get("id")
            if rid:
                ids.append(str(rid))
        if not (j.get("info") or {}).get("more_records"):
            break
        page += 1
    return ids


def _delete_ids(
    s: requests.Session,
    api_domain: str,
    module: str,
    ids: list[str],
    dry_run: bool,
) -> bool:
    if not ids:
        return True
    if dry_run:
        print(f"  DRY-RUN {module}: would DELETE {len(ids)} record(s)")
        return True
    ok = True
    for i in range(0, len(ids), DELETE_CHUNK):
        part = ids[i : i + DELETE_CHUNK]
        r = _crm(
            s,
            api_domain,
            "DELETE",
            f"/{module}",
            params={"ids": ",".join(part), "wf_trigger": "false"},
        )
        if not r.ok:
            print(f"  DELETE {module} HTTP {r.status_code}: {r.text[:2000]}", file=sys.stderr)
            ok = False
            continue
        try:
            for row in (r.json().get("data") or []):
                if (row.get("status") or "").lower() != "success":
                    print(f"  Item: {json.dumps(row)[:800]}", file=sys.stderr)
                    ok = False
        except json.JSONDecodeError:
            pass
        time.sleep(0.2)
    return ok


def _list_leads(s: requests.Session, api_domain: str) -> list[dict[str, Any]]:
    rows: list[dict] = []
    page = 1
    while True:
        r = _crm(
            s,
            api_domain,
            "GET",
            "/Leads",
            params={
                "fields": "id,First_Name,Last_Name,Full_Name,Company",
                "per_page": 200,
                "page": page,
            },
        )
        if r.status_code == 204:
            break
        r.raise_for_status()
        j = r.json()
        rows.extend(j.get("data") or [])
        if not (j.get("info") or {}).get("more_records"):
            break
        page += 1
    return rows


def _find_preserve(
    leads: list[dict],
    need_first: str,
    need_last: str,
) -> str | None:
    nf, nl = need_first.lower().strip(), need_last.lower().strip()
    matches: list[str] = []
    for row in leads:
        fn = (row.get("First_Name") or "").lower()
        ln = (row.get("Last_Name") or "").lower()
        full = (row.get("Full_Name") or "").lower()
        if nf in fn or nf in full:
            if nl in ln or nl in full:
                if row.get("id"):
                    matches.append(str(row["id"]))
    if len(matches) > 1:
        print(
            f"More than one lead matches {need_first!r} + {need_last!r}: {matches} — using first.",
            file=sys.stderr,
        )
    return matches[0] if matches else None


def _create_baqer_lead(s: requests.Session, api_domain: str, dry_run: bool) -> bool:
    body = {
        "data": [
            {
                "First_Name": "Baqer",
                "Last_Name": "Al-Marayati",
                "Company": "Aljazeera",
                "Phone": "+9647800000000",
            }
        ]
    }
    if dry_run:
        print("  DRY-RUN: would POST new Lead for Baqer Al-Marayati (Company/Phone are placeholders; edit in UI).")
        return True
    r = _crm(s, api_domain, "POST", "/Leads", data=json.dumps(body))
    if not r.ok:
        print(f"POST Leads HTTP {r.status_code}: {r.text[:3000]}", file=sys.stderr)
        return False
    try:
        j = r.json()
        for row in j.get("data") or []:
            print("  Created lead id:", row.get("details", {}).get("id") or row.get("id"), row)
    except Exception:
        print(r.text[:2000])
    return True


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Delete CRM data except one Baqer lead (or id); optionally create that lead if missing."
    )
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--preserve-lead-id",
        help="Skip name matching; keep this Lead id and delete all other Leads.",
    )
    ap.add_argument(
        "--no-create-lead",
        action="store_true",
        help="If no lead matches Baqer, do not create one; leaves zero leads unless one matched.",
    )
    args = ap.parse_args()
    will_create = not args.no_create_lead

    try:
        s, api_domain = _token()
    except RuntimeError as e:
        print(e, file=sys.stderr)
        return 1

    print(f"API: {api_domain}\n")

    leads = _list_leads(s, api_domain)
    print(f"Leads in org: {len(leads)}")

    if args.preserve_lead_id:
        preserve_id = str(args.preserve_lead_id).strip()
        if not any(str(r.get("id")) == preserve_id for r in leads):
            print(
                f"--preserve-lead-id={preserve_id} not found in Leads.",
                file=sys.stderr,
            )
            return 1
    else:
        preserve_id = _find_preserve(
            leads, DEFAULT_PRESERVE_FIRST, DEFAULT_PRESERVE_LAST
        )
        if preserve_id:
            print(f"Preserve lead id={preserve_id} (name match {DEFAULT_PRESERVE_FIRST}/{DEFAULT_PRESERVE_LAST}).")
        else:
            print(
                f"No lead matches default preserve ({DEFAULT_PRESERVE_FIRST!r} + {DEFAULT_PRESERVE_LAST!r} in name)."
            )

    ok = True
    for mod in _MODULE_ORDER:
        ids = _get_all_ids(s, api_domain, mod)
        if not ids:
            continue
        print(f"\n{mod}: {len(ids)} record(s) to delete")
        if not _delete_ids(s, api_domain, mod, ids, args.dry_run):
            ok = False

    all_lead_ids = [str(r["id"]) for r in leads if r.get("id")]
    if not preserve_id and will_create:
        to_del = all_lead_ids
    elif preserve_id:
        to_del = [i for i in all_lead_ids if i != preserve_id]
    else:
        to_del = all_lead_ids

    if to_del:
        print(f"\nLeads: {len(to_del)} to delete (preserve={preserve_id!r})")
        if not _delete_ids(s, api_domain, "Leads", to_del, args.dry_run):
            ok = False
    else:
        print("\nLeads: nothing to delete (only preserved lead)")

    if not preserve_id and will_create and not args.dry_run:
        print("\nCreating a single new lead for Baqer (no matching lead to preserve)…")
        if not _create_baqer_lead(s, api_domain, False):
            ok = False
    elif not preserve_id and will_create and args.dry_run:
        _create_baqer_lead(s, api_domain, True)

    if not preserve_id and not will_create and not args.dry_run and all_lead_ids:
        print(
            "\n--no-create-lead: you have no Baqer match and asked not to create one; all leads are deleted.",
            file=sys.stderr,
        )

    if ok:
        print("\nDone. Check Zoho Recycle Bin if you need to recover something.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
