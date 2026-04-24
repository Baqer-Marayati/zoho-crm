#!/usr/bin/env python3
"""
Build Wave A product CSV (English) from Canon * EN.rtf spec files.

Reads bold headings + following body lines; writes:
  Product_Name, Unit_Price, Qty_in_Stock, Description

No SKU / Product_Code — import dedupes by Product_Name in Zoho.
Unit_Price is 0 until pricing is added.

Usage:
  ./venv/bin/python build_canon_products_en_csv.py \
    --source "/path/to/Canon machine specs for SAP" \
    --out ../../artifacts/zoho/import/canon_products_wave_a_en.csv
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


def _rtf_char_escape(m: re.Match[str]) -> str:
    """RTF \\'hh is a single byte (hex); interpret as Windows-1252 (Zoho/Canon exports)."""
    b = bytes.fromhex(m.group(1))
    return b.decode("cp1252", errors="replace")


def _clean_rtf_line(line: str) -> str:
    line = re.sub(r"\\'([0-9a-fA-F]{2})", _rtf_char_escape, line)
    line = line.replace("\\'a0", " ")
    line = line.rstrip("\\").strip()
    line = re.sub(r"\s+", " ", line)
    return line.strip()


def _is_engine_title(title: str) -> bool:
    t = title.strip().lower()
    return bool(re.match(r"^(imagepress|varioprint)\s", t))


def parse_rtf_file(path: Path, family: str) -> list[tuple[str, str, str]]:
    """Return list of (raw_title, description_one_line, family)."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    out: list[tuple[str, str, str]] = []
    pos = 0
    while True:
        idx = raw.find(r"\f0\b", pos)
        if idx < 0:
            break
        idx += len(r"\f0\b")
        # Skip font size / color preamble up to kerning0
        m_pre = re.match(
            r"(?:\s*\\fs\d+\s*\\cf\d+\s*\\expnd0\\expndtw0\\kerning0\s*)?",
            raw[idx:],
        )
        if m_pre:
            idx += m_pre.end()
        m_title = re.match(r"\s*([^\n\\]+)\s*\n\\f1\\b0\s*\\\s*\n", raw[idx:])
        if not m_title:
            pos = idx
            continue
        title = m_title.group(1).strip()
        start_body = idx + m_title.end()
        next_blk = raw.find(r"\f0\b", start_body)
        body_raw = raw[start_body:] if next_blk < 0 else raw[start_body:next_blk]
        lines: list[str] = []
        for ln in body_raw.split("\n"):
            cl = _clean_rtf_line(ln)
            if not cl or cl == "}":
                continue
            if cl.startswith("{") and cl.endswith("}"):
                continue
            lines.append(cl)
        desc = " ".join(lines).strip()
        pos = start_body + 1
        if not title or len(title) < 2:
            continue
        if title in ("\xa0", " ") or re.match(r"^[\s'\\]+$", title):
            continue
        if not desc:
            continue
        out.append((title, desc, family))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Build Canon EN product CSV from RTF specs")
    ap.add_argument(
        "--source",
        type=Path,
        default=Path("/Users/baqer/Dropbox/Work/Canon/Canon machine specs for SAP"),
        help="Folder containing product subfolders with * EN.rtf",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent.parent.parent
        / "artifacts"
        / "zoho"
        / "import"
        / "canon_products_wave_a_en.csv",
        help="Output CSV path",
    )
    args = ap.parse_args()

    if not args.source.is_dir():
        print(f"Source not a directory: {args.source}", flush=True)
        return 1

    en_files = sorted(args.source.glob("**/* EN.rtf"))
    if not en_files:
        print(f"No '* EN.rtf' files under {args.source}", flush=True)
        return 1

    rows: list[dict[str, str]] = []
    for rtf_path in en_files:
        family = rtf_path.parent.name
        for title, desc, fam in parse_rtf_file(rtf_path, family):
            if _is_engine_title(title):
                display = f"Canon {title.strip()}"
            else:
                display = f"Canon {title.strip()} ({fam})"
            rows.append(
                {
                    "Product_Name": display,
                    "Unit_Price": "0",
                    "Qty_in_Stock": "0",
                    "Description": f"[Series: {fam}] {desc}",
                }
            )

    # Dedupe by name (first row wins)
    by_name: dict[str, dict[str, str]] = {}
    for r in rows:
        key = r["Product_Name"].strip().casefold()
        if key not in by_name:
            by_name[key] = r
    rows = list(by_name.values())

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "Product_Name",
                "Unit_Price",
                "Qty_in_Stock",
                "Description",
            ],
        )
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote {len(rows)} rows → {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
