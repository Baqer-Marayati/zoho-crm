#!/usr/bin/env python3
"""
Product-first Quoted_Items line layout (recommended UX):

1) Rename picklist field **Machine_SKU** to **Product (Machine)** (api_name stays Machine_SKU).
2) Remove **Product Name** (lookup) from the used layout when Zoho allows it; if the field is
   **system mandatory**, it cannot be removed — then set **Product Name** to **read-only** on
   the layout (reps use **Product (Machine)**; Deluge / Client Script still set the lookup).
   api_name `Product_Name` is unchanged.
3) Re-sync picklist **options onto the layout** for Machine_SKU, Model / speed, Configuration
   1/2 — required for map_dependency (Zoho needs layout-bound option ids).

Run after: provision_quoted_line_dependencies.py
Before: re-paste the Deluge body from
  ../../artifacts/zoho/deluge/quoted_items_sync_machine_sku.deluge
  into the Zoho function **quoted_items_sync_machine_sku** (same name; new logic).
Optional: add a Client Script from ../../artifacts/zoho/client_scripts/ for instant Product
lookup in the form before save.

  cd tools/zoho
  ./venv/bin/python provision_quoted_line_product_first_layout.py
  ./venv/bin/python provision_quoted_line_product_first_layout.py --dry-run

OAuth: ZohoCRM.settings.layouts.UPDATE, ZohoCRM.settings.fields.UPDATE
"""
from __future__ import annotations

import argparse
import sys

import requests

from zoho_tokens import auth_headers, get_access_token_and_domain

API_VER = "v8"
API_SKU = "Machine_SKU"
API_PRODUCT = "Product_Name"
LABEL_PICK = "Product (Machine)"
CHILD_API = (
    "Model_speed",
    "Finisher_line",
    "POD_paper_module_line",
)


def _session():
    try:
        access, dom = get_access_token_and_domain()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return None, None, None
    s = requests.Session()
    s.headers.update({**auth_headers(access), "Content-Type": "application/json"})
    return s, access, dom


def _get_layout(s: requests.Session, dom: str, module: str, lid: str) -> dict | None:
    r = s.get(
        f"{dom.rstrip('/')}/crm/{API_VER}/settings/layouts/{lid}",
        params={"module": module},
        timeout=60,
    )
    if not r.ok:
        print(f"GET layout HTTP {r.status_code}: {r.text[:1500]}", file=sys.stderr)
        return None
    return (r.json().get("layouts") or [None])[0]


def _field_by_api(s: requests.Session, dom: str, module: str, api: str) -> dict | None:
    r = s.get(
        f"{dom.rstrip('/')}/crm/{API_VER}/settings/fields",
        params={"module": module, "type": "all"},
        timeout=60,
    )
    if not r.ok:
        print(f"GET fields HTTP {r.status_code}", file=sys.stderr)
        return None
    for f in r.json().get("fields") or []:
        if f.get("api_name") == api:
            return f
    return None


def _patch_field_label(
    s: requests.Session, dom: str, module: str, fid: str, label: str, dry: bool
) -> bool:
    if dry:
        print(f"  (dry-run) PATCH field {fid} -> field_label {label!r}")
        return True
    r = s.patch(
        f"{dom.rstrip('/')}/crm/{API_VER}/settings/fields/{fid}",
        params={"module": module},
        json={"fields": [{"id": str(fid), "field_label": label}]},
        timeout=60,
    )
    if not r.ok:
        print(f"PATCH field label HTTP {r.status_code}: {r.text[:2000]}", file=sys.stderr)
        return False
    print(f"  OK: field {fid} label -> {label!r}")
    return True


def _remove_from_used(
    s: requests.Session,
    dom: str,
    module: str,
    lid: str,
    layout: dict,
    api: str,
    dry: bool,
) -> bool:
    msku_fid: str | None = None
    section_id: str | None = None
    for sec in layout.get("sections") or []:
        for f in sec.get("fields") or []:
            if (f.get("api_name") or "") == api and (sec.get("type") or "") == "used":
                msku_fid = str(f.get("id", ""))
                section_id = str(sec.get("id", ""))
                break
        if msku_fid:
            break
    if not msku_fid or not section_id:
        print(f"  {api} is not on a used section; nothing to remove.")
        return True
    if dry:
        print(f"  (dry-run) move {api} to Unused (field id={msku_fid})")
        return True
    body = {
        "layouts": [
            {
                "sections": [
                    {
                        "id": section_id,
                        "fields": [
                            {
                                "id": msku_fid,
                                "_delete": {"permanent": False},
                            }
                        ],
                    }
                ]
            }
        ]
    }
    r = s.patch(
        f"{dom.rstrip('/')}/crm/{API_VER}/settings/layouts/{lid}",
        params={"module": module},
        json=body,
        timeout=60,
    )
    if not r.ok:
        t = (r.text or "")
        if r.status_code == 400 and "System mandatory" in t:
            print(
                "  Product Name cannot be removed from the layout in this org (system mandatory).",
                "Setting it read-only on the used layout so reps use Product (Machine) only.",
            )
            return _set_read_only_on_used(s, dom, module, lid, msku_fid, section_id, dry)
        print(f"PATCH layout HTTP {r.status_code}: {r.text[:2000]}", file=sys.stderr)
        return False
    print(f"  OK: {api} (id={msku_fid}) moved to Unused on layout {lid}")
    return True


def _set_read_only_on_used(
    s: requests.Session,
    dom: str,
    module: str,
    lid: str,
    field_id: str,
    section_id: str,
    dry: bool,
) -> bool:
    if dry:
        print(f"  (dry-run) set field {field_id} read_only on used layout")
        return True
    body = {
        "layouts": [
            {
                "sections": [
                    {
                        "id": section_id,
                        "fields": [
                            {
                                "id": field_id,
                                "read_only": True,
                            }
                        ],
                    }
                ]
            }
        ]
    }
    r = s.patch(
        f"{dom.rstrip('/')}/crm/{API_VER}/settings/layouts/{lid}",
        params={"module": module},
        json=body,
        timeout=60,
    )
    if not r.ok:
        print(f"  PATCH read-only HTTP {r.status_code}: {r.text[:2000]}", file=sys.stderr)
        return False
    print("  OK: Product Name set to read-only on the line layout (reps: use Product (Machine))")
    return True


def _push_picklist_options_to_layout(
    s: requests.Session, dom: str, module: str, lid: str, layout: dict, dry: bool
) -> bool:
    """Map dependency validates against **layout**-bound picklist option ids; push from global field."""
    fmeta: dict[str, dict] = {}
    for a in (API_SKU, *CHILD_API):
        f = _field_by_api(s, dom, module, a)
        if not f:
            print(f"  Field not found: {a}", file=sys.stderr)
            return False
        fmeta[a] = f

    used_sec: dict | None = None
    for sec in layout.get("sections") or []:
        if (sec.get("type") or "") == "used" and (sec.get("fields") or []):
            used_sec = sec
            break
    if not used_sec or not used_sec.get("id"):
        print("  No used section with fields", file=sys.stderr)
        return False
    section_id = str(used_sec["id"])

    def pl_fields() -> list[dict]:
        out: list[dict] = []
        for a, fg in fmeta.items():
            pvs = [
                {
                    "id": str(p["id"]),
                    "display_value": p["display_value"],
                    "actual_value": p.get("actual_value"),
                }
                for p in (fg.get("pick_list_values") or [])
            ]
            if not pvs:
                print(f"  No pick_list_values on field {a}", file=sys.stderr)
                return []
            out.append(
                {
                    "id": str(fg["id"]),
                    "pick_list_values": pvs,
                }
            )
        return out

    if dry:
        print(f"  (dry-run) PATCH layout push picklist options for {', '.join(fmeta)}")
        return True
    r = s.patch(
        f"{dom.rstrip('/')}/crm/{API_VER}/settings/layouts/{lid}",
        params={"module": module},
        json={"layouts": [{"sections": [{"id": section_id, "fields": pl_fields()}]}]},
        timeout=120,
    )
    if not r.ok:
        print(f"  PATCH layout (picklist sync) HTTP {r.status_code}: {r.text[:2000]}", file=sys.stderr)
        return False
    print("  OK: picklist options pushed to layout (Machine_SKU + Model + Configs)")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    tok = _session()
    if not tok[0]:
        return 1
    s, _a, dom = tok

    r0 = s.get(
        f"{dom.rstrip('/')}/crm/{API_VER}/settings/layouts",
        params={"module": "Quoted_Items"},
        timeout=60,
    )
    if not r0.ok:
        print(f"GET layouts HTTP {r0.status_code}", file=sys.stderr)
        return 1
    layouts = r0.json().get("layouts") or []
    if not layouts:
        print("No Quoted_Items layouts", file=sys.stderr)
        return 1
    lid = str(layouts[0].get("id", ""))
    if not lid:
        return 1
    print(f"  Quoted_Items layout_id={lid}")

    sku = _field_by_api(s, dom, "Quoted_Items", API_SKU)
    if not sku:
        return 1
    if (sku.get("field_label") or "") != LABEL_PICK:
        if not _patch_field_label(
            s, dom, "Quoted_Items", str(sku["id"]), LABEL_PICK, args.dry_run
        ):
            return 1
    else:
        print(f"  Field {API_SKU} label already {LABEL_PICK!r}")

    layout = _get_layout(s, dom, "Quoted_Items", lid)
    if not layout:
        return 1
    if not _remove_from_used(s, dom, "Quoted_Items", lid, layout, API_PRODUCT, args.dry_run):
        return 1
    if not args.dry_run:
        layout = _get_layout(s, dom, "Quoted_Items", lid) or layout
    if not _push_picklist_options_to_layout(
        s, dom, "Quoted_Items", lid, layout, args.dry_run
    ):
        return 1

    print(
        "\nNext: (1) Paste updated Deluge from artifacts/zoho/deluge/quoted_items_sync_machine_sku.deluge\n"
        "into Zoho function quoted_items_sync_machine_sku. (2) Optional Client Script: see\n"
        "artifacts/zoho/client_scripts/."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
