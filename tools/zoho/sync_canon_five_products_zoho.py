#!/usr/bin/env python3
"""
Remove flat Canon Wave-A product rows from Zoho, then import the five-machine CSV.

Deletes Products whose Product_Name matches a row in canon_products_wave_a_en.csv
(23 legacy names: per-speed engines + accessories). Then runs the same POST path as
provision_phase3 step 2 for canon_products_five_machines_en.csv.

Requires ZohoCRM.modules.ALL (or Products DELETE + CREATE).

Usage:
  cd tools/zoho
  ./venv/bin/python sync_canon_five_products_zoho.py
  ./venv/bin/python sync_canon_five_products_zoho.py --dry-run
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import requests

from zoho_tokens import auth_headers, get_access_token_and_domain

API_VER = "v8"
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
IMPORT_DIR = REPO_ROOT / "artifacts" / "zoho" / "import"
LEGACY_CSV = IMPORT_DIR / "canon_products_wave_a_en.csv"
FIVE_CSV = IMPORT_DIR / "canon_products_five_machines_en.csv"


def _crm(session: requests.Session, api_domain: str, method: str, path: str, **kwargs):
    url = f"{api_domain.rstrip('/')}/crm/{API_VER}{path}"
    return session.request(method, url, timeout=120, **kwargs)


def _legacy_name_set(path: Path) -> set[str]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return {(r.get("Product_Name") or "").strip().casefold() for r in rows if (r.get("Product_Name") or "").strip()}


def _list_products_to_delete(
    session: requests.Session, api_domain: str, legacy_cf: set[str]
) -> list[tuple[str, str]]:
    """Return [(id, Product_Name), ...] for records to delete."""
    out: list[tuple[str, str]] = []
    page = 1
    while True:
        r = _crm(
            session,
            api_domain,
            "GET",
            "/Products",
            params={
                "fields": "id,Product_Name",
                "per_page": 200,
                "page": page,
            },
        )
        if r.status_code == 204:
            break
        if not r.ok:
            raise RuntimeError(f"GET /Products page {page} HTTP {r.status_code}: {r.text[:2000]}")
        body = r.json()
        for p in body.get("data") or []:
            pid = str(p.get("id") or "")
            pname = (p.get("Product_Name") or "").strip()
            if not pid or not pname:
                continue
            if pname.casefold() in legacy_cf:
                out.append((pid, pname))
        info = body.get("info") or {}
        if not info.get("more_records"):
            break
        page += 1
    return out


def _delete_batch(session: requests.Session, api_domain: str, ids: list[str], dry_run: bool) -> bool:
    if not ids:
        return True
    if dry_run:
        print(f"  [dry-run] Would DELETE {len(ids)} product(s)")
        return True
    chunk = 100
    ok_all = True
    for i in range(0, len(ids), chunk):
        part = ids[i : i + chunk]
        r = _crm(
            session,
            api_domain,
            "DELETE",
            "/Products",
            params={"ids": ",".join(part), "wf_trigger": "false"},
        )
        if not r.ok:
            print(f"  DELETE /Products HTTP {r.status_code}: {r.text[:2500]}", file=sys.stderr)
            ok_all = False
            continue
        try:
            data = r.json().get("data") or []
            for row in data:
                if (row.get("status") or "").lower() != "success":
                    print(f"  Item: {json.dumps(row)[:500]}", file=sys.stderr)
                    ok_all = False
        except json.JSONDecodeError:
            print(f"  DELETE OK (non-JSON): {r.text[:500]}")
    return ok_all


def _import_five(session: requests.Session, api_domain: str, dry_run: bool) -> bool:
    """Invoke provision_phase3.step2_products (same CSV rules)."""
    from provision_phase3 import step2_products

    return step2_products(session, api_domain, dry_run, csv_path=FIVE_CSV)


def main() -> int:
    ap = argparse.ArgumentParser(description="Delete legacy Canon products; import five-machine CSV")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not LEGACY_CSV.is_file():
        print(f"Missing {LEGACY_CSV}", file=sys.stderr)
        return 1
    if not FIVE_CSV.is_file():
        print(f"Missing {FIVE_CSV}", file=sys.stderr)
        return 1

    try:
        access, api_domain = get_access_token_and_domain()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1

    session = requests.Session()
    session.headers.update(auth_headers(access))

    legacy_cf = _legacy_name_set(LEGACY_CSV)
    print(f"Legacy name set: {len(legacy_cf)} distinct name(s) from {LEGACY_CSV.name}")

    try:
        to_del = _list_products_to_delete(session, api_domain, legacy_cf)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1

    if not to_del:
        print("No legacy Canon products found in Zoho (nothing to delete by name).")
    else:
        print(f"Deleting {len(to_del)} product(s) matching legacy Wave-A names:")
        for pid, pname in to_del:
            print(f"  {pid}  {pname}")
        ids = [p[0] for p in to_del]
        if not _delete_batch(session, api_domain, ids, args.dry_run):
            print("Delete step had errors; stopping before import.", file=sys.stderr)
            return 1

    print("\nImporting five-machine catalog…")
    if not _import_five(session, api_domain, args.dry_run):
        return 1

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
