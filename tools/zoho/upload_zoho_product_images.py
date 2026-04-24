#!/usr/bin/env python3
"""
Render the first page of each product's Canon brochure/spec PDF to a JPEG and upload
to Zoho CRM as the record Product Image (POST /crm/v8/Products/{id}/photo).

Prefer **upload_zoho_product_web_images.py** for Canon official imagery (graphiPLAZA +
canon.a.bigcontent.io PDFs); use this script only for local brochure PDF first pages or
explicit PDF-based fallback.

Uses collateral under ~/Dropbox/Work/Canon/Canon machine specs for SAP. Long edge
default 2400px (Zoho ~10 MP / 10 MB).

Requires: PyMuPDF (pymupdf), requests, Zoho OAuth with Products write + photo scope.

Usage:
  cd tools/zoho
  ./venv/bin/python upload_zoho_product_images.py
  ./venv/bin/python upload_zoho_product_images.py --dry-run
  ./venv/bin/python upload_zoho_product_images.py --product-code CANON-IP-V1000
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import fitz  # PyMuPDF
import requests

from zoho_tokens import auth_headers, get_access_token_and_domain

API_VER = "v8"
SCRIPT_DIR = Path(__file__).resolve().parent

DEFAULT_SPEC_ROOT = Path.home() / "Dropbox/Work/Canon/Canon machine specs for SAP"

# Product_Code -> path relative to spec root (EN brochure preferred; AR if no EN)
REL_PDF_BY_CODE: dict[str, str] = {
    "CANON-VP6K-TITAN": "VarioPrint 6000 TITAN/VarioPrint 6000 TITAN Product Brochure AR.pdf",
    "CANON-IP-V1000": "imagePRESS V1000/imagePRESS V1000 Product Brochure EN.pdf",
    "CANON-IP-V1350": "imagePRESS V1350/imagePRESS V1350 Product Brochure EN.pdf",
    "CANON-IP-V9K-SER": "imagePRESS V900/imagePRESS V900 Product Brochure EN.pdf",
    "CANON-VP140-SER": "varioPRINT 140/varioprint 140 Product Brochure EN.pdf",
    "CANON-COLO-SER": "Colorado/Colorado-series_Brochure-with-Spec_2022_CanonCA.pdf",
    "CANON-ARIZ-SER": "Arizona/Arizona-1300-FLOW_Product-Brochure_CPP.pdf",
    "CANON-CW-T-SER": "LFP ME/CANON-CW-T-SER_colorWAVE-T-series_brochure.pdf",
    "CANON-PW-T3035": "LFP ME/CANON-PW-T3035_plotWAVE-T30-T35-spec.pdf",
    "CANON-PW-T5055": "LFP ME/CANON-PW-T5055_plotWAVE-T-series-brochure.pdf",
    "CANON-PW-T75": "LFP ME/CANON-PW-T75_plotWAVE-T75-datasheet.pdf",
    "CANON-IPF-TZ32000": "LFP ME/CANON-IPF-TZ32000_TZ-series-brochure.pdf",
    "CANON-IPF-TX-SER": "LFP ME/CANON-IPF-TX-SER_TX-series-brochure.pdf",
    "CANON-IPF-TM-SER": "LFP ME/CANON-IPF-TM-SER_TM-series-brochure.pdf",
    "CANON-IPF-TC21": "LFP ME/CANON-IPF-TC21_TC-20-line-brochure.pdf",
    "CANON-IPF-PRO-SER": "LFP ME/CANON-IPF-PRO-SER_PRO-2600-6600-brochure.pdf",
    "CANON-IPF-PRO1100": "LFP ME/CANON-IPF-PRO1100_PRO-1100-brochure.pdf",
    "CANON-IPF-GPS-SER": "LFP ME/CANON-IPF-GPS-SER_GP-S-brochure.pdf",
    "CANON-IPF-GP-CG-SER": "LFP ME/CANON-IPF-GP-CG-SER_GP-2000-4000-brochure.pdf",
}


def _crm_base(api_domain: str) -> str:
    return f"{api_domain.rstrip('/')}/crm/{API_VER}"


def _product_id_by_code(session: requests.Session, base: str, code: str) -> str | None:
    page = 1
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


def _render_first_page_jpeg(pdf_path: Path, out_path: Path, max_side: int, quality: int) -> None:
    doc = fitz.open(pdf_path)
    try:
        page = doc[0]
        w, h = page.rect.width, page.rect.height
        scale = max_side / max(w, h)
        mat = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        pix.save(str(out_path), output="jpeg", jpg_quality=quality)
    finally:
        doc.close()


def _upload_photo(session: requests.Session, base: str, product_id: str, image_path: Path) -> tuple[bool, str]:
    url = f"{base}/Products/{product_id}/photo"
    auth = session.headers.get("Authorization", "")
    with image_path.open("rb") as f:
        r = requests.post(
            url,
            headers={"Authorization": auth},
            files={"file": (image_path.name, f, "image/jpeg")},
            timeout=180,
        )
    if r.ok:
        return True, r.text[:500]
    return False, f"HTTP {r.status_code}: {r.text[:1500]}"


def main() -> int:
    ap = argparse.ArgumentParser(description="Upload Zoho Product Image from Canon brochure PDF cover")
    ap.add_argument("--source", type=Path, default=DEFAULT_SPEC_ROOT, help="Canon specs root folder")
    ap.add_argument("--max-side", type=int, default=2400, help="Long edge in pixels (keep under ~10 MP)")
    ap.add_argument("--quality", type=int, default=92, help="JPEG quality 1-100")
    ap.add_argument("--product-code", type=str, default="", help="Only this Product_Code")
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

    codes = [args.product_code] if args.product_code.strip() else list(REL_PDF_BY_CODE.keys())

    ok_all = True
    for code in codes:
        rel = REL_PDF_BY_CODE.get(code)
        if not rel:
            print(f"No PDF mapping for {code}", file=sys.stderr)
            ok_all = False
            continue
        pdf_path = args.source / rel
        if not pdf_path.is_file():
            print(f"Missing PDF for {code}: {pdf_path}", file=sys.stderr)
            ok_all = False
            continue

        pid = _product_id_by_code(session, base, code)
        if not pid:
            print(f"No Zoho product Product_Code={code}", file=sys.stderr)
            ok_all = False
            continue

        print(f"\n{code} (id={pid}) ← {pdf_path.name}")
        if args.dry_run:
            print("  [dry-run] would render page 1 → JPEG → POST /photo")
            continue

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            _render_first_page_jpeg(pdf_path, tmp_path, args.max_side, args.quality)
            good, msg = _upload_photo(session, base, pid, tmp_path)
            if good:
                print(f"  OK: Product Image uploaded ({tmp_path.stat().st_size} bytes)")
            else:
                print(f"  FAIL: {msg}", file=sys.stderr)
                ok_all = False
        finally:
            tmp_path.unlink(missing_ok=True)

    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
