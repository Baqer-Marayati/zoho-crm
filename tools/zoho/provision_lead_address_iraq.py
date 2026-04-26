#!/usr/bin/env python3
"""
Configure Iraq-specific address picklists on the Standard Leads layout.

Zoho's v8 Layout/Fields APIs do not allow moving or reconfiguring the built-in Address
subfields (Country, State, City, Zip, Coordinates). This script creates separate custom
picklists and places them in Address Information:

- Country (Iraq): single picklist option, Iraq.
- Province: Iraq governorates.
- City (Iraq): Iraq city options.
- Province -> City (Iraq) map dependency.

After running, the built-in address fields can still remain visible until hidden manually
in Zoho's page layout UI, because Zoho rejects API changes to address subfield layout config.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

import requests

from zoho_tokens import auth_headers, get_access_token_and_domain

API_VER = "v8"
MODULE = "Leads"

GOVERNORATES = [
    "Al Anbar",
    "Al Muthanna",
    "Al-Qādisiyyah",
    "Babylon",
    "Baghdad",
    "Basra",
    "Dhi Qar",
    "Diyala",
    "Dohuk",
    "Erbil",
    "Karbala",
    "Kirkuk",
    "Maysan",
    "Najaf",
    "Nineveh",
    "Saladin",
    "Sulaymaniyah",
    "Wasit",
]

CITIES_BY_GOVERNORATE = {
    "Al Anbar": ["Ramadi", "Fallujah", "Haditha", "Hit", "Al-Qaim", "Rutba"],
    "Al Muthanna": ["Samawah", "Rumaitha", "Al-Khidhir", "Salman"],
    "Al-Qādisiyyah": ["Diwaniyah", "Afak", "Al-Shamiya", "Hamza"],
    "Babylon": ["Hillah", "Al-Musayyib", "Haswa", "Al-Qasim"],
    "Baghdad": ["Baghdad", "Abu Ghraib", "Mahmoudiyah", "Taji"],
    "Basra": ["Basra", "Al-Zubair", "Umm Qasr", "Al-Qurna", "Shatt Al-Arab"],
    "Dhi Qar": ["Nasiriyah", "Suq Al-Shuyukh", "Shatrah", "Rifai"],
    "Diyala": ["Baqubah", "Muqdadiyah", "Khanaqin", "Balad Ruz", "Kifri"],
    "Dohuk": ["Dohuk", "Zakho", "Amedi", "Akre", "Semel"],
    "Erbil": ["Erbil", "Koya", "Shaqlawa", "Soran", "Mergasor"],
    "Karbala": ["Karbala", "Al-Hindiya", "Ain Al-Tamur"],
    "Kirkuk": ["Kirkuk", "Hawija", "Daquq", "Dibis"],
    "Maysan": ["Amarah", "Ali Al-Sharqi", "Al-Majar Al-Kabir", "Qal'at Saleh"],
    "Najaf": ["Najaf", "Kufa", "Al-Manathera", "Al-Mishkhab"],
    "Nineveh": ["Mosul", "Tal Afar", "Sinjar", "Hamdaniya", "Bartella", "Bashiqa"],
    "Saladin": ["Tikrit", "Samarra", "Balad", "Baiji", "Dujail", "Al-Shirqat"],
    "Sulaymaniyah": ["Sulaymaniyah", "Halabja", "Ranya", "Chamchamal", "Kalar", "Penjwen"],
    "Wasit": ["Kut", "Al-Hay", "Badra", "Numaniyah", "Suwaira"],
}


def _slug(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value).strip("_")[:100] or "value"


def _crm(session: requests.Session, api_domain: str, method: str, path: str, **kwargs):
    return session.request(
        method,
        f"{api_domain.rstrip('/')}/crm/{API_VER}{path}",
        timeout=120,
        **kwargs,
    )


def _token_with_retries(attempts: int = 5) -> tuple[str, str]:
    last_error: Exception | None = None
    for n in range(attempts):
        try:
            return get_access_token_and_domain()
        except RuntimeError as e:
            last_error = e
            if "too many requests" not in str(e).lower():
                raise
            time.sleep(min(30.0 * (2**n), 300.0))
    assert last_error
    raise last_error


def _session() -> tuple[requests.Session, str]:
    token, api_domain = _token_with_retries()
    session = requests.Session()
    session.headers.update(auth_headers(token))
    session.headers["Content-Type"] = "application/json"
    return session, api_domain


def _fields(session: requests.Session, api_domain: str) -> list[dict[str, Any]]:
    r = _crm(session, api_domain, "GET", "/settings/fields", params={"module": MODULE})
    r.raise_for_status()
    return r.json().get("fields") or []


def _by_label(fields: list[dict[str, Any]], label: str) -> dict[str, Any] | None:
    return next((f for f in fields if (f.get("field_label") or "").lower() == label.lower()), None)


def _pick_values(values: list[str]) -> list[dict[str, str]]:
    return [{"display_value": v, "actual_value": _slug(v)} for v in values]


def _ensure_picklist(
    session: requests.Session,
    api_domain: str,
    fields: list[dict[str, Any]],
    labels: list[str],
    values: list[str],
    default_value: str | None,
    dry_run: bool,
) -> dict[str, Any]:
    for label in labels:
        field = _by_label(fields, label)
        if field:
            print(f"Exists: {label} ({field.get('api_name')})")
            return field

    for label in labels:
        body = {
            "fields": [
                {
                    "field_label": label,
                    "data_type": "picklist",
                    "pick_list_values": _pick_values(values),
                    "pick_list_values_sorted_lexically": True,
                    "enable_colour_code": False,
                }
            ]
        }
        if default_value:
            body["fields"][0]["default_value"] = default_value
        print(f"POST picklist: {label}")
        if dry_run:
            return {"id": "dry-run", "api_name": _slug(label), "field_label": label}
        r = _crm(
            session,
            api_domain,
            "POST",
            "/settings/fields",
            params={"module": MODULE},
            data=json.dumps(body),
        )
        if r.ok:
            print(json.dumps(r.json(), indent=2)[:1500])
            return _by_label(_fields(session, api_domain), label) or {}
        print(f"  rejected {label}: HTTP {r.status_code} {r.text[:500]}")

    raise RuntimeError(f"Could not create any label from {labels}.")


def _standard_layout_id(session: requests.Session, api_domain: str) -> str:
    r = _crm(session, api_domain, "GET", "/settings/layouts", params={"module": MODULE})
    r.raise_for_status()
    layouts = r.json().get("layouts") or []
    for layout in layouts:
        if layout.get("name") == "Standard" and layout.get("status") == "active":
            return str(layout["id"])
    if not layouts:
        raise RuntimeError("No Leads layouts returned.")
    return str(layouts[0]["id"])


def _address_section_id(session: requests.Session, api_domain: str, layout_id: str) -> str:
    r = _crm(session, api_domain, "GET", f"/settings/layouts/{layout_id}", params={"module": MODULE})
    r.raise_for_status()
    layout = (r.json().get("layouts") or [None])[0]
    for section in layout.get("sections") or []:
        label = (section.get("name") or section.get("display_label") or "").lower()
        if "address" in label and section.get("id"):
            return str(section["id"])
    raise RuntimeError("Address Information section not found.")


def _add_fields_to_layout(
    session: requests.Session,
    api_domain: str,
    layout_id: str,
    section_id: str,
    fields: list[dict[str, Any]],
    dry_run: bool,
) -> bool:
    body = {
        "layouts": [
            {
                "sections": [
                    {
                        "id": section_id,
                        "fields": [{"id": str(f["id"])} for f in fields if f.get("id") != "dry-run"],
                    }
                ]
            }
        ]
    }
    print("PATCH layout: add Iraq custom address fields")
    if dry_run:
        print(json.dumps(body, indent=2))
        return True
    r = _crm(
        session,
        api_domain,
        "PATCH",
        f"/settings/layouts/{layout_id}",
        params={"module": MODULE},
        data=json.dumps(body),
    )
    if not r.ok:
        print(f"PATCH layout failed HTTP {r.status_code}: {r.text[:2000]}", file=sys.stderr)
        return False
    print(json.dumps(r.json(), indent=2)[:1500])
    return True


def _sync_dependency(
    session: requests.Session,
    api_domain: str,
    layout_id: str,
    province: dict[str, Any],
    city: dict[str, Any],
    dry_run: bool,
) -> bool:
    province_options = {
        o.get("display_value"): {
            "display_value": o.get("display_value"),
            "actual_value": o.get("actual_value") or o.get("display_value"),
            "id": str(o["id"]),
        }
        for o in province.get("pick_list_values") or []
        if o.get("display_value") and o.get("id")
    }
    city_options = {
        o.get("display_value"): {
            "display_value": o.get("display_value"),
            "actual_value": o.get("actual_value") or o.get("display_value"),
            "id": str(o["id"]),
        }
        for o in city.get("pick_list_values") or []
        if o.get("display_value") and o.get("id")
    }
    pick_list_values = []
    for governorate, cities in CITIES_BY_GOVERNORATE.items():
        if governorate not in province_options:
            continue
        pick_list_values.append(
            {
                **province_options[governorate],
                "maps": [city_options[c] for c in cities if c in city_options],
            }
        )

    body = {
        "map_dependency": [
            {
                "parent": {"api_name": province["api_name"], "id": str(province["id"])},
                "child": {"api_name": city["api_name"], "id": str(city["id"])},
                "pick_list_values": pick_list_values,
            }
        ]
    }
    print(f"POST/PUT map dependency: {province['api_name']} -> {city['api_name']}")
    if dry_run:
        print(json.dumps(body, indent=2)[:2500])
        return True

    r_get = _crm(
        session,
        api_domain,
        "GET",
        f"/settings/layouts/{layout_id}/map_dependency",
        params={"module": MODULE},
    )
    dep_id = None
    if r_get.ok and r_get.text.strip():
        for md in r_get.json().get("map_dependency") or []:
            parent = md.get("parent") or {}
            child = md.get("child") or {}
            if parent.get("api_name") == province["api_name"] and child.get("api_name") == city["api_name"]:
                dep_id = str(md.get("id"))
                break

    method = "PUT" if dep_id else "POST"
    path = (
        f"/settings/layouts/{layout_id}/map_dependency/{dep_id}"
        if dep_id
        else f"/settings/layouts/{layout_id}/map_dependency"
    )
    r = _crm(session, api_domain, method, path, params={"module": MODULE}, data=json.dumps(body))
    if not r.ok:
        print(f"{method} map_dependency failed HTTP {r.status_code}: {r.text[:2000]}", file=sys.stderr)
        return False
    print(json.dumps(r.json(), indent=2)[:1500])
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision Iraq custom address picklists on Leads.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    session, api_domain = _session()
    fields = _fields(session, api_domain)

    country = _ensure_picklist(
        session, api_domain, fields, ["Country", "Country (Iraq)"], ["Iraq"], "Iraq", args.dry_run
    )
    fields = _fields(session, api_domain)
    province = _ensure_picklist(
        session, api_domain, fields, ["Province", "Province (Iraq)"], GOVERNORATES, None, args.dry_run
    )
    fields = _fields(session, api_domain)
    city_values = sorted({city for cities in CITIES_BY_GOVERNORATE.values() for city in cities})
    city = _ensure_picklist(
        session, api_domain, fields, ["City", "City (Iraq)"], city_values, None, args.dry_run
    )

    layout_id = _standard_layout_id(session, api_domain)
    section_id = _address_section_id(session, api_domain, layout_id)
    ok = _add_fields_to_layout(
        session, api_domain, layout_id, section_id, [country, province, city], args.dry_run
    )
    if not args.dry_run:
        fields = _fields(session, api_domain)
        province = _by_label(fields, province["field_label"]) or province
        city = _by_label(fields, city["field_label"]) or city
    ok = _sync_dependency(session, api_domain, layout_id, province, city, args.dry_run) and ok

    print(
        "Note: Zoho rejected API hiding/reconfiguring of built-in Address subfields; "
        "hide those in the UI layout editor if they remain visible."
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
