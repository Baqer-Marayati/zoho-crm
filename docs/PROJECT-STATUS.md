# Project status

**As of 2026-04-29** — *Update when direction or scope changes.*

| Item | State |
|------|--------|
| **Stack** | Zoho CRM **Professional** (reps); **Power BI** (management reporting); this repo = docs + `tools/zoho` scripts |
| **Source of truth** | Zoho org configuration and live data; Power BI published datasets — **not** fully reproducible from Git alone |
| **Quote PDF (Aljazeera Quotation)** | **Standardized 2026-04** — HTML in `tools/zoho/provision_quote_template.py`; design rules in [`docs/zoho/QUOTE-TEMPLATE-LEARNINGS.md`](./zoho/QUOTE-TEMPLATE-LEARNINGS.md); `make zoho-quote-template-replace` to push. **2026-04-26:** “SALES QUOTATION” title nudged lower (spacer 72px) and republished to Zoho. |

## MVP scope

- **Pipeline:** lead through deal, won/lost
- **Quotes** with product library and file attachments; workflows / Deluge as needed
- **Power BI** models/reports (builder licenses per org policy; managers as viewers as per IT)

## Open decisions

- Zoho **edition** and add-ons (e.g. Sign)
- Power BI: **Pro vs Premium/Fabric** for viewers — one answer from IT
- Optional **Blueprint** process graph on Deals (**Setup → Process Management → Blueprint**) — not required while server-side workflow rollback rules cover the current Proposal / Quote gate (`docs/zoho/DEALS-QUOTES-PROCESS-PROVISIONING.md`)

## Next steps

**Primary build path:** [`docs/zoho/IMPLEMENTATION-CHECKLIST.md`](./zoho/IMPLEMENTATION-CHECKLIST.md) (phased checklist + links to all workshop docs). Picklist/import starters: [`artifacts/zoho/picklists/`](../artifacts/zoho/picklists/), [`artifacts/zoho/import/`](../artifacts/zoho/import/).

1. ~~Zoho org + API Console app + refresh token (local `.env` only)~~ **Done (2026-04-23)** — `tools/zoho/zoho_ping.py`; tokens in `tools/zoho/.env` only.  
2. ~~**Unified Deals pipeline**~~ **Done (2026-04-23)** — single **Standard (Standard)** pipeline; sector via **Line of business** (Production \| MPS \| Radiology) on Lead + Deal; `pipelines_seed.json` + `provision_pipelines.py --sync`; legacy **Production** / **MPS** pipelines retired via Zoho **transfer-and-delete** API where applicable.  
3. ~~**Phase 2 Leads & Deals** fields + layouts~~ **Done (2026-04-23)** — picklists (`provision_phase2_fields.py`), Closing Date + map dependencies (`provision_phase2_layouts.py`), field history tracking (`provision_phase2_tracking.py`). **Lead → Deal conversion mapping** checked via API (`audit_lead_conversion_mapping.py`): **Line of business** copies to Deal; optional: map **Company** → **Potential Name** if you want that automated. Remaining optional UI: **stage–probability** per pipeline (~2 min, Setup → Pipelines).  
4. ~~**Phase 3 Products & Quotes** (price book + fields)~~ **Done (2026-04-23)** — `provision_phase3.py`: IQD price book, Payment Terms picklist on Quotes, Contract Folder URL on Deals + Quotes. **Pending**: Wave A CSV needs real SKUs → then `provision_phase3.py --step 2` (or `make zoho-phase3-products`).  
5. **Next (before users):** **Phase 3** Wave A product import (real SKUs in CSV → `provision_phase3.py --step 2` or `make zoho-phase3-products`), **Phase 4** lead import — see **[IMPLEMENTATION-CHECKLIST.md](./zoho/IMPLEMENTATION-CHECKLIST.md)**. ~~**Deals + Quotes sales process**~~ **Done (2026-04-29)** — workflows + Deluge via **`make zoho-deals-quotes-process`** — [`DEALS-QUOTES-PROCESS-PROVISIONING.md`](./zoho/DEALS-QUOTES-PROCESS-PROVISIONING.md). **Phase 1** (MFA, M365, dup rules, territories, roles, IQD company settings) runs **last**, immediately **before** purchasing licenses and assigning users; then **Phase 5** pilot.  
6. **Power BI:** later — [`POWER-BI-AND-LICENSING.md`](./zoho/POWER-BI-AND-LICENSING.md).
