#!/usr/bin/env python3
"""
Quote line (Quoted_Items) — Machine SKU, Model / speed, Configuration 1 & 2 with map dependency.

Zoho *map_dependency* needs a *parent picklist*; the line Product lookup cannot be the parent in the
standard API. Reps set **Machine SKU** to the same **Product_Code** as the product on that line;
**Model / speed** and **Configuration 1/2** then show only options for that code.

Renames: Finisher (line) -> Configuration 1, POD / paper module (line) -> Configuration 2

OAuth: ZohoCRM.settings.fields.UPDATE, ZohoCRM.settings.layouts.READ,
       ZohoCRM.settings.map_dependency.CREATE (or ZohoCRM.settings.ALL).

Usage:
  cd tools/zoho
  ./venv/bin/python provision_quoted_line_dependencies.py --dry-run
  ./venv/bin/python provision_quoted_line_dependencies.py
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

import requests

from zoho_tokens import auth_headers, get_access_token_and_domain

API_VER = "v8"
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
EXT_JSON = REPO_ROOT / "artifacts" / "zoho" / "product_extensions" / "extensions_by_product_code.json"

LINE_MODULE_CANDIDATES = ("Quoted_Items", "QuotedItems", "Quote_Line_Items", "Quotes_Line_Items")

OLD_FINISHERS = "Finisher (line)"
OLD_POD = "POD / paper module (line)"
LABEL_C1 = "Configuration 1"
LABEL_C2 = "Configuration 2"
LABEL_SKU = "Machine SKU"
LABEL_MS = "Model / speed"
# Zoho line-item picklist: avoid em dash and some punctuation (API returns INVALID_DATA).
NONE_OPT = "- None -"
_DEFAULT_MODEL = ["- Not applicable -"]


def _zoho_pick(s: str) -> str:
    """Zoho line picklists reject some punctuation; keep readable ASCII for option labels."""
    t = unicodedata.normalize("NFKD", s or "")
    t = t.encode("ascii", "ignore").decode("ascii")
    t = t.replace("—", "-").replace("–", "-")
    t = t.replace("&", " and ")
    t = re.sub(r"[^a-zA-Z0-9 \-().,/%+]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:255] if t else t

MODEL_SPEED: dict[str, list[str]] = {
    "CANON-IRDX-C3900-SER": [
        "C3922i (22 ppm A4)",
        "C3926i (26 ppm A4)",
        "C3930i (30 ppm A4)",
        "C3935i (35 ppm A4)",
    ],
    "CANON-IRDX-C478-SER": [
        "C478i (no internal finisher)",
        "C478iZ (internal staple/offset finisher)",
    ],
    "CANON-IRDX-C259359-SER": [
        "C259i (25 ppm A4)",
        "C359i (35 ppm A4, MFP)",
        "C359P (print only) — if offered",
    ],
    "CANON-IF-C5100-SER": [
        "C5140 (40 ppm A4)",
        "C5150 (50 ppm A4)",
        "C5160 (60 ppm A4)",
        "C5170 (70 ppm A4)",
    ],
    "CANON-IP-V9K-SER": [
        "V700 (70 ppm) — confirm on quote",
        "V800 (80 ppm) — confirm on quote",
        "V900 (90 ppm) — confirm on quote",
    ],
    "CANON-IRDX-4900-SER": [
        "6860i (86 ppm) — confirm on quote",
        "6870i (87 ppm) — confirm on quote",
    ],
    "CANON-IRDX-4800-SER": [
        "4825i (25 ppm) — confirm on quote",
        "4835i (35 ppm) — confirm on quote",
        "4845i (45 ppm) — confirm on quote",
    ],
    "CANON-IR-2700-SER": [
        "2725i",
        "2730i",
        "2745i",
    ],
    "CANON-IR-2900-SER": [
        "2925i",
        "2930i",
        "2945i",
    ],
    "CANON-IF-6100-SER": [
        "IF6140 (40 ppm) — confirm on quote",
        "IF6150 (50 ppm) — confirm on quote",
        "IF6160 (60 ppm) — confirm on quote",
    ],
    "CANON-IF-8100-SER": [
        "IF8185 / IF8195 / IF8197 — confirm speed on quote",
    ],
    "CANON-IRAC55-ES2-SER": [
        "C5540i ES+ II (40 ppm) — confirm on quote",
        "C5560i ES+ II (60 ppm) — confirm on quote",
    ],
    "CANON-IR-2425-SER": [
        "2425 / 2425i / 2425N — confirm on quote",
    ],
}


def _crm(session: requests.Session, api_domain: str, method: str, path: str, **kwargs):
    url = f"{api_domain.rstrip('/')}/crm/{API_VER}{path}"
    return session.request(method, url, timeout=120, **kwargs)


def _slug(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s.strip()).strip("_")
    return s[:100] if s else "value"


def _discover_line_module(session: requests.Session, api_domain: str) -> str | None:
    r = _crm(session, api_domain, "GET", "/settings/modules")
    if not r.ok:
        return None
    apis = {m.get("api_name") for m in r.json().get("modules", []) if m.get("api_name")}
    for cand in LINE_MODULE_CANDIDATES:
        if cand in apis:
            print(f"  Line module: {cand}")
            return cand
    for m in r.json().get("modules", []) or []:
        an = m.get("api_name") or ""
        if "quoted" in an.lower() and "item" in an.lower():
            print(f"  Line module (fuzzy): {an}")
            return str(an)
    return None


def _fields_map(session: requests.Session, api_domain: str, module: str) -> dict[str, dict]:
    r = _crm(
        session,
        api_domain,
        "GET",
        "/settings/fields",
        params={"module": module, "type": "all"},
    )
    if not r.ok:
        raise RuntimeError(f"GET fields {module} HTTP {r.status_code}: {r.text[:2000]}")
    return {
        (f.get("field_label") or "").strip().lower(): f
        for f in r.json().get("fields", [])
        if f.get("field_label")
    }


def _default_layout_id(session: requests.Session, api_domain: str, module: str) -> str | None:
    r = _crm(session, api_domain, "GET", "/settings/layouts", params={"module": module})
    if not r.ok:
        return None
    layouts = r.json().get("layouts") or []
    for lo in layouts:
        if (lo.get("name") or "").lower() in ("standard", "default") or lo.get("default"):
            return str(lo.get("id"))
    return str(layouts[0]["id"]) if layouts else None


def _patch_field_label(
    session: requests.Session, api_domain: str, module: str, field_id: str, new_label: str, dry: bool
) -> bool:
    if dry:
        print(f"  (dry-run) rename field {field_id} -> {new_label}")
        return True
    r = _crm(
        session,
        api_domain,
        "PATCH",
        f"/settings/fields/{field_id}",
        params={"module": module},
        json={"fields": [{"id": field_id, "field_label": new_label}]},
    )
    if not r.ok:
        print(f"  PATCH label HTTP {r.status_code}: {r.text[:1500]}", file=sys.stderr)
        return False
    return True


def _post_picklist(
    session: requests.Session, api_domain: str, module: str, label: str, values: list[str], dry: bool
) -> bool:
    fm = _fields_map(session, api_domain, module)
    if label.lower() in fm:
        print(f"  '{label}' already exists")
        return True
    pvs = [{"display_value": v, "actual_value": _slug(v)} for v in values]
    if dry:
        print(f"  (dry-run) POST '{label}' picklist, {len(values)} values")
        return True
    r = _crm(
        session,
        api_domain,
        "POST",
        "/settings/fields",
        params={"module": module},
        json={
            "fields": [
                {
                    "field_label": label,
                    "data_type": "picklist",
                    "pick_list_values": pvs,
                    "pick_list_values_sorted_lexically": True,
                    "enable_colour_code": False,
                }
            ]
        },
    )
    if not r.ok:
        print(f"  POST {label} HTTP {r.status_code}: {r.text[:3000]}", file=sys.stderr)
        return False
    print(f"  Created picklist: {label}")
    return True


def _load_per_product(ext: dict[str, Any]) -> tuple[dict[str, dict], list[str], list[str], list[str]]:
    per: dict[str, dict] = {}
    all_m: set[str] = {NONE_OPT}
    all1: set[str] = {NONE_OPT}
    all2: set[str] = {NONE_OPT}

    for code, row in ext.items():
        if not str(code).startswith("CANON-"):
            continue
        name = (row.get("product_name") or code).strip()
        sku_disp = _zoho_pick(f"{code} - {name}")[:255]
        fns = [_zoho_pick(x.strip()) for x in (row.get("finishers") or []) if str(x).strip()]
        pds = [_zoho_pick(x.strip()) for x in (row.get("pod_paper") or []) if str(x).strip()]
        c1 = fns if fns else [NONE_OPT]
        c2 = pds if pds else [NONE_OPT]
        if NONE_OPT not in c1:
            c1 = c1 + [NONE_OPT]
        if NONE_OPT not in c2:
            c2 = c2 + [NONE_OPT]
        msv = MODEL_SPEED.get(str(code))
        if msv is None or len(msv) == 0:
            ms = _DEFAULT_MODEL[:]
        else:
            ms = [_zoho_pick(x) for x in msv]
        for x in ms:
            all_m.add(x)
        for x in c1:
            all1.add(x)
        for x in c2:
            all2.add(x)
        per[str(code)] = {
            "sku_disp": sku_disp,
            "model": ms,
            "c1": c1,
            "c2": c2,
        }

    def _dedupe_ordered(seq: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for v in sorted(seq, key=str.casefold):
            if v in seen:
                continue
            seen.add(v)
            out.append(v)
        return out

    return (
        per,
        _dedupe_ordered(list(all_m)),
        _dedupe_ordered(list(all1)),
        _dedupe_ordered(list(all2)),
    )


def _refresh_fields(session: requests.Session, api_domain: str, module: str) -> dict[str, dict]:
    r = _crm(
        session,
        api_domain,
        "GET",
        "/settings/fields",
        params={"module": module, "type": "all"},
    )
    if not r.ok:
        return {}
    return { (f.get("field_label") or "").strip().lower(): f for f in (r.json().get("fields") or []) if f.get("field_label") }


def _merge_picklist_options(
    session: requests.Session, api_domain: str, module: str, field_id: str, desired: list[str], dry: bool
) -> bool:
    """Add any missing display values (Zoho treats full pick_list replace as error if dup with existing)."""
    if dry:
        return True
    r0 = _crm(
        session, api_domain, "GET", f"/settings/fields/{field_id}", params={"module": module}
    )
    if not r0.ok:
        print(f"  GET field {field_id} HTTP {r0.status_code}", file=sys.stderr)
        return False
    body = r0.json() or {}
    fobj = (body.get("fields") or [body])[0]
    ex = {p.get("display_value", "").strip() for p in (fobj.get("pick_list_values") or []) if p}
    to_add = [v for v in desired if v.strip() and v not in ex]
    if not to_add:
        print(f"  Picklist {field_id}: no new values to add ({len(ex)} already present)")
        return True
    pvs = [{"display_value": v, "actual_value": _slug(v)} for v in to_add]
    r = _crm(
        session,
        api_domain,
        "PATCH",
        f"/settings/fields/{field_id}",
        params={"module": module},
        json={"fields": [{"id": field_id, "pick_list_values": pvs}]},
    )
    if not r.ok:
        print(f"  MERGE picklist {field_id} HTTP {r.status_code}: {r.text[:2000]}", file=sys.stderr)
        return False
    print(f"  Added {len(to_add)} picklist option(s) to field {field_id}")
    return True


def _resolve_pick_display(c_by: dict[str, Any], wanted: str) -> dict | None:
    if wanted in c_by:
        return c_by[wanted]
    wlow = wanted.casefold()
    for k, pvo in c_by.items():
        if k.casefold() == wlow:
            return pvo
    if "none" in wlow or wanted == NONE_OPT:
        for k, pvo in c_by.items():
            if "none" in k.casefold():
                return pvo
    return None


def _map_rows(
    child_f: dict,
    allowed: set[str],
) -> list[dict]:
    c_by = {p["display_value"]: p for p in (child_f.get("pick_list_values") or [])}
    out: list[dict] = []
    for dv in sorted(allowed, key=str.casefold):
        pvo = _resolve_pick_display(c_by, dv)
        if not pvo:
            continue
        disp = pvo.get("display_value") or dv
        out.append(
            {
                "id": str(pvo["id"]),
                "display_value": disp,
                "actual_value": (pvo.get("actual_value") or pvo.get("value") or _slug(disp))[:255],
            }
        )
    return out


def _product_code_for_machine_sku_display(
    disp: str, code_by_disp: dict[str, str], per: dict[str, dict]
) -> str | None:
    """
    Map a Machine SKU picklist *display* to a Product_Code key in `per`.
    Zoho or users may use em dash (—) vs ASCII hyphen; labels must still align with
    map_dependency, so we try exact, _zoho_pick-normalized, and product-code prefix.
    """
    d = (disp or "").strip()
    if not d or d == NONE_OPT:
        return None
    for candidate in (d, _zoho_pick(d), _zoho_pick(d.replace("—", "-").replace("–", "-"))):
        if not candidate:
            continue
        hit = code_by_disp.get(candidate)
        if hit:
            return str(hit)
    for code in sorted(per.keys(), key=lambda x: len(str(x)), reverse=True):
        c = str(code)
        if d.startswith(c + " ") or d == c:
            return c
        z = _zoho_pick(d)
        if z.startswith(c + " ") or z == c:
            return c
    return None


def _sync_map(
    session: requests.Session, api_domain: str, module: str, layout_id: str, body: dict, dry: bool
) -> bool:
    papi = body["map_dependency"][0]["parent"]["api_name"]
    capi = body["map_dependency"][0]["child"]["api_name"]
    if dry:
        print(f"  (dry-run) map_dependency {papi} -> {capi}")
        return True
    r0 = _crm(
        session,
        api_domain,
        "GET",
        f"/settings/layouts/{layout_id}/map_dependency",
        params={"module": module},
    )
    if r0.status_code == 204 or not (r0.text or "").strip():
        body0: dict = {}
    elif not r0.ok:
        print(f"GET map_dependency {r0.status_code}: {r0.text[:2000]}", file=sys.stderr)
        return False
    else:
        try:
            body0 = r0.json()
        except Exception:
            print(f"GET map_dependency non-JSON: {r0.text[:500]}", file=sys.stderr)
            return False
    dep_id: str | None = None
    for md in body0.get("map_dependency") or []:
        if (md.get("parent") or {}).get("api_name") == papi and (md.get("child") or {}).get("api_name") == capi:
            dep_id = str(md.get("id") or "")
            break
    if dep_id:
        r1 = _crm(
            session,
            api_domain,
            "PUT",
            f"/settings/layouts/{layout_id}/map_dependency/{dep_id}",
            params={"module": module},
            json=body,
        )
    else:
        r1 = _crm(
            session,
            api_domain,
            "POST",
            f"/settings/layouts/{layout_id}/map_dependency",
            params={"module": module},
            json=body,
        )
    if not r1.ok:
        print(f"map_dep HTTP {r1.status_code}: {r1.text[:2500]}", file=sys.stderr)
        return False
    print(f"  Mapped {papi} -> {capi} ({'PUT' if dep_id else 'POST'})")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    ext = json.loads(EXT_JSON.read_text(encoding="utf-8"))
    per, all_m, all_c1, all_c2 = _load_per_product(ext)
    if not per:
        print("No CANON- entries in extensions", file=sys.stderr)
        return 1

    try:
        access, dom = get_access_token_and_domain()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1
    s = requests.Session()
    s.headers.update(auth_headers(access))
    s.headers["Content-Type"] = "application/json"

    mod = _discover_line_module(s, dom)
    if not mod:
        return 1
    layout_id = _default_layout_id(s, dom, mod)
    if not layout_id:
        print("No layout for Quoted_Items; cannot add map dependency.", file=sys.stderr)
        return 1
    print(f"  module={mod} layout_id={layout_id}")

    fm = _fields_map(s, dom, mod)
    f1 = fm.get(OLD_FINISHERS.lower()) or fm.get(LABEL_C1.lower())
    f2 = fm.get(OLD_POD.lower()) or fm.get(LABEL_C2.lower())
    if f1 and (f1.get("field_label") or "") != LABEL_C1:
        _patch_field_label(s, dom, mod, str(f1["id"]), LABEL_C1, args.dry_run)
    if f2 and (f2.get("field_label") or "") != LABEL_C2:
        _patch_field_label(s, dom, mod, str(f2["id"]), LABEL_C2, args.dry_run)

    sku_vals = [NONE_OPT] + [per[k]["sku_disp"] for k in sorted(per.keys(), key=str.casefold)]
    if not _post_picklist(s, dom, mod, LABEL_SKU, sku_vals, args.dry_run):
        return 1
    if not _post_picklist(s, dom, mod, LABEL_MS, all_m, args.dry_run):
        return 1

    if args.dry_run:
        print(
            f"  (dry-run) Would MERGE picklists: Machine SKU ({len(sku_vals)}), "
            f"Model/speed ({len(all_m)}), Configuration 1/2 ({len(all_c1)} / {len(all_c2)} values), "
            "then POST map_dependency x3 (Machine SKU -> Model/speed, Config 1, Config 2)."
        )
        print("\nDry-run OK.")
        return 0

    fm2 = _refresh_fields(s, dom, mod)
    c1f = fm2.get(LABEL_C1.lower())
    c2f = fm2.get(LABEL_C2.lower())
    fsku = fm2.get(LABEL_SKU.lower())
    fms = fm2.get(LABEL_MS.lower())
    if not c1f or not c2f or not fsku or not fms:
        print("Could not find required line fields after create.", file=sys.stderr)
        return 1

    # Keep Machine SKU + Model/speed in sync with extensions (not only on first create).
    if not _merge_picklist_options(s, dom, mod, str(fsku["id"]), sku_vals, args.dry_run):
        return 1
    if not _merge_picklist_options(s, dom, mod, str(fms["id"]), all_m, args.dry_run):
        return 1
    if not _merge_picklist_options(s, dom, mod, str(c1f["id"]), all_c1, args.dry_run):
        return 1
    if not _merge_picklist_options(s, dom, mod, str(c2f["id"]), all_c2, args.dry_run):
        return 1

    fm3 = _refresh_fields(s, dom, mod)
    c1f = fm3[LABEL_C1.lower()]
    c2f = fm3[LABEL_C2.lower()]
    fsku = fm3[LABEL_SKU.lower()]
    fms = fm3[LABEL_MS.lower()]

    p_sku = {p["display_value"]: p for p in (fsku.get("pick_list_values") or [])}

    def one_map(which: str) -> bool:
        child = fms if which == "ms" else (c1f if which == "c1" else c2f)
        key = "model" if which == "ms" else which
        nb = {p["display_value"]: p for p in (child.get("pick_list_values") or [])}
        nchild = _resolve_pick_display(nb, NONE_OPT)
        nrow = (
            {
                "id": str(nchild["id"]),
                "display_value": nchild.get("display_value") or NONE_OPT,
                "actual_value": nchild.get("actual_value")
                or nchild.get("value")
                or "None",
            }
            if nchild
            else None
        )
        code_by_disp = {row["sku_disp"]: c for c, row in per.items()}

        pli: list[dict] = []
        for pvo in fsku.get("pick_list_values") or []:
            disp = (pvo.get("display_value") or "").strip()
            if not disp:
                continue
            actual = (pvo.get("actual_value") or "").strip()
            if disp == "-None-" and actual == "-None-":
                continue
            is_none_parent = (
                disp == NONE_OPT
                or pvo.get("actual_value", "").casefold() in ("none", "-none-", "none-")
            )
            if is_none_parent and nrow is not None:
                maps: list[dict] = [nrow]
            else:
                code = _product_code_for_machine_sku_display(
                    disp, code_by_disp, per
                )
                allowed: set[str] = (
                    {NONE_OPT} if not code else set(per[code].get(key) or [NONE_OPT])
                )
                maps = _map_rows(child, allowed)
                if not maps and nrow is not None:
                    maps = [nrow]
            pli.append(
                {
                    "id": str(pvo.get("id")),
                    "display_value": disp,
                    "actual_value": pvo.get("actual_value")
                    or pvo.get("value")
                    or _slug(disp),
                    "maps": maps,
                }
            )
        b = {
            "map_dependency": [
                {
                    "parent": {"api_name": fsku["api_name"], "id": str(fsku["id"])},
                    "child": {"api_name": child["api_name"], "id": str(child["id"])},
                    "pick_list_values": pli,
                }
            ]
        }
        return _sync_map(s, dom, mod, layout_id, b, args.dry_run)

    if not (one_map("ms") and one_map("c1") and one_map("c2")):
        return 1

    print(
        "\nNext: Run `provision_quoted_line_product_first_layout.py` to rename **Machine SKU** to "
        "**Product (Machine)**, move **Product Name** off the used layout, and sync picklist options "
        "on the layout. Reps pick Product (Machine) first; Deluge + optional Client Script set the "
        "Product lookup. Order on the line: **Product (Machine)**, **Model / speed**, "
        "**Configuration 1**, **Configuration 2**."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
