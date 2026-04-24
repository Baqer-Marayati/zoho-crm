#!/usr/bin/env python3
"""
Consolidate Canon EN spec rows into **five** Zoho Products (one per machine line).

Reads the flat `canon_products_wave_a_en.csv` (engines + options from RTF build) and
writes `canon_products_five_machines_en.csv` with:
  Product_Name, Product_Code, Unit_Price, Qty_in_Stock, Description

**Description** is a short, CRM-friendly summary (same for every quote using that product).
Speed tier, finisher, and POD choices belong on the **quote line**, not in this field.
Use `--long-spec` only if you need the old single-field dump of all RTF-derived text.

Usage:
  cd tools/zoho
  ./venv/bin/python build_canon_five_machines_csv.py
  ./venv/bin/python build_canon_five_machines_csv.py --long-spec
  ./venv/bin/python build_canon_five_machines_csv.py \\
    --in ../../artifacts/zoho/import/canon_products_wave_a_en.csv \\
    --out ../../artifacts/zoho/import/canon_products_five_machines_en.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

REPO_IMPORT = Path(__file__).resolve().parent.parent.parent / "artifacts" / "zoho" / "import"

# Stable Zoho Product_Code (SKU root) per line
MACHINES: list[dict[str, Any]] = [
    {
        "key": "vp6k_titan",
        "product_name": "Canon varioPRINT 6000 TITAN",
        "product_code": "CANON-VP6K-TITAN",
        "blurb": "Cut-sheet color production; speed tier chosen on quote (6180 / 6220 / 6270 / 6330 ppm).",
    },
    {
        "key": "ip_v1000",
        "product_name": "Canon imagePRESS V1000",
        "product_code": "CANON-IP-V1000",
        "blurb": "Color digital press; configure finishers and paper handling on quote.",
    },
    {
        "key": "ip_v1350",
        "product_name": "Canon imagePRESS V1350",
        "product_code": "CANON-IP-V1350",
        "blurb": "High-volume color digital press; configure finishers and POD deck on quote.",
    },
    {
        "key": "ip_v900_series",
        "product_name": "Canon imagePRESS V900 series",
        "product_code": "CANON-IP-V9K-SER",
        "blurb": "Color digital press family: V700 / V800 / V900 speed tiers; shared options where compatible.",
    },
    {
        "key": "vp140_series",
        "product_name": "Canon varioPRINT 140 series",
        "product_code": "CANON-VP140-SER",
        "blurb": "Cut-sheet production line: varioPRINT 115 / 130 / 140 speed tiers; options on quote.",
    },
]

# Customer-facing catalog copy (Zoho Product Description). Keep concise; deep spec lives in
# attachments and in "Compatible finishers" / "Compatible POD / paper" on the product.
CURATED_DESCRIPTIONS: dict[str, str] = {
    "vp6k_titan": (
        "High-volume cut-sheet color production (varioPRINT 6000 TITAN). "
        "Engine speeds 6180 / 6220 / 6270 / 6330 ppm (BW/CL) are selected on the quote. "
        "LED imaging up to 600 x 1200 dpi; typical media ~50–300 gsm. "
        "Paper feed, stacking, and PIM options are chosen on the quote line. "
        "Full specifications: product attachments and technical datasheet."
    ),
    "ip_v1000": (
        "Canon imagePRESS V1000 color digital press at 100 ppm (BW/CL). "
        "Typical duty ~75k–600k pages/month (peak to ~600k). "
        "2400 x 2400 dpi class imaging; media ~52–400 gsm. "
        "Finisher and POD / paper handling are selected on the quote line. "
        "Details: compatible options on this product record + attachments."
    ),
    "ip_v1350": (
        "Canon imagePRESS V1350 high-volume color digital press at 135 ppm (BW/CL). "
        "Designed for heavy monthly volumes (recommended up to ~1.2M pages, peak ~2.4M). "
        "2400 x 2400 dpi; media ~60–500 gsm. "
        "Finisher and POD deck are selected on the quote line. "
        "Full specs: attachments."
    ),
    "ip_v900_series": (
        "Canon imagePRESS V900 family: choose V700 (70 ppm), V800 (80 ppm), or V900 (90 ppm) on the quote. "
        "2400 x 2400 dpi; typical media ~52–350 gsm. "
        "Finisher and POD options on the quote line (Booklet Finisher-AC2 applies to V700/V800 only). "
        "Full specs: attachments."
    ),
    "vp140_series": (
        "Canon varioPRINT 140 cut-sheet line: choose 115 (117 ppm), 130 (133 ppm), or 140 (143 ppm) on the quote. "
        "600 x 2400 dpi; typical media ~50–300 gsm. "
        "Optional booklet finisher and external paper module on the quote line. "
        "Full specs: attachments."
    ),
}


def _norm(s: str) -> str:
    return (s or "").strip().casefold()


def _bucket(product_name: str) -> str | None:
    """Map flat catalog name to machine key."""
    n = _norm(product_name)

    # varioPRINT 140 family first (avoid clash with other varioPRINT lines)
    if re.search(r"varioprint (115|130|140)\b", n) or "(varioprint 140)" in n:
        return "vp140_series"

    if (
        re.search(r"imagepress v(700|800|900)\b", n)
        or "(imagepress v900)" in n
    ):
        return "ip_v900_series"

    if "imagepress v1350" in n:
        return "ip_v1350"

    if "imagepress v1000" in n:
        return "ip_v1000"

    if (
        re.search(r"varioprint (6180|6220|6270|6330)\s+titan", n)
        or "6000 titan" in n
    ):
        return "vp6k_titan"

    return None


def _section(title: str, body: str) -> str:
    body = " ".join((body or "").split())
    return f"=== {title} === {body}"


def _build_description_long(
    machine: dict[str, Any],
    engines: list[str],
    options: list[str],
) -> str:
    """Legacy: one field with all RTF-derived text (not recommended for CRM/PDF)."""
    parts: list[str] = [
        _section("Overview", machine["blurb"]),
        _section(
            "Speed / engine tiers (select on quote)",
            " ".join(engines) if engines else "See technical blocks below.",
        ),
        _section(
            "Compatible options & technical detail (from spec source)",
            " ".join(options) if options else "None merged from source file.",
        ),
        _section(
            "License & software",
            "Document speed/license entitlements on the quote line. "
            "Commercial SKUs for CLM or click contracts are not in this CSV.",
        ),
        _section(
            "Pictures & PDFs in Zoho",
            f"After import: attach hero image, datasheet, brochure to this product. "
            f"Suggested file prefix: {machine['product_code']}_",
        ),
    ]
    return " ".join(parts)


def _build_description(machine: dict[str, Any], engines: list[str], options: list[str], long_spec: bool) -> str:
    if long_spec:
        return _build_description_long(machine, engines, options)
    key = machine["key"]
    if key not in CURATED_DESCRIPTIONS:
        raise RuntimeError(f"Missing CURATED_DESCRIPTIONS for {key}")
    return CURATED_DESCRIPTIONS[key]


def main() -> int:
    ap = argparse.ArgumentParser(description="Build five-machine Canon product CSV for Zoho")
    ap.add_argument("--in", dest="in_path", type=Path, default=REPO_IMPORT / "canon_products_wave_a_en.csv")
    ap.add_argument("--out", dest="out_path", type=Path, default=REPO_IMPORT / "canon_products_five_machines_en.csv")
    ap.add_argument(
        "--manifest",
        type=Path,
        default=REPO_IMPORT / "canon_product_line" / "five_machines_manifest.json",
        help="Write JSON manifest for collateral naming and quote guidance",
    )
    ap.add_argument(
        "--long-spec",
        action="store_true",
        help="Use full merged RTF text as Description (old behavior)",
    )
    args = ap.parse_args()

    if not args.in_path.is_file():
        print(f"Input CSV not found: {args.in_path}", flush=True)
        return 1

    rows_in: list[dict[str, str]] = []
    with args.in_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows_in.append(row)

    buckets: dict[str, dict[str, list[str]]] = {m["key"]: {"engines": [], "options": []} for m in MACHINES}

    for row in rows_in:
        name = (row.get("Product_Name") or "").strip()
        desc = (row.get("Description") or "").strip()
        key = _bucket(name)
        if not key:
            print(f"  (skip unbucketed) {name}", flush=True)
            continue
        block = f"{name}: {desc}".strip()

        is_engine = bool(
            re.match(
                r"^Canon varioPRINT (6180|6220|6270|6330) TITAN$",
                name,
                re.I,
            )
            or re.match(r"^Canon imagePRESS V1000$", name, re.I)
            or re.match(r"^Canon imagePRESS V1350$", name, re.I)
            or re.match(r"^Canon imagePRESS V(700|800|900)$", name, re.I)
            or re.match(r"^Canon varioPRINT (115|130|140)$", name, re.I)
        )

        if is_engine:
            buckets[key]["engines"].append(block)
        else:
            buckets[key]["options"].append(block)

    out_rows: list[dict[str, str]] = []
    try:
        rel_csv = str(args.out_path.relative_to(REPO_IMPORT.parent.parent.parent))
    except ValueError:
        rel_csv = str(args.out_path)
    manifest: dict[str, Any] = {
        "zoho_import_csv": rel_csv,
        "products": [],
    }

    for machine in MACHINES:
        key = machine["key"]
        eng = buckets[key]["engines"]
        opt = buckets[key]["options"]
        desc = _build_description(machine, eng, opt, args.long_spec)
        out_rows.append(
            {
                "Product_Name": machine["product_name"],
                "Product_Code": machine["product_code"],
                "Unit_Price": "0",
                "Qty_in_Stock": "0",
                "Description": desc,
            }
        )
        manifest["products"].append(
            {
                "key": key,
                "product_name": machine["product_name"],
                "product_code": machine["product_code"],
                "speed_tiers_note": "Set quote line picklists or text for chosen tier.",
                "collateral_suggested_filenames": [
                    f"{machine['product_code']}_hero.jpg",
                    f"{machine['product_code']}_datasheet_en.pdf",
                    f"{machine['product_code']}_brochure_en.pdf",
                ],
                "source_engine_rows": len(eng),
                "source_option_rows": len(opt),
            }
        )

    args.out_path.parent.mkdir(parents=True, exist_ok=True)
    with args.out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["Product_Name", "Product_Code", "Unit_Price", "Qty_in_Stock", "Description"],
        )
        w.writeheader()
        w.writerows(out_rows)

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    with args.manifest.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    print(f"Wrote {len(out_rows)} products → {args.out_path}", flush=True)
    print(f"Manifest → {args.manifest}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
