# Power BI, Zoho, and licensing (practical)

This is not legal or licensing advice. Confirm with **Microsoft** and your **IT** for your tenant.

## Roles in your scenario

| Role | Typical need |
|------|------------------|
| **You (report builder)** | Power BI **Desktop** (free) to **author**; a license that can **publish** to a workspace — often **Power BI Pro** (or PPU) |
| **Managers (view only)** | Ability to open **shared** or **app** content in the Power BI service. Whether they need **Pro** or can use a **Free** user depends on **where** the content is hosted (shared capacity vs **Premium** / **Fabric** capacity) |
| **Reps (CRM only)** | **Zoho CRM** seat; no Power BI required if they do not open reports in the service |

Zoho and Power BI are **separate** subscriptions. Connecting them does **not** add a per-user Zoho fee for managers who never log into Zoho.

## “Who pays for what”

- **Zoho:** paid per CRM user (reps, admins) as per your Zoho plan.
- **Power BI:** Microsoft bills per the SKUs you assign (Pro, PPU, Premium capacity, etc.).
- **Integration:** the **API** and Power Query work do not have a special “Zoho + Power BI connector tax” in the simple REST setup; the cost is your **time** and **infrastructure** (scheduled refresh, gateways only if you use on-prem data).

## Zoho as data source

Options depend on your architecture:

- **Custom connector / Power Query** against Zoho’s **REST** API (scriptable from this repo’s credentials pattern).
- Other patterns your organization prefers (e.g. extract to a warehouse) — out of scope until you choose one.

**Refresh:** configure in the Power BI service; ensure the **credential** used for refresh is allowed (often a service Zoho user or a dedicated connection).

## Action for IT (one message)

> “We will publish Zoho-sourced reports to the Power BI service. For **N** report viewers, do they need **Power BI Pro** or does **Premium / Fabric** capacity on the workspace allow **Free** viewers? Which workspace should we use?”

Record the answer in `../PROJECT-STATUS.md` so the team does not re-litigate it later.
