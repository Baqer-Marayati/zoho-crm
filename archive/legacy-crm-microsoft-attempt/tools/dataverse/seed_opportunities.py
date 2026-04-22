#!/usr/bin/env python3
"""Seed demo rows into the new_opportunity table.

Re-runnable: an existing row with the same name is patched in place rather
than duplicated, so this script can be re-executed safely.
"""

from __future__ import annotations

import json
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(__file__))
from create_opportunity import (  # noqa: E402
    DATAVERSE_URL,
    PUBLISHER_PREFIX,
    acquire_token,
)


# Picklist option values must match the values declared in
# create_opportunity.py. Using a publisher-prefixed range keeps them stable
# across imports.
STAGE = {
    "Discovery": 100000000,
    "Qualify": 100000001,
    "Proposal": 100000002,
    "Negotiation": 100000003,
    "Commit": 100000004,
    "Closed Won": 100000005,
    "Closed Lost": 100000006,
}

TRACK = {
    "Industrial": 100000000,
    "Software": 100000001,
    "Service": 100000002,
    "Aftermarket": 100000003,
}


SEED_ROWS = [
    {
        "name": "Expand regional channel",
        "stage": "Proposal",
        "track": "Industrial",
        "amount": 124000,
        "reporting_amount": 124000,
        "close_date": "2026-06-30",
        "probability": 60,
        "owner": "A. Rahim",
        "rolling_summary": "Channel partner discussions advanced; awaiting "
                          "signed MOU.",
        "competitors": "Acme Industrial; Globex",
    },
    {
        "name": "Platform renewal",
        "stage": "Negotiation",
        "track": "Software",
        "amount": 86500,
        "reporting_amount": 86500,
        "close_date": "2026-05-12",
        "probability": 80,
        "owner": "S. Khan",
        "rolling_summary": "Annual renewal at higher tier; legal redlines "
                          "pending.",
        "competitors": "Initech",
    },
    {
        "name": "Service contract uplift",
        "stage": "Qualify",
        "track": "Service",
        "amount": 42000,
        "reporting_amount": 42000,
        "close_date": "2026-08-01",
        "probability": 30,
        "owner": "M. Abbas",
        "rolling_summary": "Customer evaluating extended service window; "
                          "decision in Q3.",
        "competitors": "In-house team",
    },
    {
        "name": "Spare parts framework",
        "stage": "Discovery",
        "track": "Aftermarket",
        "amount": 19200,
        "reporting_amount": 19200,
        "close_date": "2026-07-22",
        "probability": 20,
        "owner": "L. Saad",
        "rolling_summary": "Initial conversations on multi-year spare parts "
                          "framework.",
        "competitors": "Local distributor",
    },
    {
        "name": "Greenfield plant build-out",
        "stage": "Commit",
        "track": "Industrial",
        "amount": 612000,
        "reporting_amount": 612000,
        "close_date": "2026-09-15",
        "probability": 90,
        "owner": "A. Rahim",
        "rolling_summary": "Greenfield plant on track for award; PO "
                          "pending board approval.",
        "competitors": "Acme Industrial",
    },
]


def headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
        "OData-MaxVersion": "4.0",
        "OData-Version": "4.0",
        "Prefer": "return=representation",
    }


def find_existing(token: str, set_name: str, name: str) -> str | None:
    safe = name.replace("'", "''")
    url = (
        f"{DATAVERSE_URL}/api/data/v9.2/{set_name}"
        f"?$select={PUBLISHER_PREFIX}_opportunityid"
        f"&$filter={PUBLISHER_PREFIX}_name eq '{safe}'"
    )
    r = requests.get(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "OData-Version": "4.0",
    }, timeout=30)
    r.raise_for_status()
    rows = r.json().get("value", [])
    if not rows:
        return None
    return rows[0][f"{PUBLISHER_PREFIX}_opportunityid"]


def row_payload(spec: dict) -> dict:
    return {
        f"{PUBLISHER_PREFIX}_name": spec["name"],
        f"{PUBLISHER_PREFIX}_stage": STAGE[spec["stage"]],
        f"{PUBLISHER_PREFIX}_track": TRACK[spec["track"]],
        f"{PUBLISHER_PREFIX}_amount": spec["amount"],
        f"{PUBLISHER_PREFIX}_reportingamount": spec["reporting_amount"],
        f"{PUBLISHER_PREFIX}_closedate": spec["close_date"],
        f"{PUBLISHER_PREFIX}_probability": spec["probability"],
        f"{PUBLISHER_PREFIX}_owner": spec["owner"],
        f"{PUBLISHER_PREFIX}_rollingsummary": spec["rolling_summary"],
        f"{PUBLISHER_PREFIX}_competitors": spec["competitors"],
    }


def upsert(token: str, set_name: str, spec: dict) -> str:
    payload = row_payload(spec)
    existing_id = find_existing(token, set_name, spec["name"])
    if existing_id:
        url = (
            f"{DATAVERSE_URL}/api/data/v9.2/{set_name}"
            f"({existing_id})"
        )
        r = requests.patch(url, headers=headers(token), json=payload,
                           timeout=30)
        if r.status_code not in (200, 204):
            raise RuntimeError(f"PATCH failed: {r.status_code} {r.text}")
        return existing_id
    url = f"{DATAVERSE_URL}/api/data/v9.2/{set_name}"
    r = requests.post(url, headers=headers(token), json=payload, timeout=30)
    if r.status_code not in (200, 201, 204):
        raise RuntimeError(f"POST failed: {r.status_code} {r.text}")
    return r.json()[f"{PUBLISHER_PREFIX}_opportunityid"]


def discover_entity_set(token: str) -> str:
    """Return the EntitySetName (used in URL paths) for new_opportunity."""
    url = (
        f"{DATAVERSE_URL}/api/data/v9.2/EntityDefinitions"
        f"(LogicalName='{PUBLISHER_PREFIX}_opportunity')"
        "?$select=EntitySetName"
    )
    r = requests.get(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "OData-Version": "4.0",
    }, timeout=30)
    r.raise_for_status()
    return r.json()["EntitySetName"]


def main() -> int:
    token = acquire_token()
    set_name = discover_entity_set(token)
    print(f"Entity set: {set_name}")
    for spec in SEED_ROWS:
        rid = upsert(token, set_name, spec)
        print(f"  upserted: {spec['name']:30s} -> {rid}")
    print(f"\nSeeded {len(SEED_ROWS)} opportunities.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)
