# Twenty-inspired CRM on Power Apps (blueprint)

This document translates patterns from the open-source CRM **[Twenty](https://github.com/twentyhq/twenty)** (React + NestJS + PostgreSQL, metadata-driven objects) into a **Microsoft-native** design: **Canvas Power App** + **Dataverse** + **Power Automate** + **Power BI**. It is a build guide, not a feature-for-feature clone—Twenty’s **dynamic data model**, **command palette**, and **server runtime** cannot be reproduced literally in Canvas.

## What we observed in Twenty’s code

- **Core business objects** are expressed as standard metadata (see `CoreObjectNameSingular` in `twenty-shared`): e.g. `company`, `person`, `opportunity`, `task`, `note`, `activity`, `attachment`, plus messaging/workflow objects.
- The front end is built around **record index** (table/board views per object) and **record show** (single-record workspace)—see `RecordIndexContext`, `RecordShowPage` under `twenty-front`.
- **Extensibility** is “objects as code” and workflows in their stack—not something Power Apps copies directly; we mirror the **outcome**: entities, views, and automation in Dataverse and cloud flows.

## Parity: what to replicate vs defer

| Twenty concept | Power Apps + Dataverse equivalent | v1 scope |
|----------------|-------------------------------------|----------|
| Object list + grid (“Record index”) | Gallery or **experimental** grid connected to Dataverse | Yes — Opportunities first, then Companies/Contacts |
| Record detail (“Record show”) | Form + related subgalleries (activities, products, notes) | Yes |
| Multiple views / filters | **Views** in Dataverse + `Filter` formula or view picker | Yes |
| Command-K palette | Search box + **Navigate** buttons; or **Copilot** later | Optional |
| Attachments morph model | **SharePoint** folder per record + link column (your round-4 choice) | Yes |
| Notes + timeline | Dated **activities** + **notes** table; summary field on Opportunity | Yes |
| Matrix security (region × product) | Business units, **teams**, column security where needed | Design early; implement in phases |
| AI agents | Power Platform Copilot / external | Later |

## Dataverse model (aligns with your discovery workshops)

Use **out-of-the-box** tables where possible (`Account`, `Contact`, `Lead`, `Opportunity`, `Opportunity Product`, `Activity` / `Task`, `Phone Call`, `Appointment` as needed). **Custom** additions:

- **Product line / pipeline track** — choice column on `Opportunity` or related **Pipeline** table; drives **stage** choice (same labels across lines, filtered per line—matches your round-5 choice).
- **Forecast category** — choice: Commit / Upside / Stretch (or your labels).
- **Reporting amount** — currency for mixed-currency exceptions vs **transaction currency**.
- **Opportunity summary** — multiline text (rolling “current situation”).
- **Competitors** — intersection (many-to-many) with a **Competitor** table or multi-select **Choices** if you accept reporting limits.
- **Weekly pipeline snapshot** — custom table keyed by week + owner + track for trend charts.
- **Quota** — custom **Target** table (period, owner, team, amount).

**Company** in Twenty maps to **Account**; **Person** to **Contact**.

## Canvas app structure (Twenty-like navigation)

Use a **narrow layout** similar to Twenty’s shell:

1. **`scrHub`** — Quick actions: *New lead*, *New opportunity*, links to **Power BI** app/report, settings (admin).
2. **`scrIndex`** — Single reusable screen with **context variable** `varEntity` (`"opportunity"`, `"account"`, …). **Gallery** (table style) bound to a **collection** filled by `LookUp`/`Filter` or **data source** per entity. Top bar: search, view selector, **+** button.
3. **`scrRecord`** — Context `varEntity`, `varRecordId`. Main **form** (edit or view). **Tabs** (horizontal container): *Overview*, *Products*, *Activities*, *Notes*, *Files* (deep link to SharePoint folder).
4. **`scrLeadConvert`** — Placeholder until workshop lands rules (round 5: workshop TBD).

**UX details that read “modern” without custom code:**

- Light theme, 8px spacing grid, rounded cards, **icon** column for type.
- **Header**: `User().FullName` + environment badge.
- **Stage** control: **Slider or** dropdown filtered by `Pipeline Track`.

## Power Fx patterns (stubs)

**Navigate from index to record (example):**

```powerapps
Navigate(
    scrRecord,
    ScreenTransition.Fade,
    {
        varEntity: "opportunity",
        varRecordId: ThisItem.OpportunityId
    }
)
```

**Filter opportunities by product line (same stage names, different meaning):**

```powerapps
Filter(
    Opportunities,
    PipelineTrack = drpPipelineTrack.Selected.Value,
    Or(
        IsBlank(txtSearch.Text),
        StartsWith(Name, txtSearch.Text)
    )
)
```

**Related activities (same screen):**

```powerapps
Filter(
    Activities,
    RegardingObjectId = varRecordId
)
```

## Automation (replaces part of Twenty’s server logic)

- **On opportunity create / stage change** — Power Automate: optional Teams post to owner’s manager; log to **snapshot** table weekly via **scheduled flow**, not per save (volume control).
- **SharePoint folder** — Flow: when Opportunity created, create folder in dedicated CRM site library, write **Document link** URL back to Opportunity.

## Security

- Enforce **matrix** rules with **teams** and **user role assignments**; prove one test user per matrix cell in a test plan before go-live.
- **Delete**: only admin security role (your round-4 choice); others close as Lost or deactivate.

## What not to attempt in Canvas v1

- Full **metadata designer** inside the app (building new entities from UI).
- **Real-time** email/thread sync like a mail client—that is Outlook + Dynamics sync territory.
- Replacing **Power BI** with in-app charts for executive KPIs—embed **Power BI** tiles or link out (your “balanced dashboard” requirement).

## Next implementation steps in Power Platform

1. Create / extend Dataverse tables and relationships; configure security roles and teams for the matrix.
2. Import **starting views** (My Open Opportunities, By Stage, By Owner).
3. Build **`scrIndex`** + **`scrRecord`** for **Opportunity** only; add Account/Contact/Lead next.
4. Add **Power Automate** flows for SharePoint folder + weekly snapshot.
5. Wire **Power BI** dataset to Dataverse; validate **forecast category** and **reporting amount** in DAX.

## Reference clone (local only)

A shallow clone of Twenty for study lives under `_reference/twenty` (ignored by git in this repo). Remove it anytime to save disk space; upstream source remains [github.com/twentyhq/twenty](https://github.com/twentyhq/twenty).
