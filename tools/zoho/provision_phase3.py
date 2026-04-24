#!/usr/bin/env python3
"""
provision_phase3.py — Phase 3: Products & Quotes for Zoho CRM (API v8).

Steps (--step N runs only that step; omit for all):
  1  IQD Standard Price Book  — idempotent GET before POST to /crm/v8/Price_Books
  2  Wave A products import   — CSV check + batch POST to /crm/v8/Products
  3  Quote/Deal layout fields  — Payment Terms (picklist) + Contract Folder URL (url)
                                 on Quotes; Contract Folder URL on Deals
  4  Quotes attachments       — read-only layout check; prints status only

Modes:
  --step N    Run only step N (1–4)
  --verify    Verify-only: confirm state, no writes
  --dry-run   Print planned actions; no API writes

OAuth scopes:
  ZohoCRM.settings.ALL   required for steps 3 + 4 (field/layout settings)
  ZohoCRM.modules.ALL    required for steps 1 + 2 (Price_Books, Products records)

Usage:
  cd tools/zoho && ./venv/bin/python provision_phase3.py
  ./venv/bin/python provision_phase3.py --step 1
  ./venv/bin/python provision_phase3.py --step 2 --products-csv ../../artifacts/zoho/import/canon_products_wave_a_en.csv
  ./venv/bin/python provision_phase3.py --step 2 --products-csv ../../artifacts/zoho/import/canon_products_five_machines_en.csv
  ./venv/bin/python provision_phase3.py --verify
  ./venv/bin/python provision_phase3.py --dry-run
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
PICKLISTS_DIR = REPO_ROOT / "artifacts" / "zoho" / "picklists"
IMPORT_DIR = REPO_ROOT / "artifacts" / "zoho" / "import"

# Layout IDs (confirmed in live org)
QUOTES_LAYOUT_ID = "7353692000000091017"
DEALS_LAYOUT_ID = "7353692000000091023"

PRICE_BOOK_NAME = "Standard IQD"
PAYMENT_TERMS_LABEL = "Payment Terms"
CONTRACT_URL_LABEL = "Contract Folder URL"
PRODUCTS_CSV = IMPORT_DIR / "products_wave_a_template.csv"
PAYMENT_TERMS_CSV = PICKLISTS_DIR / "payment_terms.csv"


# ─── Shared helpers ───────────────────────────────────────────────────────────

def _crm(session: requests.Session, api_domain: str, method: str, path: str, **kwargs):
    url = f"{api_domain.rstrip('/')}/crm/{API_VER}{path}"
    return session.request(method, url, timeout=120, **kwargs)


def _slug(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", s.strip()).strip("_")[:100] or "value"


def _get_layout(
    session: requests.Session, api_domain: str, layout_id: str, module: str
) -> dict | None:
    r = _crm(
        session, api_domain, "GET", f"/settings/layouts/{layout_id}",
        params={"module": module},
    )
    if not r.ok:
        print(
            f"  GET layout {layout_id} ({module}) HTTP {r.status_code}: {r.text[:2000]}",
            file=sys.stderr,
        )
        return None
    layouts = r.json().get("layouts") or []
    return layouts[0] if layouts else None


def _get_fields_by_label(
    session: requests.Session, api_domain: str, module: str
) -> dict[str, dict]:
    r = _crm(session, api_domain, "GET", "/settings/fields", params={"module": module})
    if not r.ok:
        raise RuntimeError(
            f"GET /settings/fields?module={module} HTTP {r.status_code}: {r.text[:2000]}"
        )
    return {
        (f.get("field_label") or "").strip().lower(): f
        for f in r.json().get("fields") or []
        if f.get("field_label")
    }


def _post_field(
    session: requests.Session,
    api_domain: str,
    module: str,
    field_def: dict,
    dry_run: bool,
) -> str | None:
    """POST a new field. Returns field_id string, 'dry_run', or None on error."""
    label = field_def.get("field_label", "?")
    print(f"  POST field '{label}' (type={field_def.get('data_type')}) → {module}")
    if dry_run:
        return "dry_run"
    r = _crm(
        session, api_domain, "POST", "/settings/fields",
        params={"module": module},
        json={"fields": [field_def]},
    )
    if not r.ok:
        print(f"  HTTP {r.status_code}: {r.text[:3000]}", file=sys.stderr)
        return None
    try:
        resp = r.json()
        print(json.dumps(resp, indent=2)[:2000])
        for item in resp.get("fields") or []:
            fid = (item.get("details") or {}).get("id") or item.get("id")
            if fid:
                return str(fid)
    except json.JSONDecodeError:
        print(r.text[:2000])
    return None


def _field_in_layout_sections(layout: dict, field_id: str) -> str | None:
    """Return section name if field is already in a non-unused section, else None."""
    for sec in layout.get("sections") or []:
        for f in sec.get("fields") or []:
            if str(f.get("id")) == str(field_id):
                return sec.get("name") or sec.get("display_label") or "?"
    return None


def _find_target_section(layout: dict, preferred_name: str | None = None) -> dict | None:
    """Return the best section to add a field to, by preferred name or first active one."""
    sections = layout.get("sections") or []
    if preferred_name:
        for sec in sections:
            sec_name = (sec.get("name") or sec.get("display_label") or "").lower()
            if sec_name == preferred_name.lower():
                return sec
        # Fuzzy: prefer section whose name contains a key word from preferred_name
        for word in preferred_name.split():
            for sec in sections:
                sec_name = (sec.get("name") or sec.get("display_label") or "").lower()
                if word.lower() in sec_name and sec.get("id") and sec.get("fields") is not None:
                    return sec
    # Fallback: first section that has an id and a fields list
    for sec in sections:
        if sec.get("id") and sec.get("fields") is not None:
            return sec
    return sections[0] if sections else None


def _patch_layout_add_field(
    session: requests.Session,
    api_domain: str,
    layout_id: str,
    module: str,
    section_id: str,
    field_id: str,
    field_label: str,
    dry_run: bool,
) -> bool:
    print(
        f"  PATCH layout {layout_id} ({module}): add '{field_label}' "
        f"to section {section_id}"
    )
    if dry_run:
        return True
    patch = {
        "layouts": [
            {
                "sections": [
                    {
                        "id": str(section_id),
                        "fields": [{"id": str(field_id)}],
                    }
                ]
            }
        ]
    }
    r = _crm(
        session, api_domain, "PATCH", f"/settings/layouts/{layout_id}",
        params={"module": module},
        json=patch,
    )
    if not r.ok:
        print(f"  HTTP {r.status_code}: {r.text[:3000]}", file=sys.stderr)
        return False
    try:
        print(json.dumps(r.json(), indent=2)[:2000])
    except json.JSONDecodeError:
        print(f"  HTTP {r.status_code} OK")
    return True


def _ensure_field_on_layout(
    session: requests.Session,
    api_domain: str,
    module: str,
    layout_id: str,
    field_id: str,
    field_label: str,
    section_hint: str | None,
    dry_run: bool,
) -> bool:
    """Make sure field_id is in an active section of the given layout."""
    layout = _get_layout(session, api_domain, layout_id, module)
    if not layout:
        return False
    sec_name = _field_in_layout_sections(layout, field_id)
    if sec_name:
        print(
            f"  Field '{field_label}' already on {module} layout "
            f"section '{sec_name}'; skip PATCH."
        )
        return True
    sec = _find_target_section(layout, section_hint)
    if not sec or not sec.get("id"):
        print(
            f"  No suitable section found in {module} layout; cannot place '{field_label}'.",
            file=sys.stderr,
        )
        return False
    sec_display = sec.get("name") or sec.get("display_label") or sec["id"]
    print(f"  Target section for '{field_label}': '{sec_display}' (id={sec.get('id')})")
    return _patch_layout_add_field(
        session, api_domain, layout_id, module,
        str(sec["id"]), field_id, field_label, dry_run,
    )


def _ensure_picklist_field(
    session: requests.Session,
    api_domain: str,
    module: str,
    layout_id: str,
    label: str,
    values: list[str],
    section_hint: str | None,
    dry_run: bool,
) -> bool:
    fields = _get_fields_by_label(session, api_domain, module)
    label_lower = label.lower()
    field_id: str | None = None

    if label_lower in fields:
        field_id = str(fields[label_lower]["id"])
        print(f"  Field '{label}' exists on {module} (id={field_id}); skip create.")
    else:
        pick_vals = [{"display_value": v, "actual_value": _slug(v)} for v in values]
        field_def: dict[str, Any] = {
            "field_label": label,
            "data_type": "picklist",
            "pick_list_values": pick_vals,
            "pick_list_values_sorted_lexically": False,
            "enable_colour_code": False,
        }
        result = _post_field(session, api_domain, module, field_def, dry_run)
        if result == "dry_run":
            print(f"  (dry-run) Would add '{label}' to {module} layout {layout_id}")
            return True
        if not result:
            return False
        field_id = result

    return _ensure_field_on_layout(
        session, api_domain, module, layout_id,
        field_id, label, section_hint, dry_run,
    )


def _ensure_url_field(
    session: requests.Session,
    api_domain: str,
    module: str,
    layout_id: str,
    label: str,
    section_hint: str | None,
    dry_run: bool,
) -> bool:
    fields = _get_fields_by_label(session, api_domain, module)
    label_lower = label.lower()
    field_id: str | None = None

    if label_lower in fields:
        field_id = str(fields[label_lower]["id"])
        print(f"  Field '{label}' exists on {module} (id={field_id}); skip create.")
    else:
        # Zoho CRM custom field data_type for text: "text" (single line, 255 chars).
        # The "url" type is not available for custom fields — use text with the label
        # making the SharePoint intent clear.
        field_def: dict[str, Any] = {
            "field_label": label,
            "data_type": "text",
        }
        result = _post_field(session, api_domain, module, field_def, dry_run)
        if result == "dry_run":
            print(f"  (dry-run) Would add '{label}' to {module} layout {layout_id}")
            return True
        if not result:
            return False
        field_id = result

    return _ensure_field_on_layout(
        session, api_domain, module, layout_id,
        field_id, label, section_hint, dry_run,
    )


# ─── Step 1: IQD Price Book ───────────────────────────────────────────────────

def step1_price_book(session: requests.Session, api_domain: str, dry_run: bool) -> bool:
    print("\n=== Step 1: IQD Standard Price Book ===")
    # Zoho CRM v8 GET /Price_Books requires at minimum a 'fields' param
    r = _crm(
        session, api_domain, "GET", "/Price_Books",
        params={"fields": "id,Price_Book_Name,Active"},
    )
    existing: list[dict] = []
    if r.status_code == 204:
        pass  # none yet
    elif r.ok:
        body = r.json()
        existing = body.get("data") or body.get("Price_Books") or []
    else:
        print(f"  GET /Price_Books HTTP {r.status_code}: {r.text[:2000]}", file=sys.stderr)
        if r.status_code in (401, 403) or "OAUTH_SCOPE_MISMATCH" in r.text:
            print(
                "  → Scope error: token needs ZohoCRM.modules.ALL. "
                "Generate a new grant and update ZOHO_REFRESH_TOKEN in .env.",
                file=sys.stderr,
            )
        return False

    # Price_Book_Name is the API field name (not "Name")
    for pb in existing:
        pb_name = (
            pb.get("Price_Book_Name") or pb.get("Name") or pb.get("name") or ""
        ).strip()
        if pb_name.lower() == PRICE_BOOK_NAME.lower():
            print(
                f"  Skip: '{PRICE_BOOK_NAME}' already exists "
                f"(id={pb.get('id')})."
            )
            return True

    print(f"  Creating price book: '{PRICE_BOOK_NAME}' (Flat pricing)")
    if dry_run:
        return True

    # Zoho CRM v8 Price Books: mandatory field is Price_Book_Name (not Name).
    # Currency is at the org level; Pricing_Details accepts a list for range pricing.
    # Note: multi-currency Price_Books require enabling multi-currency in org settings.
    payload: dict[str, Any] = {
        "data": [
            {
                "Price_Book_Name": PRICE_BOOK_NAME,
                "Pricing_Model": "Flat",
                "Active": True,
                "Pricing_Details": [{"from_range": 1, "to_range": 1000000, "discount": 0.0}],
            }
        ]
    }
    r2 = _crm(session, api_domain, "POST", "/Price_Books", json=payload)
    if not r2.ok:
        print(f"  POST /Price_Books HTTP {r2.status_code}: {r2.text[:3000]}", file=sys.stderr)
        return False

    try:
        body2 = r2.json()
        print(f"  HTTP {r2.status_code} OK")
        print(json.dumps(body2, indent=2)[:2000])
        items = body2.get("data") or []
        for item in items:
            code = (item.get("code") or item.get("status") or "").upper()
            if code not in ("SUCCESS", ""):
                print(f"  Item status: {item}", file=sys.stderr)
    except json.JSONDecodeError:
        print(f"  HTTP {r2.status_code} OK (non-JSON)")
    return True


# ─── Step 2: Wave A Products ──────────────────────────────────────────────────

def _read_products_csv(path: Path) -> tuple[list[dict], bool]:
    """Returns (rows, has_placeholder). has_placeholder if any row contains 'example sku'."""
    rows: list[dict] = []
    has_placeholder = False
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if any("example sku" in (v or "").lower() for v in row.values()):
                has_placeholder = True
            rows.append(row)
    return rows, has_placeholder


def _norm_product_name(name: str) -> str:
    return (name or "").strip().casefold()


def _fetch_existing_products_keys(
    session: requests.Session, api_domain: str
) -> tuple[set[str], set[str]]:
    """Existing Product_Code (non-empty) and normalized Product_Name for idempotency."""
    existing_codes: set[str] = set()
    existing_names: set[str] = set()
    page = 1
    while True:
        r = _crm(
            session,
            api_domain,
            "GET",
            "/Products",
            params={
                "fields": "Product_Name,Product_Code",
                "per_page": 200,
                "page": page,
            },
        )
        if r.status_code == 204:
            break
        if not r.ok:
            print(
                f"  GET /Products (page {page}) HTTP {r.status_code}: {r.text[:1500]}",
                file=sys.stderr,
            )
            if r.status_code in (401, 403) or "OAUTH_SCOPE_MISMATCH" in r.text:
                print("  → Token needs ZohoCRM.modules.ALL scope.", file=sys.stderr)
            raise RuntimeError("Cannot list Products for idempotency check")
        body = r.json()
        for p in body.get("data") or []:
            code = (p.get("Product_Code") or "").strip()
            if code:
                existing_codes.add(code)
            n = _norm_product_name(p.get("Product_Name") or "")
            if n:
                existing_names.add(n)
        info = body.get("info") or {}
        if not info.get("more_records"):
            break
        page += 1
    return existing_codes, existing_names


def step2_products(
    session: requests.Session,
    api_domain: str,
    dry_run: bool,
    csv_path: Path | None = None,
) -> bool:
    print("\n=== Step 2: Wave A Products Import ===")
    path = csv_path or PRODUCTS_CSV
    if not path.is_file():
        print(f"  CSV not found: {path}", file=sys.stderr)
        return False

    rows, has_placeholder = _read_products_csv(path)
    if has_placeholder:
        try:
            rel = path.relative_to(REPO_ROOT)
        except ValueError:
            rel = path
        print(
            f"  Wave A CSV still has placeholder rows — replace "
            f"`{rel}` with real products and re-run.\n"
            "  (Skipping import; this is not an error.)"
        )
        return True  # not a failure

    if not rows:
        print("  CSV has no data rows; skip.")
        return True

    try:
        existing_codes, existing_names = _fetch_existing_products_keys(session, api_domain)
    except RuntimeError:
        return False
    print(
        f"  Idempotency: {len(existing_codes)} product(s) with Product_Code, "
        f"{len(existing_names)} distinct name(s) in org."
    )

    to_create: list[dict[str, Any]] = []
    pending_names: set[str] = set()
    for row in rows:
        code = (row.get("Product_Code") or "").strip()
        name = (row.get("Product_Name") or "").strip()
        if not name:
            continue
        nk = _norm_product_name(name)
        if code and code in existing_codes:
            print(f"  Skip (exists by code): {code} — {name}")
            continue
        if nk in existing_names or nk in pending_names:
            print(f"  Skip (exists by name): {name}")
            continue
        pending_names.add(nk)
        product: dict[str, Any] = {"Product_Name": name}
        if code:
            product["Product_Code"] = code
        price_str = (row.get("Unit_Price") or "0").strip()
        try:
            product["Unit_Price"] = float(price_str)
        except ValueError:
            pass
        qty_str = (row.get("Qty_in_Stock") or "0").strip()
        try:
            product["Qty_in_Stock"] = int(float(qty_str))
        except ValueError:
            pass
        desc = (row.get("Description") or "").strip()
        if desc:
            product["Description"] = desc
        to_create.append(product)

    if not to_create:
        print("  All products already exist; skip.")
        return True

    # Batch POST up to 100 at a time
    batch_size = 100
    total_ok = 0
    ok = True
    for i in range(0, len(to_create), batch_size):
        batch = to_create[i : i + batch_size]
        n = i // batch_size + 1
        print(f"  POST /Products batch {n}: {len(batch)} record(s)")
        if dry_run:
            total_ok += len(batch)
            continue
        r2 = _crm(session, api_domain, "POST", "/Products", json={"data": batch})
        if not r2.ok:
            print(f"  HTTP {r2.status_code}: {r2.text[:2000]}", file=sys.stderr)
            ok = False
            continue
        try:
            body = r2.json()
            print(json.dumps(body, indent=2)[:2000])
            for item in body.get("data") or []:
                if (item.get("code") or item.get("status") or "").upper() == "SUCCESS":
                    total_ok += 1
                else:
                    print(f"  Item status: {item}", file=sys.stderr)
                    ok = False
        except json.JSONDecodeError:
            print(f"  HTTP {r2.status_code} (non-JSON)", file=sys.stderr)
            ok = False

    print(f"  Products POST total: {total_ok}/{len(to_create)} successful")
    return ok


# ─── Step 3: Quote/Deal Layout Fields ────────────────────────────────────────

def step3_layout_fields(session: requests.Session, api_domain: str, dry_run: bool) -> bool:
    print("\n=== Step 3: Quote/Deal Layout Fields ===")
    ok = True

    # Payment Terms picklist on Quotes
    print("\n  ── Payment Terms picklist → Quotes ──")
    if not PAYMENT_TERMS_CSV.is_file():
        print(f"  Missing: {PAYMENT_TERMS_CSV}", file=sys.stderr)
        ok = False
    else:
        payment_vals: list[str] = []
        with PAYMENT_TERMS_CSV.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            col = (reader.fieldnames or ["Display_Value"])[0]
            for row in reader:
                val = (row.get(col) or "").strip()
                if val:
                    payment_vals.append(val)
        print(f"  {len(payment_vals)} payment terms values loaded from CSV.")
        ok = (
            _ensure_picklist_field(
                session, api_domain, "Quotes", QUOTES_LAYOUT_ID,
                PAYMENT_TERMS_LABEL, payment_vals, "Quote Information", dry_run,
            )
            and ok
        )

    # Contract Folder URL on Deals
    print("\n  ── Contract Folder URL → Deals ──")
    ok = (
        _ensure_url_field(
            session, api_domain, "Deals", DEALS_LAYOUT_ID,
            CONTRACT_URL_LABEL, "Deal Information", dry_run,
        )
        and ok
    )

    # Contract Folder URL on Quotes
    print("\n  ── Contract Folder URL → Quotes ──")
    ok = (
        _ensure_url_field(
            session, api_domain, "Quotes", QUOTES_LAYOUT_ID,
            CONTRACT_URL_LABEL, "Quote Information", dry_run,
        )
        and ok
    )

    return ok


# ─── Step 4: Quotes Attachments Confirmation ─────────────────────────────────

def step4_attachments(session: requests.Session, api_domain: str) -> bool:
    print("\n=== Step 4: Quotes Attachments Confirmation ===")
    layout = _get_layout(session, api_domain, QUOTES_LAYOUT_ID, "Quotes")
    if not layout:
        return False

    related_lists = layout.get("related_lists") or []
    att = next(
        (
            rl
            for rl in related_lists
            if "attach" in (rl.get("api_name") or rl.get("name") or "").lower()
        ),
        None,
    )
    if att:
        print(
            f"  OK: Attachments related list found on Quotes layout "
            f"(api_name='{att.get('api_name') or att.get('name')}', "
            f"label='{att.get('display_label') or att.get('label') or '?'}')."
        )
        print("  Zoho Attachments are always available — no configuration needed.")
    else:
        rl_names = [rl.get("api_name") or rl.get("name") for rl in related_lists]
        print(
            f"  NOTE: 'Attachments' not found in layout related_lists "
            f"({rl_names}).\n"
            "  This is usually fine — Zoho Attachments appear automatically in the "
            "Quotes record view without layout configuration."
        )
    return True


# ─── Verify Mode ─────────────────────────────────────────────────────────────

def run_verify(session: requests.Session, api_domain: str) -> None:
    print("\n══════════════════════════════════════")
    print("  Phase 3 — Verification Report")
    print("══════════════════════════════════════")
    all_ok = True

    # [1] Price Book
    print("\n[1] IQD Price Book")
    r = _crm(session, api_domain, "GET", "/Price_Books", params={"fields": "id,Price_Book_Name,Active"})
    if r.status_code == 204:
        print(f"  FAIL: No price books found (HTTP 204).")
        all_ok = False
    elif r.ok:
        body = r.json()
        pbs = body.get("data") or body.get("Price_Books") or []
        match = [
            pb for pb in pbs
            if (
                pb.get("Price_Book_Name") or pb.get("Name") or pb.get("name") or ""
            ).strip().lower() == PRICE_BOOK_NAME.lower()
        ]
        if match:
            pb = match[0]
            print(
                f"  OK: '{pb.get('Price_Book_Name') or pb.get('Name')}' "
                f"active={pb.get('Active')} id={pb.get('id')}"
            )
        else:
            names = [
                pb.get("Price_Book_Name") or pb.get("Name") for pb in pbs
            ]
            print(f"  FAIL: '{PRICE_BOOK_NAME}' not found. Existing: {names}")
            all_ok = False
    else:
        print(f"  ERROR: GET /Price_Books HTTP {r.status_code}")
        all_ok = False

    # [2] Products
    print("\n[2] Wave A Products")
    canon_csv = REPO_ROOT / "artifacts" / "zoho" / "import" / "canon_products_wave_a_en.csv"
    csv_check = PRODUCTS_CSV if PRODUCTS_CSV.is_file() else canon_csv
    if csv_check.is_file():
        _, has_ph = _read_products_csv(csv_check)
        if has_ph:
            print(
                "  NOTE: Wave A CSV still has placeholder rows — "
                "import skipped until real SKUs are added."
            )
        else:
            r2 = _crm(session, api_domain, "GET", "/Products", params={"per_page": 1})
            if r2.status_code == 204:
                print("  NOTE: No products in org yet.")
            elif r2.ok:
                info = r2.json().get("info") or {}
                count = info.get("count") or "?"
                print(f"  OK: {count} product(s) in org.")
            else:
                print(f"  ERROR: GET /Products HTTP {r2.status_code}")
                all_ok = False
    else:
        print(f"  NOTE: No product CSV at {PRODUCTS_CSV} or {canon_csv}.")

    # [3] Fields
    print("\n[3] Layout Fields")
    checks = [
        ("Quotes", QUOTES_LAYOUT_ID, PAYMENT_TERMS_LABEL, "picklist"),
        ("Deals", DEALS_LAYOUT_ID, CONTRACT_URL_LABEL, "url/text"),
        ("Quotes", QUOTES_LAYOUT_ID, CONTRACT_URL_LABEL, "url/text"),
    ]
    for module, layout_id, label, expected_type in checks:
        try:
            fields = _get_fields_by_label(session, api_domain, module)
        except RuntimeError as e:
            print(f"  ERROR: {e}")
            all_ok = False
            continue
        label_lower = label.lower()
        if label_lower in fields:
            f = fields[label_lower]
            extra = ""
            if f.get("data_type") == "picklist":
                extra = f", {len(f.get('pick_list_values') or [])} options"
            print(
                f"  OK: '{label}' on {module} "
                f"(id={f.get('id')}, type={f.get('data_type')}{extra})"
            )
        else:
            print(f"  FAIL: '{label}' not found on {module}")
            all_ok = False

    # [4] Attachments
    print("\n[4] Quotes Attachments")
    layout = _get_layout(session, api_domain, QUOTES_LAYOUT_ID, "Quotes")
    if layout:
        related_lists = layout.get("related_lists") or []
        has_att = any(
            "attach" in (rl.get("api_name") or rl.get("name") or "").lower()
            for rl in related_lists
        )
        tag = "OK" if has_att else "NOTE"
        print(
            f"  {tag}: Attachments in related_lists: {has_att} "
            "(standard Zoho feature — always available in UI)"
        )
    else:
        print("  NOTE: Could not fetch Quotes layout.")

    print(
        f"\n{'═'*38}\n  Result: {'PASS ✓' if all_ok else 'FAIL — see items above'}\n"
        f"{'═'*38}"
    )


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 3: Products & Quotes for Zoho CRM")
    parser.add_argument(
        "--step", type=int, choices=[1, 2, 3, 4],
        help="Run only step N; omit to run all steps in order",
    )
    parser.add_argument(
        "--verify", action="store_true",
        help="Verify-only: confirm state without making changes",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print planned actions; no API writes",
    )
    parser.add_argument(
        "--products-csv",
        type=Path,
        default=None,
        help=f"CSV for step 2 only (default: {PRODUCTS_CSV})",
    )
    args = parser.parse_args()

    try:
        access, api_domain = get_access_token_and_domain()
    except RuntimeError as e:
        print(e, file=sys.stderr)
        return 1

    session = requests.Session()
    session.headers.update(auth_headers(access))

    if args.verify:
        run_verify(session, api_domain)
        return 0

    run_all = args.step is None
    ok = True

    if run_all or args.step == 1:
        ok = step1_price_book(session, api_domain, args.dry_run) and ok
    if run_all or args.step == 2:
        ok = step2_products(
            session, api_domain, args.dry_run, args.products_csv,
        ) and ok
    if run_all or args.step == 3:
        ok = step3_layout_fields(session, api_domain, args.dry_run) and ok
    if run_all or args.step == 4:
        ok = step4_attachments(session, api_domain) and ok

    label = f"step {args.step}" if args.step else "all steps"
    print(f"\n─── Phase 3 {label} complete | ok={ok} dry_run={args.dry_run} ───")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
