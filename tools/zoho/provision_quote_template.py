#!/usr/bin/env python3
"""
Create (or update) the Aljazeera Machinery sales quotation PDF template in Zoho CRM.

Usage:
    cd tools/zoho
    ./venv/bin/python provision_quote_template.py [--dry-run]

Flags:
    --dry-run   Print the payload instead of calling the API.
    --replace   If a template named "Aljazeera Quotation" already exists, delete
                it first then recreate (default: skip if already exists).
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

# ── Config ──────────────────────────────────────────────────────────────────

TEMPLATE_NAME = "Aljazeera Quotation"
FOLDER_ID     = "7353692000000740772"   # Public Templates folder in this org
LOGO_PATH     = Path("/Users/baqer/Dropbox/Work/Logos/Aljazeera.png")

# 260 px-wide thumbnail is embedded as base64 so the PDF works without
# a public URL.  Regenerate with: sips -Z 260 Aljazeera.png --out /tmp/logo_sm.png
LOGO_SM_PATH  = Path("/tmp/aljazeera_logo_sm.png")

ENV_PATH = Path(__file__).resolve().parent / ".env"

# ── Helpers ──────────────────────────────────────────────────────────────────

def _logo_b64() -> str:
    """Return the base64 string of the resized logo, creating it if needed."""
    if not LOGO_SM_PATH.exists():
        if not LOGO_PATH.exists():
            print(f"[warn] Logo not found at {LOGO_PATH}, skipping logo embed.", file=sys.stderr)
            return ""
        os.system(f'sips -Z 260 "{LOGO_PATH}" --out "{LOGO_SM_PATH}" > /dev/null 2>&1')
    data = LOGO_SM_PATH.read_bytes()
    return base64.b64encode(data).decode()


def _get_token(accounts: str, client_id: str, client_secret: str, refresh_token: str) -> tuple[str, str]:
    resp = requests.post(
        f"{accounts}/oauth/v2/token",
        data={
            "grant_type":    "refresh_token",
            "client_id":     client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        },
        timeout=60,
    )
    resp.raise_for_status()
    d = resp.json()
    return d["access_token"], d.get("api_domain", "https://www.zohoapis.com")


# ── HTML Template ────────────────────────────────────────────────────────────
# Design: clean document-style (inspired by Zylker Electronics reference).
# White background, thin border card, logo top-left + QUOTATION top-right in navy,
# label:value meta rows, polished customer panel, navy table header, navy Balance Due row.

def build_html(logo_b64: str) -> str:
    logo_img = (
        f'<img src="data:image/png;base64,{logo_b64}" alt="Aljazeera Machinery"'
        ' height="46" style="display:block;margin-bottom:6px;" />'
        if logo_b64
        else '<div style="font-size:18px;font-weight:700;color:#1B2B4B;">Aljazeera Machinery</div>'
    )

    return f"""<table border="0" cellspacing="0" cellpadding="0" width="100%"
  style="background:#EAECF0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">
<tr><td align="center" style="padding:20px 12px;">

<!-- ═══ DOCUMENT CARD ═══════════════════════════════════════════════════════ -->
<table border="0" cellspacing="0" cellpadding="0" width="760"
  style="background:#FFFFFF;border:1px solid #C8CDD5;border-bottom:3px solid #C8CDD5;">

  <!-- ── 1. HEADER: logo left · QUOTATION right ─────────────────────────── -->
  <tr>
    <td style="padding:28px 32px 20px 32px;">
      <table border="0" cellspacing="0" cellpadding="0" width="100%">
        <tr>
          <td width="55%" valign="top">
            {logo_img}
            <div style="font-size:11px;color:#6B7280;line-height:1.7;">
              ${{!org.street}}<br>
              ${{!org.city}} ${{!org.state}}<br>
              ${{!org.country}}
            </div>
          </td>
          <td width="45%" valign="bottom" align="right">
            <div style="font-size:26px;font-weight:700;color:#1B3C8C;letter-spacing:2px;">QUOTATION</div>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- ── divider ──────────────────────────────────────────────────────────── -->
  <tr><td style="padding:0 32px;">
    <div style="border-top:1px solid #DDE1E8;"></div>
  </td></tr>

  <!-- ── 2. META: label : value grid ──────────────────────────────────────── -->
  <tr>
    <td style="padding:14px 32px 16px;">
      <table border="0" cellspacing="0" cellpadding="4" width="100%"
             style="font-size:12px;color:#1C2434;">
        <tr>
          <td width="17%" style="color:#6B7280;">Quote #</td>
          <td width="1%"  style="color:#6B7280;">:</td>
          <td width="32%" style="font-weight:600;">${{!Quotes.Quote_Number}}</td>
          <td width="17%" style="color:#6B7280;">Date</td>
          <td width="1%"  style="color:#6B7280;">:</td>
          <td width="32%" style="font-weight:600;">
            <span style="display:inline-block;width:64px;max-width:64px;white-space:nowrap;overflow:hidden;vertical-align:bottom;">
              ${{!Quotes.Created_Time}}
            </span>
          </td>
        </tr>
        <tr>
          <td style="color:#6B7280;">Payment Terms</td>
          <td style="color:#6B7280;">:</td>
          <td style="font-weight:600;">${{!Quotes.Payment_Terms}}</td>
          <td style="color:#6B7280;">Valid Until</td>
          <td style="color:#6B7280;">:</td>
          <td style="font-weight:600;">14 Days</td>
        </tr>
        <tr>
          <td style="color:#6B7280;">Reference</td>
          <td style="color:#6B7280;">:</td>
          <td style="font-weight:600;">${{!Quotes.Subject}}</td>
          <td style="color:#6B7280;">Sales Person</td>
          <td style="color:#6B7280;">:</td>
          <td style="font-weight:600;">${{!Quotes.Owner}}</td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- ── divider ──────────────────────────────────────────────────────────── -->
  <tr><td style="padding:0 32px;">
    <div style="border-top:1px solid #DDE1E8;"></div>
  </td></tr>

  <!-- ── 3. CUSTOMER DETAILS ───────────────────────────────────────────────── -->
  <tr>
    <td style="padding:10px 32px 12px;">
      <table border="0" cellspacing="0" cellpadding="0" width="100%"
             style="background:#F4F6FA;border:1px solid #DDE1E8;border-left:4px solid #1B3C8C;">
        <tr>
          <td width="40%" valign="top" style="padding:12px 18px 12px;">
            <div style="font-size:10px;font-weight:700;color:#8894A8;
                        text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">Company Details</div>
            <div style="font-size:13px;font-weight:700;color:#1C2434;margin-bottom:5px;">
              ${{!org.company_name}}
            </div>
            <div style="font-size:12px;color:#4B5B6E;line-height:1.5;">
              ${{!org.street}}<br>
              ${{!org.city}} ${{!org.state}}<br>
              ${{!org.country}}<br>
              +964 781 300 0007<br>
              info@aljazeeramachinery.com
            </div>
          </td>
          <td width="10%">&nbsp;</td>
          <td width="50%" valign="top" style="padding:12px 18px 12px 28px;border-left:1px solid #DDE1E8;">
            <div style="font-size:10px;font-weight:700;color:#8894A8;
                        text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">Bill To</div>
            <div style="font-size:13px;font-weight:700;color:#1C2434;margin-bottom:5px;">
              ${{!Quotes.Account_Name}}
            </div>
            <div style="font-size:12px;color:#4B5B6E;line-height:1.5;">
              Attn: ${{!Quotes.Contact_Name}}<br>
              ${{!Quotes.Billing_Street}}<br>
              ${{!Quotes.Billing_City}} ${{!Quotes.Billing_State}}<br>
              ${{!Quotes.Billing_Country}}
            </div>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- ── 4. PRODUCTS TABLE ────────────────────────────────────────────────── -->
  <tr>
    <td style="padding:0 32px;">
      <table border="0" cellspacing="0" cellpadding="0" width="100%"
             style="font-size:12px;border-collapse:collapse;">
        <thead>
          <tr>
            <td bgcolor="#1B2B4B"
                style="color:#FFF;font-size:10px;font-weight:700;padding:10px 8px;
                       text-align:center;width:4%;">#</td>
            <td bgcolor="#1B2B4B"
                style="color:#FFF;font-size:10px;font-weight:700;padding:10px 12px;width:40%;">
              Item &amp; Description</td>
            <td bgcolor="#1B2B4B"
                style="color:#FFF;font-size:10px;font-weight:700;padding:10px 8px;
                       text-align:center;width:9%;">Qty</td>
            <td bgcolor="#1B2B4B"
                style="color:#FFF;font-size:10px;font-weight:700;padding:10px 8px;
                       text-align:right;width:14%;">Rate</td>
            <td bgcolor="#1B2B4B"
                style="color:#FFF;font-size:10px;font-weight:700;padding:10px 8px;
                       text-align:right;width:11%;">Discount</td>
            <td bgcolor="#1B2B4B"
                style="color:#FFF;font-size:10px;font-weight:700;padding:10px 8px;
                       text-align:right;width:14%;">Amount</td>
          </tr>
        </thead>
        <tbody id="subform_1">
          <tr>
            <td valign="top" align="center"
                style="padding:11px 8px;border-bottom:1px solid #E8ECF0;
                       color:#8894A8;font-size:11px;">
              ${{!Quotes.Quoted_Items.Sequence_Number}}
            </td>
            <td valign="top" style="padding:11px 12px;border-bottom:1px solid #E8ECF0;">
              <div style="font-weight:700;color:#1C2434;font-size:12px;">
                ${{!Quotes.Quoted_Items.Product_Name.Product_Name}}
              </div>
              <div style="font-size:10px;color:#8894A8;margin-top:2px;">
                ${{!Quotes.Quoted_Items.Product_Name.Product_Code}}
              </div>
              <div style="font-size:11px;color:#5A6878;margin-top:4px;line-height:1.5;">
                ${{!Quotes.Quoted_Items.Description}}
              </div>
            </td>
            <td valign="top" align="center"
                style="padding:11px 8px;border-bottom:1px solid #E8ECF0;color:#1C2434;">
              ${{!Quotes.Quoted_Items.Quantity}}
            </td>
            <td valign="top" align="right"
                style="padding:11px 8px;border-bottom:1px solid #E8ECF0;color:#1C2434;">
              ${{!Quotes.Quoted_Items.List_Price}}
            </td>
            <td valign="top" align="right"
                style="padding:11px 8px;border-bottom:1px solid #E8ECF0;color:#5A6878;">
              ${{!Quotes.Quoted_Items.Discount}}
            </td>
            <td valign="top" align="right"
                style="padding:11px 8px;border-bottom:1px solid #E8ECF0;
                       font-weight:700;color:#1C2434;">
              ${{!Quotes.Quoted_Items.Total}}
            </td>
          </tr>
        </tbody>
      </table>
    </td>
  </tr>

  <!-- ── 5. TOTALS ────────────────────────────────────────────────────────── -->
  <tr>
    <td style="padding:0 32px 8px;">
      <table border="0" cellspacing="0" cellpadding="0" width="100%">
        <tr>
          <td width="55%">&nbsp;</td>
          <td width="45%">
            <table border="0" cellspacing="0" cellpadding="0" width="100%"
                   style="font-size:12px;border:1px solid #DDE1E8;border-top:none;">
              <tr>
                <td style="padding:8px 14px;color:#6B7280;border-top:1px solid #DDE1E8;
                           border-bottom:1px solid #DDE1E8;">Sub Total</td>
                <td align="right"
                    style="padding:8px 14px;color:#1C2434;border-top:1px solid #DDE1E8;
                           border-bottom:1px solid #DDE1E8;">${{!Quotes.Sub_Total}}</td>
              </tr>
              <tr>
                <td style="padding:6px 14px;color:#6B7280;border-bottom:1px solid #DDE1E8;">
                  Discount</td>
                <td align="right"
                    style="padding:6px 14px;color:#1C2434;border-bottom:1px solid #DDE1E8;">
                  ${{!Quotes.Discount}}</td>
              </tr>
              <!-- Balance Due — matches the navy "Balance Due" row in the reference -->
              <tr bgcolor="#1B2B4B">
                <td style="padding:12px 14px;color:#FFFFFF;font-weight:700;font-size:13px;">
                  Balance Due</td>
                <td align="right"
                    style="padding:12px 14px;color:#FFFFFF;font-weight:700;font-size:14px;">
                  ${{!Quotes.Grand_Total}}</td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- ── divider ──────────────────────────────────────────────────────────── -->
  <tr><td style="padding:6px 32px 0;">
    <div style="border-top:1px solid #DDE1E8;"></div>
  </td></tr>

  <!-- ── 6. THANKS + NOTES ────────────────────────────────────────────────── -->
  <tr>
    <td style="padding:16px 32px 4px;">
      <table border="0" cellspacing="0" cellpadding="0" width="100%">
        <tr>
          <td width="100%" valign="top">
            <div style="font-size:12px;color:#5A6878;font-style:italic;margin-bottom:12px;">
              Thank you for your business with Aljazeera Machinery.
            </div>
            <div style="font-size:12px;color:#4B5B6E;line-height:1.75;">
              ${{!Quotes.Description}}
            </div>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- ── 7. TERMS & CONDITIONS ────────────────────────────────────────────── -->
  <tr>
    <td style="padding:14px 32px 18px;">
      <div style="font-size:11px;font-weight:700;color:#1C2434;margin-bottom:5px;">
        Terms &amp; Conditions</div>
      <div style="font-size:11px;color:#5A6878;line-height:1.85;">
        ${{!Quotes.Terms_and_Conditions}}
      </div>
    </td>
  </tr>

  <!-- ── 8. FOOTER ────────────────────────────────────────────────────────── -->
  <tr>
    <td bgcolor="#F4F6FA"
        style="padding:11px 32px;border-top:1px solid #DDE1E8;">
      <table border="0" cellspacing="0" cellpadding="0" width="100%">
        <tr>
          <td style="font-size:11px;color:#8894A8;">${{!org.company_name}}</td>
          <td align="right" style="font-size:11px;color:#8894A8;">info@aljazeeramachinery.com</td>
        </tr>
      </table>
    </td>
  </tr>

</table><!-- /DOCUMENT CARD -->
</td></tr>
</table>"""


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run",  action="store_true", help="Print payload, do not call API.")
    ap.add_argument("--replace",  action="store_true", help="Delete existing template then recreate.")
    args = ap.parse_args()

    load_dotenv(ENV_PATH)
    accounts      = os.environ.get("ZOHO_ACCOUNTS_URL", "https://accounts.zoho.com").rstrip("/")
    client_id     = os.environ.get("ZOHO_CLIENT_ID",     "").strip()
    client_secret = os.environ.get("ZOHO_CLIENT_SECRET", "").strip()
    refresh_token = os.environ.get("ZOHO_REFRESH_TOKEN", "").strip()

    if not all([client_id, client_secret, refresh_token]):
        print("Set ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET, ZOHO_REFRESH_TOKEN in tools/zoho/.env",
              file=sys.stderr)
        return 1

    logo_b64 = _logo_b64()
    html     = build_html(logo_b64)

    payload = {
        "inventory_templates": [
            {
                "name":        TEMPLATE_NAME,
                "module":      {"api_name": "Quotes"},
                "content":     html,
                "editor_mode": "rich_text",
                "category":    "normal",
                "folder":      {"id": FOLDER_ID},
            }
        ]
    }

    if args.dry_run:
        print(json.dumps({**payload["inventory_templates"][0], "content": f"<...{len(html)} chars...>"}, indent=2))
        return 0

    print("Refreshing Zoho access token...")
    try:
        access, api_domain = _get_token(accounts, client_id, client_secret, refresh_token)
    except Exception as exc:
        print(f"Token refresh failed: {exc}", file=sys.stderr)
        return 1

    hdrs = {"Authorization": f"Zoho-oauthtoken {access}", "Content-Type": "application/json"}

    # Check if template already exists
    existing_id: str | None = None
    lst = requests.get(
        f"{api_domain}/crm/v2/settings/inventory_templates",
        params={"module": "Quotes"},
        headers=hdrs,
        timeout=30,
    )
    for tpl in (lst.json().get("inventory_templates") or []):
        if tpl.get("name") == TEMPLATE_NAME:
            existing_id = tpl["id"]
            break

    if existing_id and not args.replace:
        print(f"Template '{TEMPLATE_NAME}' already exists (id={existing_id}).")
        print("Re-run with --replace to overwrite it.")
        return 0

    if existing_id and args.replace:
        print(f"Deleting existing template id={existing_id}...")
        dr = requests.delete(
            f"{api_domain}/crm/v3/settings/inventory_templates",
            params={"ids": existing_id},
            headers=hdrs,
            timeout=30,
        )
        if not dr.ok:
            print(f"Delete failed: {dr.status_code} {dr.text[:400]}", file=sys.stderr)
            return 1
        print("Deleted.")

    # Create
    print(f"Creating template '{TEMPLATE_NAME}' ...")
    r = requests.post(
        f"{api_domain}/crm/v3/settings/inventory_templates",
        headers=hdrs,
        json=payload,
        timeout=60,
    )
    data = r.json()

    results = data.get("inventory_templates") or []
    if results and results[0].get("status") == "success":
        created_id = results[0]["details"]["id"]
        print(f"\nTemplate created successfully!")
        print(f"  Name : {TEMPLATE_NAME}")
        print(f"  ID   : {created_id}")
        print(f"\nView / edit it in Zoho:")
        print(f"  Setup → Customization → Templates → Inventory → Quotes")
        return 0
    else:
        print(f"API returned HTTP {r.status_code}:", file=sys.stderr)
        print(json.dumps(data, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
