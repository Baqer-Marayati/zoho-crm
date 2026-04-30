# Sales pipeline and deal stages — agree, then configure Zoho

Use this in a **short workshop** (whoever owns sales + whoever administers CRM). After decisions are written down, one person implements them in Zoho (usually under an hour for a first version).

## 1. Decisions to agree (before clicking in Zoho)

Answer these on paper or in a doc; they drive everything else.

| # | Question | Your answer |
|---|----------|-------------|
| 1 | **One pipeline or several?** | **One unified pipeline** — **Standard (Standard)** on Deals. **Sector** = **Line of business** picklist (**Production \| MPS \| Radiology**) on Lead and Deal — filter in CRM views and Power BI slicers. |
| 2 | **Definition of a Deal:** When do we **create** a deal? (e.g. after qualified meeting, after quote sent) | |
| 3 | **Definition of Won:** What must be true? (PO received, payment, delivery?) | |
| 4 | **Definition of Lost:** Reason codes you care about (price, timing, competitor, no budget) | |
| 5 | **Handoffs:** Who moves the stage—rep only, manager approval, finance? | |
| 6 | **Forecast:** Which stages count as “commit” vs “best case” for reporting? | |

Keep **stage names short and in plain language** your team will actually say on calls.

**Also agreed (workshop, 2026-04-23):** create a **Deal** after the **first real meeting / discovery**; **Closed Lost** requires a **lost reason**; **~6–8 stages** (plus closed outcomes); **deal owner** may set **Closed Won**.

## 2. Unified pipeline + sector (current model)

| Concept | Implementation |
|---------|----------------|
| **Pipeline** | **Standard (Standard)** — default Zoho Deals pipeline; one ordered stage path for all sectors. |
| **Sector / line** | **Line of business** picklist on **Lead** and **Deal**: **Production**, **MPS**, **Radiology** (see [`artifacts/zoho/picklists/line_of_business.csv`](../../artifacts/zoho/picklists/line_of_business.csv)). |
| **Reporting** | CRM list views, dashboards, and **Power BI** — slice/filter by **Line of business**. |
| **Rep scope** | Optional: profiles + workflows so a rep’s **Line of business** defaults or is validated against a **User** field (see workshop notes). |

**Stage order** (versioned in [`tools/zoho/pipelines_seed.json`](../../tools/zoho/pipelines_seed.json)) — **7 stages**: short names for reps; **Quote Sent** means a **formal customer quotation/PDF** has been sent.

1. Qualification  
2. Needs Analysis  
3. Solution / Value
4. Quote Sent
5. Negotiation
6. Closed Won  
7. Closed Lost  

**Competitive losses** use **Closed Lost** plus **Competitor** and **Lost Reason** (no separate stage). After edits to the seed file, run **`provision_deal_stage_picklist.py`** (PATCHes the **Standard Deals layout** so Stage **pick_list_values** include only the active seed stages, in order; omitted values like **Identify Decision Makers** move to Unused and disappear from Stage View), then **`provision_pipelines.py --sync`**, then **`provision_phase2_layouts.py`** to refresh Stage → Lost Reason / Competitor maps (requires settings OAuth scopes).

### Stage reminders (so reps don’t forget to update)

Keep **few stages** *and* nudge behavior:

1. **Weekly pipeline review** (already in your checklist) — manager asks “what moved this week?” and fixes stale stages.  
2. **Zoho workflow (recommended):** **Setup → Automation → Workflow Rules** on **Deals** — e.g. *when* **Stage** is unchanged for **N days** (or **Modified Time** / last activity), **send email** to owner or **create Task** “Review deal stage.” Add one rule per critical open stage if you want tighter nudges.  
3. **Training:** “After every customer meeting, update Stage or log an activity the same day.”

Deluge timing rules vary by edition; start with **7-day** inactivity on open stages and tune down if noisy.

### 2.1 Retiring extra pipelines (Production / MPS) in Zoho

If you previously had **separate pipelines** per line, Zoho does not allow a simple HTTP DELETE. Use **Transfer and Delete** so deals move to **Standard (Standard)**:

- **API:** `POST /crm/v8/settings/pipeline/actions/transfer?layout_id={layout_id}`  
- **Docs:** [Transfer and Delete a Pipeline (v8)](https://www.zoho.com/crm/developer/docs/api/v8/transfer-and-delete-pipeline.html)  
- Map each **stage** in the old pipeline to the **same** stage ID in **Standard** (identity mapping) when both use the same Deals **Stage** picklist.

### 2.2 Archived: `archive/pipelines_seed.radiology.json`

A separate **Radiology** pipeline is **not** required when sectors are modeled with **Line of business**. The file lives at [`../../tools/zoho/archive/pipelines_seed.radiology.json`](../../tools/zoho/archive/pipelines_seed.radiology.json) (historical reference only; use `provision_pipelines.py --seed` from `tools/zoho` if you ever reintroduce a split).

Set **probabilities** and **forecast categories** per stage in **Deals → layout → Stage–probability mapping** once stage names are final.

## 3. Example stage model (adapt or replace)

Use this as a **starting template** if you don’t already have a list.

| Order | Stage (example name) | Typical probability | Notes |
|------:|----------------------|--------------------|--------|
| 1 | Qualification | 10% | Fit, budget, decision maker |
| 2 | Discovery / needs analysis | 20% | |
| 3 | Proposal / quote sent | 50% | |
| 4 | Negotiation | 70% | |
| 5 | Verbal commit | 90% | Optional; skip if you don’t use it |
| 6 | Closed Won | 100% | Align with your “Won” definition |
| 7 | Closed Lost | 0% | Use **lost reason** on the deal |

Probabilities are for **forecasting**; Zoho can map stages to **forecast categories** (Pipeline / Best Case / Commit / Closed). Tune percentages to how *your* company forecasts.

## 4. Implement in Zoho CRM (admin)

Paths can vary slightly by edition and UI; if a menu name differs, use **Setup search** (gear icon) for “Pipelines” or “Deals”.

### 4.0 Automated option (this repository)

You can **create or update** the **Standard (Standard)** pipeline from [`tools/zoho/pipelines_seed.json`](../../tools/zoho/pipelines_seed.json) using the Zoho CRM **v8 Settings API**:

1. In [Zoho API Console](https://api-console.zoho.com/), **Generate Code** for your Self Client with scope **`ZohoCRM.settings.ALL`** (or at minimum layouts + pipeline READ/CREATE/UPDATE). Exchange for a **new** refresh token and set `ZOHO_REFRESH_TOKEN` in `tools/zoho/.env`.
2. Ensure every **stage name** in the seed file exists on **Deals → Stage** in Zoho (same spelling as in the UI). If your org uses different labels, edit `pipelines_seed.json` to match exactly.
3. From the repo:  
   - First time / new names only: `make zoho-provision-pipelines` or `./venv/bin/python provision_pipelines.py`  
   - **After changing `pipelines_seed.json`:** `./venv/bin/python provision_pipelines.py --sync` (or `make zoho-sync-pipelines`)  
   Use `--dry-run` first if you want a preview.

**Limits:** Zoho ties pipeline stages to existing **Stage** picklist option IDs. Brand‑new stage *labels* must be added once in **Modules and Fields**. Probability / forecast mapping and **required Lost Reason** are still configured in the UI (or follow-up APIs).

### 4.1 Create or edit pipelines and stages (manual)

1. Sign in as a **CRM admin**.
2. **Setup** (gear) → **Customization** → **Pipelines** (or search **Pipelines** in Setup).
3. Confirm **Standard (Standard)** is the **default** pipeline and stage order matches your agreement.
4. Set **probability** per stage where the UI allows (or use stage–probability mapping below).

Official overview: [Zoho — customize deal stage / pipeline tips](https://www.zoho.com/crm/resources/tips/customize-deal-stage-field.html).

### 4.2 Stage probability and forecast behavior

1. **Setup** → **Customization** → **Modules and Fields** → **Deals** → open the **Layout** you use (often “Standard”).
2. In the layout editor, open **Settings** (or equivalent) → **Stage–Probability Mapping** (wording may be “Stage Probability”).
3. Align **percentages** and **forecast category** (if shown) with what leadership expects in reports.

### 4.3 Access: who can change stages

1. **Setup** → **Security Control** → **Profiles** (and **Roles and Sharing** if you use hierarchy).
2. Confirm sales roles can **edit** Deals and the **Stage** field; restrict if only managers may close won/lost.

If **Pipelines** is missing: **Setup** → **Customization** → **Modules and Fields** → **Organize Modules** — ensure **Deals** is enabled. See [Zoho troubleshooting — pipelines](https://help.zoho.com/portal/en/kb/crm/troubleshooting-tips/articles/troubleshooting-pipelines).

## 5. After stages exist (quick checks)

- Create a **test Deal**, walk it through **each stage**, then **Closed Won** and **Closed Lost** (with a lost reason).
- Open a **pipeline** or **stage** report/dashboard and confirm numbers move as expected.
- Agree a **rule** with the team: *deals must be in the correct stage by end of week* (or whatever cadence you use).

## 6. How this repo fits

- **Source of truth** for stages is still **Zoho** once you save the pipeline.
- Optionally export or screenshot your final stage list into `artifacts/zoho/` (no secrets) so Git records *what* you agreed, not customer data.

## Related

- [PROJECT-STATUS.md](../PROJECT-STATUS.md) — update when pipeline v1 is live.
- [GETTING-STARTED.md](./GETTING-STARTED.md) — org and API; optional for pipeline work.
