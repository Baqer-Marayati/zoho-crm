#!/usr/bin/env python3
"""PUT Product_Name + Description (+ optional Unit_Price, Qty) from CSV by Product_Code."""
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
DEFAULT_CSV = REPO_ROOT / "artifacts" / "zoho" / "import" / "canon_products_catalog_en.csv"


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
    ap = argparse.ArgumentParser(description="Sync Product_Name and Description from CSV")
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV)
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
        name = (row.get("Product_Name") or "").strip()
        desc = (row.get("Description") or "").strip()
        if not code:
            continue
        pid = _product_id_by_code(session, api_domain, code)
        if not pid:
            print(f"No product Product_Code={code}", file=sys.stderr)
            ok = False
            continue
        payload: dict = {"id": pid}
        if name:
            payload["Product_Name"] = name
        if desc:
            payload["Description"] = desc
        price = (row.get("Unit_Price") or "").strip()
        if price:
            try:
                payload["Unit_Price"] = float(price)
            except ValueError:
                pass
        qty = (row.get("Qty_in_Stock") or "").strip()
        if qty:
            try:
                payload["Qty_in_Stock"] = int(float(qty))
            except ValueError:
                pass
        if args.dry_run:
            print(f"Would PUT {code}: {name[:60]}…")
            continue
        r = _crm(session, api_domain, "PUT", "/Products", json={"data": [payload]})
        if not r.ok:
            print(f"PUT {code} HTTP {r.status_code}: {r.text[:1500]}", file=sys.stderr)
            ok = False
        else:
            print(f"Updated: {code}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
