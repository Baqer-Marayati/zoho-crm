#!/usr/bin/env python3
"""Push Product Description from canon_products_five_machines_en.csv to Zoho (PUT by Product_Code)."""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import requests

from zoho_tokens import auth_headers, get_access_token_and_domain

API_VER = "v8"
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
CSV_PATH = REPO_ROOT / "artifacts" / "zoho" / "import" / "canon_products_five_machines_en.csv"


def _crm(session: requests.Session, api_domain: str, method: str, path: str, **kwargs):
    url = f"{api_domain.rstrip('/')}/crm/{API_VER}{path}"
    return session.request(method, url, timeout=120, **kwargs)


def _product_id_by_code(session: requests.Session, api_domain: str, code: str) -> str | None:
    page = 1
    while True:
        r = _crm(
            session,
            api_domain,
            "GET",
            "/Products",
            params={"fields": "id,Product_Code", "per_page": 200, "page": page},
        )
        if r.status_code == 204:
            return None
        if not r.ok:
            print(f"GET /Products HTTP {r.status_code}: {r.text[:800]}", file=sys.stderr)
            return None
        body = r.json()
        for row in body.get("data") or []:
            if (row.get("Product_Code") or "").strip() == code:
                return str(row.get("id"))
        if not (body.get("info") or {}).get("more_records"):
            return None
        page += 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Sync Product Description from five-machines CSV")
    ap.add_argument("--csv", type=Path, default=CSV_PATH)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.csv.is_file():
        print(f"Missing {args.csv}", file=sys.stderr)
        return 1

    rows: list[dict[str, str]] = []
    with args.csv.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)

    try:
        access, api_domain = get_access_token_and_domain()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1

    session = requests.Session()
    session.headers.update(auth_headers(access))
    session.headers["Content-Type"] = "application/json"

    ok = True
    for row in rows:
        code = (row.get("Product_Code") or "").strip()
        desc = (row.get("Description") or "").strip()
        name = (row.get("Product_Name") or "").strip()
        if not code or not desc:
            continue
        pid = _product_id_by_code(session, api_domain, code)
        if not pid:
            print(f"No product Product_Code={code} ({name})", file=sys.stderr)
            ok = False
            continue
        if args.dry_run:
            print(f"Would PUT id={pid} {code}: {desc[:80]}…")
            continue
        r = _crm(
            session,
            api_domain,
            "PUT",
            "/Products",
            json={"data": [{"id": pid, "Description": desc}]},
        )
        if not r.ok:
            print(f"PUT {code} HTTP {r.status_code}: {r.text[:1500]}", file=sys.stderr)
            ok = False
        else:
            print(f"Updated Description: {code} ({name})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
