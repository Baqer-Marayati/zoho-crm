#!/usr/bin/env python3
"""Sanity-check the new_opportunity table: columns + solution membership."""

from __future__ import annotations

import os
import sys

import requests

sys.path.insert(0, os.path.dirname(__file__))
from create_opportunity import (  # noqa: E402
    DATAVERSE_URL,
    SOLUTION_UNIQUE_NAME,
    PUBLISHER_PREFIX,
    acquire_token,
)


def main() -> int:
    token = acquire_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "OData-Version": "4.0",
    }

    logical = f"{PUBLISHER_PREFIX}_opportunity"
    url = (
        f"{DATAVERSE_URL}/api/data/v9.2/EntityDefinitions"
        f"(LogicalName='{logical}')?$select=LogicalName,SchemaName,"
        "DisplayName,DisplayCollectionName,ObjectTypeCode,MetadataId"
        "&$expand=Attributes($select=LogicalName,SchemaName,AttributeType,"
        "IsCustomAttribute)"
    )
    r = requests.get(url, headers=headers, timeout=30)
    if r.status_code != 200:
        print(f"Lookup failed: {r.status_code} {r.text}", file=sys.stderr)
        return 1
    meta = r.json()
    print(f"Table: {meta['SchemaName']} (object type {meta['ObjectTypeCode']})")
    print(f"  MetadataId: {meta['MetadataId']}")
    print(f"  Custom columns:")
    for a in sorted(meta.get("Attributes", []), key=lambda x: x["LogicalName"]):
        if a.get("IsCustomAttribute") and a["LogicalName"].startswith(
            f"{PUBLISHER_PREFIX}_"
        ):
            print(f"    - {a['SchemaName']:35s} {a['AttributeType']}")

    sol_url = (
        f"{DATAVERSE_URL}/api/data/v9.2/solutions"
        f"?$filter=uniquename eq '{SOLUTION_UNIQUE_NAME}'"
        "&$select=solutionid,uniquename,friendlyname"
    )
    sr = requests.get(sol_url, headers=headers, timeout=30)
    sols = sr.json().get("value", [])
    if not sols:
        print(f"\nSolution '{SOLUTION_UNIQUE_NAME}' not found in environment.")
        return 0
    sid = sols[0]["solutionid"]
    print(f"\nSolution: {sols[0]['uniquename']} ({sid})")

    comp_url = (
        f"{DATAVERSE_URL}/api/data/v9.2/solutioncomponents"
        f"?$filter=_solutionid_value eq {sid} and componenttype eq 1"
        "&$select=objectid,componenttype"
    )
    cr = requests.get(comp_url, headers=headers, timeout=30)
    comps = cr.json().get("value", [])
    has_table = any(c["objectid"].lower() == meta["MetadataId"].lower()
                    for c in comps)
    print(f"  Entity components: {len(comps)}")
    print(f"  Includes new_opportunity: {has_table}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
