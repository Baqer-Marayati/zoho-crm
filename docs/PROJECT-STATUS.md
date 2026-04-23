# Project status

**As of 2026-04-23** — *Update when direction or scope changes.*

| Item | State |
|------|--------|
| **Stack** | Zoho CRM **Professional** (reps); **Power BI** (management reporting); this repo = docs + `tools/zoho` scripts |
| **Source of truth** | Zoho org configuration and live data; Power BI published datasets — **not** fully reproducible from Git alone |

## MVP scope

- **Pipeline:** lead through deal, won/lost
- **Quotes** with product library and file attachments; workflows / Deluge as needed
- **Power BI** models/reports (builder licenses per org policy; managers as viewers as per IT)

## Open decisions

- Zoho **edition** and add-ons (e.g. Sign)
- Power BI: **Pro vs Premium/Fabric** for viewers — one answer from IT
- Balance: **Zoho admin UI** vs **API scripts in `tools/zoho`**

## Next steps

**Primary build path:** [`docs/zoho/IMPLEMENTATION-CHECKLIST.md`](./zoho/IMPLEMENTATION-CHECKLIST.md) (phased checklist + links to all workshop docs). Picklist/import starters: [`artifacts/zoho/picklists/`](../artifacts/zoho/picklists/), [`artifacts/zoho/import/`](../artifacts/zoho/import/).

1. ~~Zoho org + API Console app + refresh token (local `.env` only)~~ **Done (2026-04-23)** — `tools/zoho/zoho_ping.py`; tokens in `tools/zoho/.env` only.  
2. ~~**Unified Deals pipeline**~~ **Done (2026-04-23)** — single **Standard (Standard)** pipeline; sector via **Line of business** (Production \| MPS \| Radiology) on Lead + Deal; `pipelines_seed.json` + `provision_pipelines.py --sync`; legacy **Production** / **MPS** pipelines retired via Zoho **transfer-and-delete** API where applicable.  
3. ~~**Phase 2 Leads & Deals** fields + layouts~~ **Done (2026-04-23)** — picklists (`provision_phase2_fields.py`), Closing Date + map dependencies (`provision_phase2_layouts.py`), field history tracking (`provision_phase2_tracking.py`). One manual UI step: **stage–probability** per pipeline (~2 min, Setup → Pipelines).  
4. ~~**Phase 3 Products & Quotes** (price book + fields)~~ **Done (2026-04-23)** — `provision_phase3.py`: IQD price book, Payment Terms picklist on Quotes, Contract Folder URL on Deals + Quotes. **Pending**: Wave A CSV needs real SKUs → then `provision_phase3.py --step 2`.  
5. **Next:** Phase 1 security (MFA, M365, dup rules, territories, roles), then Phase 4 data import, then Phase 5 pilot. Follow **[IMPLEMENTATION-CHECKLIST.md](./zoho/IMPLEMENTATION-CHECKLIST.md)**.  
6. **Power BI:** later — [`POWER-BI-AND-LICENSING.md`](./zoho/POWER-BI-AND-LICENSING.md).
