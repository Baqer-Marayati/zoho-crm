#!/usr/bin/env python3
"""
Upload Zoho Product Image from Canon official sources (not third-party stock).

Primary sources:
  • Canon Production Printing graphiPLAZA — product photography (PNG/JPEG on graphiplaza.cpp.canon).
  • Canon Amplience CDN (canon.a.bigcontent.io) — English datasheets / series brochures; we rasterise
    page 1 with PyMuPDF. These are the same PDFs linked from Canon regional sites.

If a download fails, falls back to local brochure PDF paths in upload_zoho_product_images.REL_PDF_BY_CODE.

Resize with Pillow (long edge --max-side; Zoho ~10 MP limit).

Usage:
  cd tools/zoho
  ./venv/bin/python upload_zoho_product_web_images.py
  ./venv/bin/python upload_zoho_product_web_images.py --product-code CANON-IP-V1000
  ./venv/bin/python upload_zoho_product_web_images.py --dry-run
"""
from __future__ import annotations

import argparse
import io
import sys
import tempfile
from pathlib import Path

import fitz  # PyMuPDF
import requests
from PIL import Image

from zoho_tokens import auth_headers, get_access_token_and_domain

from upload_zoho_product_images import DEFAULT_SPEC_ROOT, REL_PDF_BY_CODE

API_VER = "v8"

# Descriptive UA for HTTP fetches (Canon / graphiPLAZA)
HTTP_UA = (
    "ZohoCanonProductSync/1.0 (internal CRM catalog; "
    "Canon product imagery from graphiplaza.cpp.canon and canon.a.bigcontent.io)"
)

# -----------------------------------------------------------------------------
# Per–Product_Code sources:
#   • https://...     raster (JPEG/PNG/WebP)
#   • pdf:https://... official Canon PDF URL → render first page
# -----------------------------------------------------------------------------
PRODUCT_IMAGE_SOURCE: dict[str, str] = {
    # imagePRESS V — Canon Amplience datasheets (EM)
    "CANON-IP-V1000": "pdf:https://canon.a.bigcontent.io/v1/static/imagepress-v1000_datasheet_em_final_forweb_d39c614911b8449d99cd50f592cf42de",
    "CANON-IP-V1350": "pdf:https://canon.a.bigcontent.io/v1/static/imagepress-v1350_datasheet_em_final_forweb_c7ddd1cb90be4ac4a66f78fa1e169e5e",
    "CANON-IP-V9K-SER": "pdf:https://canon.a.bigcontent.io/v1/static/imagepress-v900-series_datasheet_em_final_forweb_03232d3e22e247c9b498cee4cf39874a",
    # varioPRINT — Canon Amplience
    "CANON-VP140-SER": "pdf:https://canon.a.bigcontent.io/v1/static/varioprint-140-series_datasheet_em_final_digi_0bfe776156a44f929a0487a25996361a",
    "CANON-VP6K-TITAN": "pdf:https://canon.a.bigcontent.io/v1/static/varioprint-6000-series-titan_data-sheet_em_final_forweb_cbe622c97fe34c8ab20abe92baf54030",
    # Wide-format roll (Colorado) — graphiPLAZA hero still
    "CANON-COLO-SER": "https://graphiplaza.cpp.canon/wp-content/uploads/2023/03/ColoradoM_Front_Left_Angle_Level_Up-rev200923-2048x1153.png",
    # Arizona flatbed — graphiPLAZA (2300 FLXflow product still, high-res PNG)
    "CANON-ARIZ-SER": "https://graphiplaza.cpp.canon/wp-content/uploads/2024/03/arizona-2300-flxflow-2048x1489.png",
    # Technical document systems — Canon Amplience series docs
    "CANON-CW-T-SER": "pdf:https://canon.a.bigcontent.io/v1/static/colorwave3600_data_sheet_emea_1.1_digi",
    "CANON-PW-T3035": "pdf:https://canon.a.bigcontent.io/v1/static/Plotwave_Series_EM_Final_LR",
    "CANON-PW-T5055": "pdf:https://canon.a.bigcontent.io/v1/static/Plotwave_Series_EM_Final_LR",
    "CANON-PW-T75": "pdf:https://canon.a.bigcontent.io/v1/static/Plotwave_Series_EM_Final_LR",
    # imagePROGRAF — Canon Amplience datasheets
    "CANON-IPF-TZ32000": "pdf:https://canon.a.bigcontent.io/v1/static/imageprograf-tz-32000_datasheet_em_final_forweb_6711925d5e884f4caa287019c7e5732a",
    "CANON-IPF-TX-SER": "pdf:https://canon.a.bigcontent.io/v1/static/imageprograf-tx-4200_datasheet_em_final_forweb_a1f16c874b3542c68984c904fa93b093",
    "CANON-IPF-TM-SER": "pdf:https://canon.a.bigcontent.io/v1/static/imageprograf-tm-300-mfp-z36_imageprograf-tm-305-mfp-z36_datasheet_em_final_digi_6aa970efcdc54b268b4cb2f4e5fd08ec",
    "CANON-IPF-TC21": "pdf:https://canon.a.bigcontent.io/v1/static/imageprograf-tc-21_datasheet_em_final_forweb_8dc100fc173145aaa580287eb356bdf3",
    "CANON-IPF-PRO-SER": "pdf:https://canon.a.bigcontent.io/v1/static/imageprograf_pro-2100_data_sheet_em_final_digi",
    "CANON-IPF-PRO1100": "pdf:https://canon.a.bigcontent.io/v1/static/imageprograf_pro-2100_data_sheet_em_final_digi",
    "CANON-IPF-GPS-SER": "pdf:https://canon.a.bigcontent.io/v1/static/imageprograf-gp-4000_datasheet_em_final_forweb_13016610674e49338207367754001fe3",
    "CANON-IPF-GP-CG-SER": "pdf:https://canon.a.bigcontent.io/v1/static/imageprograf-gp-4000_datasheet_em_final_forweb_13016610674e49338207367754001fe3",
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


def _render_pdf_jpeg(pdf: Path | bytes, out_path: Path, max_side: int, quality: int) -> None:
    if isinstance(pdf, Path):
        doc = fitz.open(pdf)
    else:
        doc = fitz.open(stream=pdf, filetype="pdf")
    try:
        page = doc[0]
        w, h = page.rect.width, page.rect.height
        scale = max_side / max(w, h)
        mat = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        pix.save(str(out_path), output="jpeg", jpg_quality=quality)
    finally:
        doc.close()


def _prepare_image_bytes(data: bytes, out_path: Path, max_side: int, quality: int) -> None:
    im = Image.open(io.BytesIO(data))
    if im.mode in ("RGBA", "LA"):
        background = Image.new("RGB", im.size, (255, 255, 255))
        background.paste(im, mask=im.split()[-1])
        im = background
    else:
        im = im.convert("RGB")
    im.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    im.save(out_path, "JPEG", quality=quality, optimize=True)


def _download(url: str, timeout: int = 120) -> bytes:
    r = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": HTTP_UA, "Accept": "*/*"},
    )
    r.raise_for_status()
    return r.content


def _upload_photo(session: requests.Session, base: str, product_id: str, image_path: Path) -> tuple[bool, str]:
    url = f"{base}/Products/{product_id}/photo"
    auth = session.headers.get("Authorization", "")
    with image_path.open("rb") as f:
        r = requests.post(
            url,
            headers={"Authorization": auth},
            files={"file": ("product.jpg", f, "image/jpeg")},
            timeout=180,
        )
    if r.ok:
        return True, r.text[:500]
    return False, f"HTTP {r.status_code}: {r.text[:1500]}"


def main() -> int:
    ap = argparse.ArgumentParser(description="Upload Zoho Product Image from Canon official URLs")
    ap.add_argument("--source", type=Path, default=DEFAULT_SPEC_ROOT, help="Canon specs root (local PDF fallback)")
    ap.add_argument("--max-side", type=int, default=2400)
    ap.add_argument("--quality", type=int, default=92)
    ap.add_argument("--product-code", type=str, default="")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    try:
        access, api_domain = get_access_token_and_domain()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1

    base = _crm_base(api_domain)
    session = requests.Session()
    session.headers.update(auth_headers(access))

    codes = [args.product_code] if args.product_code.strip() else list(PRODUCT_IMAGE_SOURCE.keys())

    ok_all = True
    for code in codes:
        if code not in PRODUCT_IMAGE_SOURCE:
            print(f"Unknown Product_Code: {code}", file=sys.stderr)
            ok_all = False
            continue
        pid = _product_id_by_code(session, base, code)
        if not pid:
            print(f"No Zoho product Product_Code={code}", file=sys.stderr)
            ok_all = False
            continue

        spec = PRODUCT_IMAGE_SOURCE[code]
        source_desc = ""

        if args.dry_run:
            print(f"\n{code} (id={pid}) [dry-run] source={spec[:100]}")
            continue

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            try:
                if spec.startswith("pdf:"):
                    pdf_url = spec[4:]
                    raw = _download(pdf_url)
                    if not raw.startswith(b"%PDF"):
                        raise ValueError("response is not a PDF")
                    _render_pdf_jpeg(raw, tmp_path, args.max_side, args.quality)
                    source_desc = f"Canon PDF p1: {pdf_url[:70]}…" if len(pdf_url) > 70 else f"Canon PDF p1: {pdf_url}"
                else:
                    raw = _download(spec)
                    _prepare_image_bytes(raw, tmp_path, args.max_side, args.quality)
                    source_desc = spec[:80] + ("…" if len(spec) > 80 else "")
            except Exception as e:
                print(f"  WARN: Canon source failed ({e}); trying local PDF fallback", file=sys.stderr)
                rel = REL_PDF_BY_CODE.get(code)
                if not rel:
                    print(f"  No local PDF mapping for {code}", file=sys.stderr)
                    ok_all = False
                    continue
                pdf_path = args.source / rel
                if not pdf_path.is_file():
                    print(f"  Missing PDF fallback: {pdf_path}", file=sys.stderr)
                    ok_all = False
                    continue
                _render_pdf_jpeg(pdf_path, tmp_path, args.max_side, args.quality)
                source_desc = f"local PDF fallback: {pdf_path.name}"

            print(f"\n{code} (id={pid}) ← {source_desc}")
            good, msg = _upload_photo(session, base, pid, tmp_path)
            if good:
                print(f"  OK: Product Image ({tmp_path.stat().st_size} bytes)")
            else:
                print(f"  FAIL: {msg}", file=sys.stderr)
                ok_all = False
        finally:
            tmp_path.unlink(missing_ok=True)

    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
