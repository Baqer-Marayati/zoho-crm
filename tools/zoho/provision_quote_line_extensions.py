#!/usr/bin/env python3
"""
1) Products: optional reference text for finishers / POD (textarea fields), synced from
   ../../artifacts/zoho/product_extensions/extensions_by_product_code.json
2) Quote line items: picklists Finisher (line) + POD / paper module (line) from
   ../../artifacts/zoho/picklists/quote_line_*.csv

Line-item fields are created on the inventory line module (usually Quoted_Items). If Zoho
rejects that module name, create the two picklists via UI (see docs/zoho/QUOTE-LINE-EXTENSIONS.md).

OAuth: ZohoCRM.settings.ALL (or fields.CREATE on Products + Quoted_Items).

Usage:
  cd tools/zoho
  ./venv/bin/python provision_quote_line_extensions.py --dry-run
  ./venv/bin/python provision_quote_line_extensions.py
  ./venv/bin/python provision_quote_line_extensions.py --products-only
  ./venv/bin/python provision_quote_line_extensions.py --quoted-items-only
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

import requests

from zoho_tokens import auth_headers, get_access_token_and_domain

API_VER = "v8"
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
EXT_JSON = REPO_ROOT / "artifacts" / "zoho" / "product_extensions" / "extensions_by_product_code.json"
PICK_FIN = REPO_ROOT / "artifacts" / "zoho" / "picklists" / "quote_line_finisher.csv"
PICK_POD = REPO_ROOT / "artifacts" / "zoho" / "picklists" / "quote_line_pod_paper.csv"

PRODUCT_FIELD_FINISHERS = "Compatible finishers"
PRODUCT_FIELD_POD = "Compatible POD / paper"
LINE_FIELD_FINISHERS = "Finisher (line)"
LINE_FIELD_POD = "POD / paper module (line)"

LINE_MODULES_TO_TRY = ("Quoted_Items", "QuotedItems", "Quote_Line_Items", "Quotes_Line_Items")


def _crm(session: requests.Session, api_domain: str, method: str, path: str, **kwargs):
    url = f"{api_domain.rstrip('/')}/crm/{API_VER}{path}"
    return session.request(method, url, timeout=120, **kwargs)


def _slug(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s.strip()).strip("_")
    return s[:100] if s else "value"


def _read_pick_csv(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    col = rows[0].keys().__iter__().__next__() if rows else "Display_Value"
    out: list[str] = []
    for row in rows:
        v = (row.get(col) or "").strip()
        if v:
            out.append(v)
    return out


def _get_fields_map(session: requests.Session, api_domain: str, module: str) -> dict[str, dict]:
    r = _crm(session, api_domain, "GET", "/settings/fields", params={"module": module})
    if not r.ok:
        raise RuntimeError(f"GET fields {module} HTTP {r.status_code}: {r.text[:2000]}")
    return {
        (f.get("field_label") or "").strip().lower(): f
        for f in r.json().get("fields", [])
        if f.get("field_label")
    }


def _post_field(
    session: requests.Session, api_domain: str, module: str, field_def: dict, dry_run: bool
) -> str | None:
    label = field_def.get("field_label", "?")
    print(f"  POST field '{label}' → module={module}")
    if dry_run:
        return "dry_run"
    r = _crm(
        session,
        api_domain,
        "POST",
        "/settings/fields",
        params={"module": module},
        json={"fields": [field_def]},
    )
    if not r.ok:
        print(f"  HTTP {r.status_code}: {r.text[:3000]}", file=sys.stderr)
        return None
    try:
        print(json.dumps(r.json(), indent=2)[:2000])
        for item in r.json().get("fields") or []:
            fid = (item.get("details") or {}).get("id") or item.get("id")
            if fid:
                return str(fid)
    except json.JSONDecodeError:
        pass
    return None


def _ensure_textarea(
    session: requests.Session, api_domain: str, module: str, label: str, dry_run: bool
) -> bool:
    fields = _get_fields_map(session, api_domain, module)
    if label.strip().lower() in fields:
        print(f"  '{label}' already on {module}")
        return True
    return _post_field(
        session,
        api_domain,
        module,
        {
            "field_label": label,
            "data_type": "textarea",
            "textarea": {"type": "large"},
        },
        dry_run,
    ) is not None or dry_run


def _api_name_for_label(session: requests.Session, api_domain: str, module: str, label: str) -> str | None:
    f = _get_fields_map(session, api_domain, module).get(label.strip().lower())
    if not f:
        return None
    return (f.get("api_name") or "").strip() or None


def _fetch_product_id_by_code(session: requests.Session, api_domain: str, code: str) -> str | None:
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
            print(f"  GET /Products page {page} HTTP {r.status_code}: {r.text[:800]}", file=sys.stderr)
            return None
        body = r.json()
        for row in body.get("data") or []:
            if (row.get("Product_Code") or "").strip() == code:
                return str(row.get("id"))
        info = body.get("info") or {}
        if not info.get("more_records"):
            return None
        page += 1


def _update_product_extensions(
    session: requests.Session,
    api_domain: str,
    ext: dict[str, Any],
    dry_run: bool,
) -> bool:
    fin_api = _api_name_for_label(session, api_domain, "Products", PRODUCT_FIELD_FINISHERS)
    pod_api = _api_name_for_label(session, api_domain, "Products", PRODUCT_FIELD_POD)
    if not fin_api or not pod_api:
        print("  Missing product field api_names; create fields first.", file=sys.stderr)
        return False

    ok = True
    for code, spec in ext.items():
        if not code.startswith("CANON-"):
            continue
        pid = _fetch_product_id_by_code(session, api_domain, code)
        if not pid:
            print(f"  No product with Product_Code={code}", file=sys.stderr)
            ok = False
            continue
        fin_lines = spec.get("finishers") or []
        pod_lines = spec.get("pod_paper") or []
        fin_text = "\n".join(f"• {x}" for x in fin_lines) if fin_lines else "— None in Wave-A spec —"
        pod_text = "\n".join(f"• {x}" for x in pod_lines) if pod_lines else "— None in Wave-A spec —"
        note = (spec.get("notes") or "").strip()
        if note:
            fin_text = fin_text + f"\n\nNote: {note}" if fin_lines else f"Note: {note}"

        if dry_run:
            print(f"  (dry-run) PUT Products id={pid} {code}")
            continue
        r2 = _crm(
            session,
            api_domain,
            "PUT",
            "/Products",
            json={"data": [{"id": pid, fin_api: fin_text, pod_api: pod_text}]},
        )
        if not r2.ok:
            print(f"  PUT Products {pid} HTTP {r2.status_code}: {r2.text[:1500]}", file=sys.stderr)
            ok = False
        else:
            print(f"  Updated product {code} id={pid}")
    return ok


def _discover_line_module(session: requests.Session, api_domain: str) -> str | None:
    r = _crm(session, api_domain, "GET", "/settings/modules")
    if not r.ok:
        return None
    apis = {m.get("api_name") for m in r.json().get("modules", []) if m.get("api_name")}
    for cand in LINE_MODULES_TO_TRY:
        if cand in apis:
            print(f"  Using line module: {cand}")
            return cand
    # fuzzy
    for m in r.json().get("modules", []):
        api = (m.get("api_name") or "").lower()
        if "quoted" in api and "item" in api:
            name = m.get("api_name")
            print(f"  Using line module (fuzzy): {name}")
            return str(name)
    return None


def _ensure_line_picklist(
    session: requests.Session,
    api_domain: str,
    module: str,
    label: str,
    values: list[str],
    dry_run: bool,
) -> bool:
    fields = _get_fields_map(session, api_domain, module)
    if label.strip().lower() in fields:
        print(f"  '{label}' already on {module}")
        return True
    pick_vals = [{"display_value": v, "actual_value": _slug(v)} for v in values]
    field_def: dict[str, Any] = {
        "field_label": label,
        "data_type": "picklist",
        "pick_list_values": pick_vals,
        "pick_list_values_sorted_lexically": False,
        "enable_colour_code": False,
    }
    res = _post_field(session, api_domain, module, field_def, dry_run)
    return res is not None


def main() -> int:
    ap = argparse.ArgumentParser(description="Product extension reference + quote line picklists")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--products-only", action="store_true")
    ap.add_argument("--quoted-items-only", action="store_true")
    args = ap.parse_args()

    if not EXT_JSON.is_file():
        print(f"Missing {EXT_JSON}", file=sys.stderr)
        return 1

    try:
        access, api_domain = get_access_token_and_domain()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1

    session = requests.Session()
    session.headers.update(auth_headers(access))
    session.headers["Content-Type"] = "application/json"

    ext_data = json.loads(EXT_JSON.read_text(encoding="utf-8"))

    do_products = not args.quoted_items_only
    do_lines = not args.products_only

    if do_products:
        print("\n=== Products: textarea reference fields ===")
        if not _ensure_textarea(session, api_domain, "Products", PRODUCT_FIELD_FINISHERS, args.dry_run):
            return 1
        if not _ensure_textarea(session, api_domain, "Products", PRODUCT_FIELD_POD, args.dry_run):
            return 1
        if args.dry_run:
            print("  (dry-run) Would PUT extension text onto each Canon product after fields exist.")
        elif not _update_product_extensions(session, api_domain, ext_data, False):
            return 1

    if do_lines:
        print("\n=== Quote line: finisher + POD picklists ===")
        fin_vals = _read_pick_csv(PICK_FIN)
        pod_vals = _read_pick_csv(PICK_POD)
        mod = _discover_line_module(session, api_domain)
        if not mod:
            print(
                "  Could not find Quoted_Items (or similar) in GET /settings/modules.\n"
                "  Add picklists manually on Quote → Product Details; see docs/zoho/QUOTE-LINE-EXTENSIONS.md",
                file=sys.stderr,
            )
            return 0 if args.products_only else 1
        if not _ensure_line_picklist(session, api_domain, mod, LINE_FIELD_FINISHERS, fin_vals, args.dry_run):
            return 1
        if not _ensure_line_picklist(session, api_domain, mod, LINE_FIELD_POD, pod_vals, args.dry_run):
            return 1

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
