#!/usr/bin/env python3
"""Create the scrCRM Opportunity table in Dataverse via the Web API.

Why Web API instead of the .NET SDK:
  The classic SDK pattern requires juggling several NuGet packages with
  conflicting target frameworks. The Web API is a plain HTTPS call that we
  can drive from Python with MSAL + requests; far fewer moving parts.

What this script does:
  1. Acquires a delegated token for the target Dataverse environment using
     MSAL's device-code flow (the same flow `pac auth create` uses).
  2. POSTs a single EntityDefinitions payload containing the table and all
     of its attributes, scoped to the `scrCRMDataverse` solution so the
     table shows up under that solution in the maker portal.
  3. Publishes customizations so the new metadata is immediately usable.

Re-runnable: if the table already exists, the script exits cleanly without
attempting to recreate it.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import msal
import requests


DATAVERSE_URL = os.environ.get(
    "DATAVERSE_URL", "https://org05dfdf92.crm4.dynamics.com"
).rstrip("/")
SOLUTION_UNIQUE_NAME = os.environ.get("SOLUTION_UNIQUE_NAME", "scrCRMDataverse")
PUBLISHER_PREFIX = os.environ.get("PUBLISHER_PREFIX", "new")

# Microsoft Azure CLI public client. It is pre-installed in every Entra
# tenant and supports the device-code flow with arbitrary first-party
# resource audiences (including Dataverse).
CLIENT_ID = os.environ.get("CLIENT_ID", "04b07795-8ddb-461a-bbee-02f9e1bf7b46")

# Device-code flow needs a tenant-bound authority (login.microsoftonline.com/
# common is rejected). Override with TENANT_ID env var for other tenants.
TENANT_ID = os.environ.get("TENANT_ID", "53ea674b-813e-46a3-9961-f0b04a117e08")
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"

TOKEN_CACHE_PATH = Path(__file__).resolve().parent / ".token_cache.json"


def _load_cache() -> msal.SerializableTokenCache:
    cache = msal.SerializableTokenCache()
    if TOKEN_CACHE_PATH.exists():
        cache.deserialize(TOKEN_CACHE_PATH.read_text())
    return cache


def _save_cache(cache: msal.SerializableTokenCache) -> None:
    if cache.has_state_changed:
        TOKEN_CACHE_PATH.write_text(cache.serialize())
        try:
            os.chmod(TOKEN_CACHE_PATH, 0o600)
        except OSError:
            pass


def acquire_token() -> str:
    scopes = [f"{DATAVERSE_URL}/.default"]
    cache = _load_cache()
    app = msal.PublicClientApplication(
        CLIENT_ID, authority=AUTHORITY, token_cache=cache
    )

    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(scopes, account=accounts[0])
        if result and "access_token" in result:
            _save_cache(cache)
            return result["access_token"]

    flow = app.initiate_device_flow(scopes=scopes)
    if "user_code" not in flow:
        raise RuntimeError(
            "Could not start device-code flow: " + json.dumps(flow, indent=2)
        )
    print()
    print("=" * 70)
    print("Sign in to Dataverse to authorize this script")
    print("=" * 70)
    print(flow["message"])
    print("=" * 70, flush=True)

    result = app.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        raise RuntimeError(
            "Token acquisition failed: " + json.dumps(result, indent=2)
        )
    _save_cache(cache)
    return result["access_token"]


def _localized_label(text: str) -> dict:
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.Label",
        "LocalizedLabels": [
            {
                "@odata.type": "Microsoft.Dynamics.CRM.LocalizedLabel",
                "Label": text,
                "LanguageCode": 1033,
            }
        ],
    }


def _required(level: str = "None") -> dict:
    return {
        "Value": level,
        "CanBeChanged": True,
        "ManagedPropertyLogicalName": "canmodifyrequirementlevelsettings",
    }


def _option(value: int, label: str) -> dict:
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.OptionMetadata",
        "Value": value,
        "Label": _localized_label(label),
    }


def _picklist(schema: str, display: str, options: list[tuple[int, str]],
              required: str = "ApplicationRequired") -> dict:
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.PicklistAttributeMetadata",
        "AttributeType": "Picklist",
        "AttributeTypeName": {"Value": "PicklistType"},
        "SchemaName": f"{PUBLISHER_PREFIX}_{schema}",
        "DisplayName": _localized_label(display),
        "Description": _localized_label(display),
        "RequiredLevel": _required(required),
        "OptionSet": {
            "@odata.type": "Microsoft.Dynamics.CRM.OptionSetMetadata",
            "OptionSetType": "Picklist",
            "IsGlobal": False,
            "Options": [_option(v, l) for v, l in options],
        },
    }


def _string(schema: str, display: str, max_length: int = 200,
            required: str = "None", is_primary: bool = False) -> dict:
    attr = {
        "@odata.type": "Microsoft.Dynamics.CRM.StringAttributeMetadata",
        "AttributeType": "String",
        "AttributeTypeName": {"Value": "StringType"},
        "SchemaName": f"{PUBLISHER_PREFIX}_{schema}",
        "DisplayName": _localized_label(display),
        "Description": _localized_label(display),
        "RequiredLevel": _required(required),
        "MaxLength": max_length,
        "FormatName": {"Value": "Text"},
    }
    if is_primary:
        attr["IsPrimaryName"] = True
    return attr


def _memo(schema: str, display: str, max_length: int = 4000) -> dict:
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.MemoAttributeMetadata",
        "AttributeType": "Memo",
        "AttributeTypeName": {"Value": "MemoType"},
        "SchemaName": f"{PUBLISHER_PREFIX}_{schema}",
        "DisplayName": _localized_label(display),
        "Description": _localized_label(display),
        "RequiredLevel": _required("None"),
        "MaxLength": max_length,
        "Format": "Text",
        "ImeMode": "Disabled",
    }


def _money(schema: str, display: str) -> dict:
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.MoneyAttributeMetadata",
        "AttributeType": "Money",
        "AttributeTypeName": {"Value": "MoneyType"},
        "SchemaName": f"{PUBLISHER_PREFIX}_{schema}",
        "DisplayName": _localized_label(display),
        "Description": _localized_label(display),
        "RequiredLevel": _required("None"),
        "Precision": 2,
        "PrecisionSource": 2,
        "ImeMode": "Disabled",
    }


def _date(schema: str, display: str, required: str = "ApplicationRequired") -> dict:
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.DateTimeAttributeMetadata",
        "AttributeType": "DateTime",
        "AttributeTypeName": {"Value": "DateTimeType"},
        "SchemaName": f"{PUBLISHER_PREFIX}_{schema}",
        "DisplayName": _localized_label(display),
        "Description": _localized_label(display),
        "RequiredLevel": _required(required),
        "Format": "DateOnly",
        "DateTimeBehavior": {"Value": "DateOnly"},
        "ImeMode": "Disabled",
    }


def _integer(schema: str, display: str,
             min_value: int = 0, max_value: int = 1_000_000_000) -> dict:
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.IntegerAttributeMetadata",
        "AttributeType": "Integer",
        "AttributeTypeName": {"Value": "IntegerType"},
        "SchemaName": f"{PUBLISHER_PREFIX}_{schema}",
        "DisplayName": _localized_label(display),
        "Description": _localized_label(display),
        "RequiredLevel": _required("None"),
        "MinValue": min_value,
        "MaxValue": max_value,
        "Format": "None",
    }


def build_entity_payload() -> dict:
    primary_name = _string(
        schema="Name",
        display="Name",
        max_length=200,
        required="ApplicationRequired",
        is_primary=True,
    )

    stage = _picklist(
        schema="Stage",
        display="Stage",
        options=[
            (100000000, "Discovery"),
            (100000001, "Qualify"),
            (100000002, "Proposal"),
            (100000003, "Negotiation"),
            (100000004, "Commit"),
            (100000005, "Closed Won"),
            (100000006, "Closed Lost"),
        ],
    )

    track = _picklist(
        schema="Track",
        display="Track",
        options=[
            (100000000, "Industrial"),
            (100000001, "Software"),
            (100000002, "Service"),
            (100000003, "Aftermarket"),
        ],
    )

    attributes = [
        primary_name,
        stage,
        track,
        _money("Amount", "Amount"),
        _money("ReportingAmount", "Reporting Amount"),
        _date("CloseDate", "Close Date"),
        _integer("Probability", "Probability", min_value=0, max_value=100),
        _memo("RollingSummary", "Rolling Summary"),
        _memo("Competitors", "Competitors"),
        _string("Owner", "Owner Name", max_length=200),
    ]

    return {
        "@odata.type": "Microsoft.Dynamics.CRM.EntityMetadata",
        "SchemaName": f"{PUBLISHER_PREFIX}_Opportunity",
        "DisplayName": _localized_label("Opportunity"),
        "DisplayCollectionName": _localized_label("Opportunities"),
        "Description": _localized_label("scrCRM sales opportunity"),
        "OwnershipType": "UserOwned",
        "HasActivities": True,
        "HasNotes": True,
        "IsActivity": False,
        "IsAvailableOffline": True,
        "Attributes": attributes,
    }


def entity_exists(token: str, logical_name: str) -> bool:
    url = (
        f"{DATAVERSE_URL}/api/data/v9.2/EntityDefinitions"
        f"(LogicalName='{logical_name}')?$select=LogicalName"
    )
    resp = requests.get(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "OData-Version": "4.0",
    }, timeout=30)
    if resp.status_code == 200:
        return True
    if resp.status_code == 404:
        return False
    raise RuntimeError(f"Lookup failed ({resp.status_code}): {resp.text}")


def create_entity(token: str, payload: dict) -> None:
    url = f"{DATAVERSE_URL}/api/data/v9.2/EntityDefinitions"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
        "OData-MaxVersion": "4.0",
        "OData-Version": "4.0",
        "MSCRM.SolutionUniqueName": SOLUTION_UNIQUE_NAME,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    if resp.status_code not in (200, 201, 204):
        raise RuntimeError(
            f"Create entity failed ({resp.status_code}):\n{resp.text}"
        )
    print(f"Created entity: {payload['SchemaName']}")


def publish_all(token: str) -> None:
    url = f"{DATAVERSE_URL}/api/data/v9.2/PublishAllXml"
    resp = requests.post(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "OData-Version": "4.0",
    }, timeout=120)
    if resp.status_code not in (200, 204):
        raise RuntimeError(
            f"Publish failed ({resp.status_code}): {resp.text}"
        )
    print("Published customizations.")


def main() -> int:
    print(f"Dataverse URL : {DATAVERSE_URL}")
    print(f"Solution      : {SOLUTION_UNIQUE_NAME}")
    print(f"Prefix        : {PUBLISHER_PREFIX}")

    token = acquire_token()

    logical = f"{PUBLISHER_PREFIX}_opportunity"
    if entity_exists(token, logical):
        print(f"Table already exists: {logical}. Skipping create.")
    else:
        payload = build_entity_payload()
        create_entity(token, payload)

    publish_all(token)
    print()
    print("Done. In Power Apps Studio, add the 'Opportunities' table as a "
          "data source to scrCRM.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:  # noqa: BLE001
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)
