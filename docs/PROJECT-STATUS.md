# Project status

**As of 2026-04-22** — *Update when direction or scope changes.*

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

1. Zoho org + API Console app + refresh token (local `.env` only)  
2. End-to-end pipeline and quote templates in Zoho  
3. Power BI dataset + refresh  
4. Add scripts in `tools/zoho/` for anything repetitive (bulk import, health checks)
