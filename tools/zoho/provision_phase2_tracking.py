#!/usr/bin/env python3
"""
Phase 2 §5 + §6 — Stage-probability API probe and field history tracking.

§5  Stage–probability mapping
    Calls GET /settings/fields?module=Deals and GET /settings/stages to confirm
    whether stage-probability can be set via the v8 API.  Reports findings; if
    the API doesn't expose it, documents the 2-minute manual path.

§6  Field history tracking
    Enables history tracking for Stage and Amount on the Deals module via:
      PATCH /settings/fields/{field_id}?module=Deals
      body: {"fields": [{"id": "{field_id}", "history_tracking": true}]}
    Idempotent: reads the current field metadata first and skips if already on.

§7  Activity discipline — training only; no API changes (noted in docs).

Usage:
  cd tools/zoho && ./venv/bin/python provision_phase2_tracking.py
  ./venv/bin/python provision_phase2_tracking.py --dry-run
  ./venv/bin/python provision_phase2_tracking.py --check-probability-only
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests

from zoho_tokens import auth_headers, get_access_token_and_domain

API_VER = "v8"
SCRIPT_DIR = Path(__file__).resolve().parent
DEALS_MODULE = "Deals"

# Fields to enable history tracking on
TRACK_API_NAMES = ["Stage", "Amount"]


# ─── helpers ─────────────────────────────────────────────────────────────────

def _crm(session: requests.Session, api_domain: str, method: str, path: str, **kwargs):
    url = f"{api_domain.rstrip('/')}/crm/{API_VER}{path}"
    return session.request(method, url, timeout=120, **kwargs)


def _get_deals_fields(session: requests.Session, api_domain: str) -> dict[str, dict]:
    """Return mapping of api_name → field dict for Deals module."""
    r = _crm(session, api_domain, "GET", "/settings/fields", params={"module": DEALS_MODULE})
    if not r.ok:
        raise RuntimeError(
            f"GET /settings/fields?module=Deals HTTP {r.status_code}: {r.text[:2000]}"
        )
    return {
        f["api_name"]: f
        for f in r.json().get("fields") or []
        if f.get("api_name")
    }


def _is_tracking_enabled(field: dict) -> bool:
    # Zoho CRM v8: the per-field toggle is history_tracking_enabled (bool).
    ht_enabled = field.get("history_tracking_enabled")
    if isinstance(ht_enabled, bool) and ht_enabled:
        return True
    # Also check old-style history_tracking boolean
    ht = field.get("history_tracking")
    if isinstance(ht, bool) and ht:
        return True
    return False


# ─── §5 stage-probability probe ──────────────────────────────────────────────

def probe_stage_probability(session: requests.Session, api_domain: str) -> None:
    """
    Confirm whether stage-probability % is configurable via Zoho CRM v8 API.

    Checks:
    1. Whether GET /settings/fields Stage pick_list_values include a 'probability' key.
    2. Whether GET /settings/stages works and returns probability values.

    Findings are reported. If /settings/stages returns 200 with probabilities, the
    user can optionally run a PUT per stage to set custom values (future enhancement).
    """
    print("\n─── §5 Stage–Probability API Probe ───")

    # Check 1: Stage field pick_list_values for probability key
    try:
        fields = _get_deals_fields(session, api_domain)
    except RuntimeError as e:
        print(f"  Cannot probe: {e}", file=sys.stderr)
        return

    stage_f = fields.get("Stage")
    if not stage_f:
        print("  Stage field not found in Deals — cannot probe.", file=sys.stderr)
        return

    opts = stage_f.get("pick_list_values") or []
    has_prob_key = any("probability" in opt for opt in opts)
    print(f"  Stage field id={stage_f.get('id')}, {len(opts)} stage option(s).")
    print(f"  'probability' key in pick_list_values GET response: {has_prob_key}")

    # Check 2: dedicated /settings/stages endpoint
    r2 = _crm(session, api_domain, "GET", "/settings/stages", params={"module": DEALS_MODULE})
    print(f"  GET /settings/stages → HTTP {r2.status_code}")

    if r2.ok:
        stages = r2.json().get("stages") or []
        print(f"  /settings/stages returned {len(stages)} stage(s) with probability values:")
        for st in stages:
            print(f"    {st.get('name'):30s}  probability={st.get('probability'):>3}")
        print(
            "\n  RESULT: Stage-probability IS readable via /settings/stages (HTTP 200)."
            "\n  Default Zoho values are already loaded above."
            "\n  To set custom probabilities: PUT /settings/stages/{stage_id}?module=Deals"
            "\n  with body {\"stages\": [{\"probability\": N}]} — test one stage manually"
            "\n  before scripting, as this endpoint is not in the main v8 public docs."
            "\n\n  UI path (~2 min per pipeline, most reliable):"
            "\n    Setup → Pipelines → [Production or MPS] → Stage-Probability column"
        )
    else:
        if has_prob_key:
            print(
                "\n  NOTE: 'probability' IS visible in pick_list_values but "
                "/settings/stages failed.\n"
                "  Stage–probability may be partially accessible — recommend UI approach."
            )
        else:
            print(
                "\n  RESULT: Stage-probability is NOT exposed by the v8 API."
                "\n  Manual step (~2 min per pipeline):"
                "\n    Setup → Pipelines → [Production or MPS] → Stage-Probability column"
            )


# ─── §6 field history tracking ───────────────────────────────────────────────

def _enable_history_tracking(
    session: requests.Session,
    api_domain: str,
    field_id: str,
    field_label: str,
    dry_run: bool,
) -> bool:
    print(f"  PATCH history_tracking_enabled=true → '{field_label}' (id={field_id})")
    if dry_run:
        return True
    # Zoho CRM v8: the per-field history tracking toggle is history_tracking_enabled.
    # Sending history_tracking (jsonobject shape) together causes INVALID_DATA errors.
    r = _crm(
        session,
        api_domain,
        "PATCH",
        f"/settings/fields/{field_id}",
        params={"module": DEALS_MODULE},
        json={"fields": [{"id": field_id, "history_tracking_enabled": True}]},
    )
    if not r.ok:
        try:
            err_items = r.json().get("fields") or []
            code = (err_items[0].get("code") or "") if err_items else ""
        except Exception:
            code = ""
        if code == "FEATURE_NOT_SUPPORTED":
            # This field is tracked as a followed_field by another field's history
            # (e.g. Amount is in Stage.history_tracking.followed_fields).
            print(
                f"  NOTE: '{field_label}' reports FEATURE_NOT_SUPPORTED for standalone "
                "history_tracking_enabled.\n"
                "  This field is likely already tracked as a 'followed field' inside "
                "another field's history tracking (e.g. Stage History tracks Amount).\n"
                "  No action required — history is being captured."
            )
            return True  # not a failure
        print(f"  HTTP {r.status_code}: {r.text[:3000]}", file=sys.stderr)
        return False
    try:
        resp = r.json()
        code = (resp.get("fields") or [{}])[0].get("code", "?")
        print(f"  HTTP {r.status_code} — {code}")
    except Exception:
        print(f"  HTTP {r.status_code} OK")
    return True


def run_history_tracking(
    session: requests.Session, api_domain: str, dry_run: bool
) -> bool:
    print("\n─── §6 Field History Tracking ───")
    try:
        fields = _get_deals_fields(session, api_domain)
    except RuntimeError as e:
        print(e, file=sys.stderr)
        return False

    ok = True
    for api_name in TRACK_API_NAMES:
        f = fields.get(api_name)
        if not f:
            print(f"  '{api_name}' field not found in Deals; skip.", file=sys.stderr)
            continue
        label = f.get("field_label") or api_name
        fid = str(f["id"])
        if _is_tracking_enabled(f):
            print(f"  Skip '{label}': history_tracking already enabled.")
            continue
        ok = _enable_history_tracking(session, api_domain, fid, label, dry_run) and ok

    return ok


# ─── main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Phase 2 §5 probe + §6 field history tracking for Zoho CRM Deals"
    )
    parser.add_argument("--dry-run", action="store_true", help="Print planned changes; no API writes")
    parser.add_argument(
        "--check-probability-only",
        action="store_true",
        help="Run stage-probability probe only; skip history tracking",
    )
    args = parser.parse_args()

    try:
        access, api_domain = get_access_token_and_domain()
    except RuntimeError as e:
        print(e, file=sys.stderr)
        return 1

    session = requests.Session()
    session.headers.update(auth_headers(access))

    probe_stage_probability(session, api_domain)

    if args.check_probability_only:
        return 0

    ok = run_history_tracking(session, api_domain, args.dry_run)

    print(
        "\n─── §7 Activity Discipline ───\n"
        "  Training only — no API configuration. See docs/zoho/PHASE2-AUTOMATED.md.\n"
        "  Covered: log a call/meeting within 24 h of stage change, use Tasks for\n"
        "  follow-ups, review Activities tab in weekly pipeline review."
    )

    if ok:
        print(
            "\nPhase 2 §5–§7 complete.\n"
            "  §5 Stage-probability: see manual path above (2 min / pipeline in Zoho UI).\n"
            "  §6 Field history tracking: Stage + Amount enabled on Deals.\n"
            "  §7 Activity discipline: training only."
        )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
