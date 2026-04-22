# Getting started with Zoho CRM in this project

## 1. Create or use a Zoho CRM org

- Sign up for **Zoho CRM** (start with a **Professional** trial or paid seats for reps, as per your plan).
- Decide a **naming pattern** for pipelines, deal stages, and product categories before bulk loading data.

## 2. Register an API (OAuth) client (for `tools/zoho` scripts)

Zoho’s CRM API uses **OAuth 2.0** (not a long-lived “API key” in the old sense for full access). Typical pattern:

1. In [Zoho API Console](https://api-console.zoho.com/) create a **Self Client** or **Server-based** app as documented for your region and product.
2. Create scopes for **Zoho CRM** (e.g. `ZohoCRM.modules.ALL` or the minimal scopes you need — tighten in production).
3. Complete the **one-time** grant to obtain a **refresh token**; store it in `.env` on your machine (see `../../tools/zoho/.env.example`).
4. Never commit tokens or client secrets. Rotate if any secret was pasted into chat or a public log.

*Exact menu names can change; follow the official Zoho CRM API authentication guide for your data center (`.com` vs `.eu` vs others).*

## 3. Configure the business in Zoho (mostly UI)

- **Pipelines and stages** for lead → deal → won/lost.
- **Modules** and fields to match your process (and any custom modules your edition allows).
- **Products** with file attachments (brochures, spec sheets) as needed.
- **Quotes** (templates, tax/shipping, PDF layout) and workflows / Deluge for “smart” behavior.
- **Roles and profiles** so reps and admins see the right data.

This repo can hold **field lists, Deluge copies, and checklists**; the system of record for configuration is still Zoho for many objects.

## 4. Power BI (separate, linked by data)

- In **Power BI Desktop** (on Windows, or a VM) connect to Zoho’s data either via the **Zoho API** in Power Query or another supported path your team approves.
- **Publish** to the Power BI service. Confirm **who needs Pro vs** Premium with IT (see [POWER-BI-AND-LICENSING.md](./POWER-BI-AND-LICENSING.md)).

## 5. This repository

- Add scripts under `tools/zoho/`.
- Update `../PROJECT-STATUS.md` when a milestone is done or scope shifts.

## Related

- [REPO-BASED-DEVELOPMENT.md](./REPO-BASED-DEVELOPMENT.md) — how much is “in Git” vs in the product.
- [ARCHITECTURE-AND-INTEGRATIONS.md](./ARCHITECTURE-AND-INTEGRATIONS.md) — end-to-end picture.
