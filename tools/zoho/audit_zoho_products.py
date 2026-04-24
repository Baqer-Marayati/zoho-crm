#!/usr/bin/env python3
"""Read-only: list Zoho Products with attachment count and Product Image flag."""
from __future__ import annotations

import json
import sys

import requests

from zoho_tokens import auth_headers, get_access_token_and_domain

API_VER = "v8"


def main() -> int:
    try:
        access, api_domain = get_access_token_and_domain()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1

    base = f"{api_domain.rstrip('/')}/crm/{API_VER}"
    s = requests.Session()
    s.headers.update(auth_headers(access))

    page = 1
    products: list[dict] = []
    while True:
        r = s.get(
            f"{base}/Products",
            params={
                "fields": "id,Product_Name,Product_Code,Description,Record_Image",
                "per_page": 200,
                "page": page,
            },
            timeout=120,
        )
        if r.status_code == 204:
            break
        r.raise_for_status()
        body = r.json()
        products.extend(body.get("data") or [])
        if not (body.get("info") or {}).get("more_records"):
            break
        page += 1

    rows = []
    for p in sorted(products, key=lambda x: (x.get("Product_Code") or "")):
        pid = str(p.get("id"))
        r2 = s.get(
            f"{base}/Products/{pid}/Attachments",
            params={"fields": "id,File_Name", "per_page": 200},
            timeout=60,
        )
        n_att = 0 if r2.status_code == 204 else len((r2.json() or {}).get("data") or [])
        if not r2.ok:
            n_att = -1
        rows.append(
            {
                "Product_Code": (p.get("Product_Code") or "").strip(),
                "Product_Name": (p.get("Product_Name") or "").strip(),
                "attachments": n_att,
                "has_product_image": bool(p.get("Record_Image")),
                "description_chars": len((p.get("Description") or "").strip()),
            }
        )

    print(json.dumps(rows, indent=2))
    missing_img = [x for x in rows if not x["has_product_image"]]
    zero_att = [x for x in rows if x["attachments"] == 0]
    print(
        f"\n# summary: {len(rows)} products | no image: {len(missing_img)} | zero attachments: {len(zero_att)}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
