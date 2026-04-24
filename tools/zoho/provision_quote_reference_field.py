#!/usr/bin/env python3
"""
Quote **Subject** (api_name: Subject) is system-mandatory; it cannot be removed or moved
to another section via the Layouts API. This script:

  1) Renames the field label to **Reference** (field API name stays `Subject`).
  2) Optionally sets **read-only** on the standard Quotes layout (can block some client
     scripts from calling setValue — only use if you have verified autofill; default off).

Zoho will still require a value on save. Use the Client Script in
  ../../artifacts/zoho/client_scripts/quote_reference_autofill.js
(see QUOTE_REFERENCE_README.txt) so Reference fills from Deal / Account / timestamp.

**Moving the field in the form:** In CRM UI — Setup → Customization → Modules and Fields
→ Quotes → (your layout) — drag **Reference** to the bottom of **Quote Information** or
add an **Internal** section. The API cannot relocate system-mandatory fields.

OAuth: ZohoCRM.settings.fields.UPDATE, ZohoCRM.settings.layouts.UPDATE (read-only path)

  cd tools/zoho
  ./venv/bin/python provision_quote_reference_field.py
  ./venv/bin/python provision_quote_reference_field.py --dry-run
  ./venv/bin/python provision_quote_reference_field.py --verify
  ./venv/bin/python provision_quote_reference_field.py --set-read-only
"""
from __future__ import annotations

import argparse
import json
import sys

import requests

from zoho_tokens import auth_headers, get_access_token_and_domain

API_VER = "v8"
MODULE = "Quotes"
TARGET_LABEL = "Reference"
FIELD_API = "Subject"


def _session():
    try:
        access, dom = get_access_token_and_domain()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return None, None
    s = requests.Session()
    s.headers.update({**auth_headers(access), "Content-Type": "application/json"})
    return s, dom


def _get_subject_field(s: requests.Session, dom: str) -> dict | None:
    r = s.get(
        f"{dom.rstrip('/')}/crm/{API_VER}/settings/fields",
        params={"module": MODULE, "type": "all"},
        timeout=120,
    )
    if not r.ok:
        print(
            f"GET /settings/fields?module={MODULE} HTTP {r.status_code}: {r.text[:2000]}",
            file=sys.stderr,
        )
        return None
    for f in r.json().get("fields") or []:
        if f.get("api_name") == FIELD_API:
            return f
    print(f"Field {FIELD_API} not found on {MODULE}", file=sys.stderr)
    return None


def _default_layout_id(s: requests.Session, dom: str) -> str | None:
    r = s.get(
        f"{dom.rstrip('/')}/crm/{API_VER}/settings/layouts",
        params={"module": MODULE},
        timeout=120,
    )
    if not r.ok:
        print(f"GET layouts HTTP {r.status_code}: {r.text[:2000]}", file=sys.stderr)
        return None
    lo = (r.json().get("layouts") or [None])[0]
    if not lo or not lo.get("id"):
        return None
    return str(lo["id"])


def _section_with_field(
    s: requests.Session, dom: str, layout_id: str, field_id: str
) -> tuple[str | None, str | None]:
    r = s.get(
        f"{dom.rstrip('/')}/crm/{API_VER}/settings/layouts/{layout_id}",
        params={"module": MODULE},
        timeout=120,
    )
    if not r.ok:
        return None, None
    layout = (r.json().get("layouts") or [None])[0]
    if not layout:
        return None, None
    for sec in layout.get("sections") or []:
        for f in sec.get("fields") or []:
            if str(f.get("id")) == str(field_id):
                name = sec.get("name") or sec.get("display_label") or "?"
                return str(sec.get("id")), name
    return None, None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--verify", action="store_true", help="Print field + layout state; no writes"
    )
    ap.add_argument(
        "--set-read-only",
        action="store_true",
        help="Set Reference (Subject) to read-only on the default Quote layout. "
        "May prevent client script setValue in some orgs — use with care.",
    )
    ap.add_argument(
        "--no-read-only",
        action="store_true",
        help="Explicitly set read_only=false on the layout (undo --set-read-only).",
    )
    args = ap.parse_args()

    tok = _session()
    if not tok[0]:
        return 1
    s, dom = tok

    fmeta = _get_subject_field(s, dom)
    if not fmeta:
        return 1
    fid = str(fmeta["id"])
    cur = fmeta.get("field_label") or ""
    print(f"  {MODULE}.{FIELD_API} id={fid} current label: {cur!r}")

    lid = _default_layout_id(s, dom)
    if not lid:
        return 1
    sec_id, sec_name = _section_with_field(s, dom, lid, fid)
    if args.verify:
        if sec_id:
            print(f"  Default layout id={lid}; {FIELD_API} in section: {sec_name!r} (id={sec_id})")
        else:
            print(f"  Default layout id={lid}; {FIELD_API} not found in layout sections")
        if args.set_read_only or args.no_read_only:
            print("  --verify: ignoring read-only flags (no write)", file=sys.stderr)
        return 0

    if cur != TARGET_LABEL:
        if args.dry_run:
            print(f"  (dry-run) PATCH field label -> {TARGET_LABEL!r}")
        else:
            r = s.patch(
                f"{dom.rstrip('/')}/crm/{API_VER}/settings/fields/{fid}",
                params={"module": MODULE},
                json={"fields": [{"id": fid, "field_label": TARGET_LABEL}]},
                timeout=120,
            )
            if not r.ok:
                print(
                    f"PATCH field HTTP {r.status_code}: {r.text[:2000]}", file=sys.stderr
                )
                return 1
            print(f"  OK: label -> {TARGET_LABEL!r}")
    else:
        print(f"  Label already {TARGET_LABEL!r}; skip field PATCH.")

    if args.set_read_only and args.no_read_only:
        print("Use only one of --set-read-only / --no-read-only", file=sys.stderr)
        return 1

    if not args.set_read_only and not args.no_read_only:
        print("  Layout: no read-only change (default).")
        return 0

    if not sec_id:
        print("  Cannot resolve section for field; read-only not applied.", file=sys.stderr)
        return 1

    ro = True if args.set_read_only else False
    if args.dry_run:
        print(f"  (dry-run) PATCH layout {lid} section {sec_id} read_only={ro}")
        return 0

    r2 = s.patch(
        f"{dom.rstrip('/')}/crm/{API_VER}/settings/layouts/{lid}",
        params={"module": MODULE},
        json={
            "layouts": [
                {"sections": [{"id": sec_id, "fields": [{"id": fid, "read_only": ro}]}]}
            ]
        },
        timeout=120,
    )
    if not r2.ok:
        print(
            f"PATCH layout read_only HTTP {r2.status_code}: {r2.text[:2000]}",
            file=sys.stderr,
        )
        return 1
    try:
        print(json.dumps(r2.json(), indent=2)[:2000])
    except json.JSONDecodeError:
        print(r2.text[:2000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
