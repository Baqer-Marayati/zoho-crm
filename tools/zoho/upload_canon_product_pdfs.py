#!/usr/bin/env python3
"""
Upload PDFs from the Canon machine specs folder to matching Zoho Products (Attachments API v8).

Default source: ~/Dropbox/Work/Canon/Canon machine specs for SAP
Mapping: subfolder name -> Product_Code (five-machine catalog).

Requires OAuth scopes that include attachment create on Products, e.g. ZohoCRM.modules.ALL
or ZohoCRM.modules.attachments.CREATE.

Usage:
  cd tools/zoho
  ./venv/bin/python upload_canon_product_pdfs.py
  ./venv/bin/python upload_canon_product_pdfs.py --dry-run
  ./venv/bin/python upload_canon_product_pdfs.py --source "/path/to/specs"
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import requests

from zoho_tokens import auth_headers, get_access_token_and_domain

API_VER = "v8"

# Subfolder (under --source) -> Product_Code
FOLDER_TO_CODE: dict[str, str] = {
    "VarioPrint 6000 TITAN": "CANON-VP6K-TITAN",
    "imagePRESS V1000": "CANON-IP-V1000",
    "imagePRESS V1350": "CANON-IP-V1350",
    "imagePRESS V900": "CANON-IP-V9K-SER",
    "varioPRINT 140": "CANON-VP140-SER",
    "Colorado": "CANON-COLO-SER",
    "Arizona": "CANON-ARIZ-SER",
}

DEFAULT_SOURCE = Path.home() / "Dropbox/Work/Canon/Canon machine specs for SAP"

# PDFs in ``<source>/LFP ME/`` named ``{Product_Code}_*.pdf`` (from regional brochures).
LFP_ME_PRODUCT_CODES: tuple[str, ...] = (
    "CANON-CW-T-SER",
    "CANON-PW-T3035",
    "CANON-PW-T5055",
    "CANON-PW-T75",
    "CANON-IPF-TZ32000",
    "CANON-IPF-TX-SER",
    "CANON-IPF-TM-SER",
    "CANON-IPF-TC21",
    "CANON-IPF-PRO-SER",
    "CANON-IPF-PRO1100",
    "CANON-IPF-GPS-SER",
    "CANON-IPF-GP-CG-SER",
)


def _crm_base(api_domain: str) -> str:
    return f"{api_domain.rstrip('/')}/crm/{API_VER}"


def _product_id_by_code(session: requests.Session, base: str, code: str) -> str | None:
    page = 1
    h = dict(session.headers)
    while True:
        r = session.get(
            f"{base}/Products",
            params={"fields": "id,Product_Code", "per_page": 200, "page": page},
            timeout=120,
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


def _upload_pdf(
    session: requests.Session,
    base: str,
    product_id: str,
    pdf_path: Path,
) -> tuple[bool, str]:
    url = f"{base}/Products/{product_id}/Attachments"
    auth = session.headers.get("Authorization", "")
    # multipart: do not send Content-Type: application/json
    with pdf_path.open("rb") as f:
        files = {"file": (pdf_path.name, f, "application/pdf")}
        r = requests.post(
            url,
            headers={"Authorization": auth},
            files=files,
            timeout=300,
        )
    if r.ok:
        return True, r.text[:500]
    return False, f"HTTP {r.status_code}: {r.text[:1500]}"


def main() -> int:
    ap = argparse.ArgumentParser(description="Upload Canon PDF specs to Zoho Products")
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="Canon specs root folder")
    ap.add_argument(
        "--lfp-me-only",
        action="store_true",
        help="Only upload PDFs from LFP ME/ (skip VarioPrint/imagePRESS/Colorado/Arizona folders)",
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.source.is_dir():
        print(f"Source not found: {args.source}", file=sys.stderr)
        return 1

    try:
        access, api_domain = get_access_token_and_domain()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1

    base = _crm_base(api_domain)
    session = requests.Session()
    session.headers.update(auth_headers(access))

    ok_all = True
    if not args.lfp_me_only:
        for folder_name, code in FOLDER_TO_CODE.items():
            sub = args.source / folder_name
            if not sub.is_dir():
                print(f"Skip missing folder: {sub}", file=sys.stderr)
                ok_all = False
                continue
            pdfs = sorted(sub.glob("*.pdf")) + sorted(sub.glob("*.PDF"))
            pdfs = [p for p in pdfs if p.is_file()]
            if not pdfs:
                print(f"No PDFs in {sub}", file=sys.stderr)
                continue

            pid = _product_id_by_code(session, base, code)
            if not pid:
                print(f"No Zoho product Product_Code={code}", file=sys.stderr)
                ok_all = False
                continue

            print(f"\n{code} (id={pid}) ← {len(pdfs)} file(s) from {folder_name}")
            for pdf in pdfs:
                if args.dry_run:
                    print(f"  [dry-run] {pdf.name}")
                    continue
                good, msg = _upload_pdf(session, base, pid, pdf)
                if good:
                    print(f"  OK: {pdf.name}")
                else:
                    print(f"  FAIL: {pdf.name} — {msg}", file=sys.stderr)
                    ok_all = False
                time.sleep(0.35)

    lfp_dir = args.source / "LFP ME"
    if lfp_dir.is_dir():
        for code in LFP_ME_PRODUCT_CODES:
            pdfs = sorted(lfp_dir.glob(f"{code}_*.pdf")) + sorted(lfp_dir.glob(f"{code}_*.PDF"))
            pdfs = [p for p in pdfs if p.is_file()]
            if not pdfs:
                print(f"No LFP ME PDF matching {code}_*.pdf in {lfp_dir}", file=sys.stderr)
                ok_all = False
                continue
            pid = _product_id_by_code(session, base, code)
            if not pid:
                print(f"No Zoho product Product_Code={code}", file=sys.stderr)
                ok_all = False
                continue
            print(f"\n{code} (id={pid}) ← {len(pdfs)} file(s) from LFP ME")
            for pdf in pdfs:
                if args.dry_run:
                    print(f"  [dry-run] {pdf.name}")
                    continue
                good, msg = _upload_pdf(session, base, pid, pdf)
                if good:
                    print(f"  OK: {pdf.name}")
                else:
                    print(f"  FAIL: {pdf.name} — {msg}", file=sys.stderr)
                    ok_all = False
                time.sleep(0.35)

    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
