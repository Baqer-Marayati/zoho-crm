# Project status

**As of 2026-04-22** — *Update this file when direction or scope changes.*

| Item | State |
|------|--------|
| **Current direction** | Zoho CRM **Professional** for reps; **Power BI** for managers; scripts and docs in this repo |
| **Abandoned / archived** | Microsoft Canvas `.msapp` build pipeline, custom React “Option E” as primary build (see `archive/`) |
| **Next implementation steps** | (1) Zoho org + OAuth app, (2) pipeline + products + quote templates, (3) Power BI dataset/refresh, (4) optional API scripts in `tools/zoho/` |

## Scope (MVP)

- End-to-end **pipeline** from lead to **won/lost** deal
- **Quotes** with product library and attached brochures/specs; smart behavior via workflows / Deluge where needed
- **Power BI** reports published by a builder with **Pro**; managers as **viewers** (licensing: confirm with IT)
- **No** requirement that the CRM UI be pixel-identical to another product; focus on **branding** and **clarity**

## Open decisions

- Exact Zoho **edition** and add-ons (e.g. Sign) — confirm with billing
- Power BI: **Pro vs Premium (Fabric) capacity** for viewer licensing — one answer from IT
- How much **automation in repo** vs **Zoho admin UI** for the first two weeks

## Archive pointer

- `archive/legacy-approvals-microsoft-starter/` — original SharePoint + Power Automate + canvas starter
- `archive/legacy-crm-microsoft-attempt/` — Dataverse solution, Python tools, and pivot / canvas / frontend architecture notes
