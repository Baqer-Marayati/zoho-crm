#!/usr/bin/env python3
"""
Create a Zoho CPQ **Product Configurator** rule via the (undocumented) Settings API.

Discovered in Apr 2026 against Zoho CRM v8:

  POST  /crm/v8/settings/cpq/product_configurators
  body: { "product_configurators": [ { ... } ] }

**Note:** This path is not in the public `GET /crm/v8/__apis` index. Zoho may change or
internal-error (500) the payload. The script idempotently tries to find an existing rule
by name, then creates a small **pilot** that ties **Product (Machine)** (Machine_SKU) on
`Quoted_Items` to a **line_item_field_update** action for a sample product — enough to
prove the API, not a full mirror of your map_dependency matrix.

**OAuth:** Use a refresh token with `ZohoCRM.settings.ALL` (or CPQ-relevant settings scopes
if your console exposes them for this endpoint).

  cd tools/zoho
  ./venv/bin/python provision_cpq_product_configurator_pilot.py --dry-run
  ./venv/bin/python provision_cpq_product_configurator_pilot.py
  ./venv/bin/python provision_cpq_product_configurator_pilot.py --product-code CANON-IP-V9K-SER
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

import requests

from zoho_tokens import auth_headers, get_access_token_and_domain

API_VER = "v8"
DEFAULT_NAME = "Pilot Product Machine line item update"
DEFAULT_PRODUCT_CODE = "CANON-IP-V9K-SER"


def _get_token_retry() -> tuple[str, str]:
    delays = (2, 10, 45, 120, 300, 600, 900)
    last_err: Exception | None = None
    for d in delays:
        try:
            return get_access_token_and_domain()
        except RuntimeError as e:
            last_err = e
            msg = str(e)
            if "too many requests" in msg.lower() or "400" in msg or "Access Denied" in msg:
                print(f"  Token refresh rate-limited; waiting {d}s…", file=sys.stderr)
                time.sleep(d)
                continue
            raise
    assert last_err is not None
    raise last_err


def _crm(
    s: requests.Session, dom: str, method: str, path: str, **kwargs: Any
) -> requests.Response:
    url = f"{dom.rstrip('/')}/crm/{API_VER}{path}"
    return s.request(method, url, timeout=120, **kwargs)


def _module_by_name(s: requests.Session, dom: str, api: str) -> dict:
    r = _crm(s, dom, "GET", "/settings/modules")
    r.raise_for_status()
    for m in r.json().get("modules") or []:
        if m.get("api_name") == api:
            return m
    raise RuntimeError(f"Module not found: {api}")


def _line_field(
    s: requests.Session, dom: str, module: str, api: str, type_all: bool = True
) -> dict:
    params: dict = {"module": module}
    if type_all:
        params["type"] = "all"
    r = _crm(s, dom, "GET", "/settings/fields", params=params)
    r.raise_for_status()
    for f in r.json().get("fields") or []:
        if f.get("api_name") == api:
            return f
    raise RuntimeError(f"Field not found: {module}.{api}")


def _default_layout_id(s: requests.Session, dom: str, module: str) -> str:
    r = _crm(s, dom, "GET", "/settings/layouts", params={"module": module})
    r.raise_for_status()
    lo = (r.json().get("layouts") or [None])[0] or {}
    lid = lo.get("id")
    if not lid:
        raise RuntimeError(f"No layout for {module}")
    return str(lid)


def _find_product_id(s: requests.Session, dom: str, product_code: str) -> str:
    r = _crm(
        s,
        dom,
        "GET",
        "/Products/search",
        params={"criteria": f"(Product_Code:equals:{product_code})"},
    )
    if r.ok:
        data = r.json() or {}
        rows = data.get("data")
        if not rows and "Products" in data:
            rows = data.get("Products")
        if rows and len(rows) > 0 and rows[0].get("id"):
            return str(rows[0]["id"])
    r2 = _crm(
        s,
        dom,
        "GET",
        "/Products",
        params={"per_page": 5, "page": 1, "sort_by": "id"},
    )
    r2.raise_for_status()
    found = (r2.json().get("data") or [{}])[0].get("id")
    if not found:
        raise RuntimeError("No Products in org to attach pilot action.")
    if product_code and r2.ok:
        print(
            f"  Warning: could not find Product_Code={product_code!r}; using first product id.",
            file=sys.stderr,
        )
    return str(found)


def _list_configurator_by_name(
    s: requests.Session, dom: str, name: str
) -> str | None:
    r = _crm(
        s,
        dom,
        "GET",
        "/settings/cpq/product_configurators",
        params={"per_page": 200, "page": 1},
    )
    if r.status_code == 204 or not (r.text or "").strip():
        return None
    if not r.ok:
        return None
    try:
        j = r.json()
    except json.JSONDecodeError:
        return None
    for k in ("product_configurators", "configurators", "data"):
        for row in (j.get(k) or []) or []:
            if (row or {}).get("name") == name and row.get("id"):
                return str(row["id"])
    return None


def _zoho_safe_name(s: str) -> str:
    """Zoho CPQ rejected em-dash, parentheses, and more in the rule `name` field (Apr 2026)."""
    t = (s or "").replace("\u2014", " ").replace("\u2013", " ")
    out: list[str] = []
    for ch in t:
        if ch.isalnum() or ch in " -_":
            out.append(ch)
        else:
            out.append(" ")
    t = "".join(out)
    return " ".join(t.split()).strip() or DEFAULT_NAME


def _build_payload(
    s: requests.Session,
    dom: str,
    name: str,
    product_id: str,
) -> dict:
    quotes = _module_by_name(s, dom, "Quotes")
    sub = _module_by_name(s, dom, "Quoted_Items")
    prods = _module_by_name(s, dom, "Products")
    f_msku = _line_field(s, dom, "Quoted_Items", "Machine_SKU")
    f_pn = _line_field(s, dom, "Quoted_Items", "Product_Name")
    q_lay = _default_layout_id(s, dom, "Quotes")
    li_lay = _default_layout_id(s, dom, "Quoted_Items")
    name = _zoho_safe_name(name)
    return {
        "product_configurators": [
            {
                "name": name,
                "description": (
                    "API pilot: on Quote line, when Product (Machine) changes, run a "
                    "line_item_field_update (sample product). Complement to map_dependency + "
                    "Deluge. Refine or delete in Zoho if redundant."
                ),
                "execute_on": "create_and_edit",
                "status": {"active": True},
                "module": {
                    "api_name": "Quotes",
                    "id": str(quotes["id"]),
                },
                "subform_module": {
                    "api_name": "Quoted_Items",
                    "id": str(sub["id"]),
                },
                "layout": {"id": str(q_lay)},
                "subform_layout": {"id": str(li_lay)},
                "trigger_field": {
                    "api_name": f_msku["api_name"],
                    "id": str(f_msku["id"]),
                },
                "entity_lookup": {
                    "api_name": f_pn["api_name"],
                    "id": str(f_pn["id"]),
                },
                "rules": [
                    {
                        "sequence_number": 1,
                        "type": "all_records",
                        "criteria": {},
                    }
                ],
                "actions": [
                    {
                        "type": "line_item_field_update",
                        "sequence_number": 1,
                        "associated_record": {
                            "id": str(product_id),
                            "module": {
                                "api_name": "Products",
                                "id": str(prods["id"]),
                            },
                        },
                    }
                ],
            }
        ]
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--name",
        type=str,
        default=DEFAULT_NAME,
        help="Rule display name (idempotent: skip if already exists).",
    )
    ap.add_argument(
        "--product-code",
        type=str,
        default=DEFAULT_PRODUCT_CODE,
        help="Target Products.Product_Code for the action's associated_record.",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print JSON only; no POST.",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="POST even if a rule with --name may already exist (may duplicate in Zoho).",
    )
    args = ap.parse_args()

    try:
        access, dom = _get_token_retry()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1

    session = requests.Session()
    session.headers.update(
        {**auth_headers(access), "Content-Type": "application/json"}
    )

    if not args.force:
        ex = _list_configurator_by_name(session, dom, _zoho_safe_name(args.name))
        if ex:
            print(
                f"  Product configurator {args.name!r} already present (id={ex}). "
                "Delete in Zoho or use --force / --name to create another."
            )
            return 0

    product_id = _find_product_id(session, dom, (args.product_code or "").strip())
    try:
        body = _build_payload(session, dom, args.name, product_id)
    except (RuntimeError, KeyError) as e:
        print(str(e), file=sys.stderr)
        return 1

    if args.dry_run:
        print("--- dry-run: resolved POST /settings/cpq/product_configurators ---\n")
        print(json.dumps(body, indent=2))
        return 0

    r = _crm(
        session,
        dom,
        "POST",
        "/settings/cpq/product_configurators",
        json=body,
    )
    if not r.ok:
        if r.status_code == 400 and "DUPLICATE_DATA" in (r.text or "") and "name" in (
            r.text or ""
        ):
            print(
                f"  Product configurator {_zoho_safe_name(args.name)!r} already exists "
                "for this layout (duplicate POST)."
            )
            return 0
        print(
            f"POST /settings/cpq/product_configurators HTTP {r.status_code}\n"
            f"{(r.text or '')[:5000]}\n",
            file=sys.stderr,
        )
        print(
            "\nIf the response is 500 or INVALID_DATA, Zoho’s CPQ payload is not fully documented. "
            "Create the same pilot in Setup → Developer Hub → CPQ → Product Configurator, "
            "or ask Zoho support for the official schema.",
            file=sys.stderr,
        )
        return 1
    try:
        out = r.json()
    except json.JSONDecodeError:
        print(r.text[:2000], file=sys.stderr)
        return 0
    print(json.dumps(out, indent=2)[:4000])
    print("  OK: Product configurator created (pilot). Review in Zoho and adjust actions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
