# Zoho CRM — implementation checklist (build order)

Use this as the **single execution order** for go-live. Detail lives in linked docs; questionnaire answers are in **CONFIGURATION-ROUND3** through **ROUND8**.

## Decision snapshot (from workshops)

| Area | Summary |
|------|---------|
| Pipelines | **One** Deals pipeline — **Standard (Standard)**; sector = **Line of business** (Production \| MPS \| Radiology) |
| Leads → Deals | Specialist reps; **line first**, then assignment; **English** UI |
| Quotes | **IQD**, **one** price book v1, **line discounts**, **manual tax**, attachments **sometimes** |
| Data | **Small** import; **dup** rules email + company; **keep all**; **SharePoint** for contracts |
| Process | **No** approval v1; **no** Books v1; **no** inventory in CRM; **no** Cases v1 |
| Governance | **MFA** all users; **pilot** 2–3 reps; **weekly** pipeline review; **strict** activities; **close date** required |

---

## Phase 0 — Already done (repo + Zoho)

- [x] API OAuth + local `.env` (`tools/zoho/`, `connect_zoho.py`)
- [x] **Unified** Deals pipeline **Standard (Standard)** (`pipelines_seed.json`, `provision_pipelines.py --sync`; retired extra pipelines via transfer API where applicable)
- [x] Workshop decisions documented (rounds 3–8 + `LEADS-AND-DEALS`, `PRODUCTS-AND-QUOTES`)

---

## Phase 1 — Security & foundation (admin, ~0.5–1 day)

1. [ ] **MFA** for all CRM users — usually **[accounts.zoho.com](https://accounts.zoho.com)** (profile → MFA/OneAuth), **not** CRM Setup search — see [`CONFIGURATION-ROUND7.md`](./CONFIGURATION-ROUND7.md)
2. [ ] **Microsoft 365** email integration — [`CONFIGURATION-ROUND3.md`](./CONFIGURATION-ROUND3.md)
3. [ ] **Duplicate rules** (email + company) — [`CONFIGURATION-ROUND6.md`](./CONFIGURATION-ROUND6.md)
4. [ ] **Territories** (geography) — [`CONFIGURATION-ROUND5.md`](./CONFIGURATION-ROUND5.md); align with **line-first** assignment — [`CONFIGURATION-ROUND6.md`](./CONFIGURATION-ROUND6.md)
5. [ ] **Roles & profiles** (Production reps vs MPS vs manager vs admin) — [`LEADS-AND-DEALS.md`](./LEADS-AND-DEALS.md)
6. [ ] **Company settings**: base currency **IQD** — [`PRODUCTS-AND-QUOTES.md`](./PRODUCTS-AND-QUOTES.md)

---

## Phase 2 — Leads & Deals (admin + pilot prep, ~1–2 days)

**Solo admin:** you can skip **separate Lead layouts per profile**; use one **Line of business** picklist on Lead and Deal (**Production** / **MPS** / **Radiology**). Add **layouts by profile** when more reps join — [`LEADS-AND-DEALS.md`](./LEADS-AND-DEALS.md).

**Automate:** `make zoho-phase2-fields` then `make zoho-phase2-layouts` (or the Python scripts in [`PHASE2-AUTOMATED.md`](./PHASE2-AUTOMATED.md)) — then finish the short UI steps there.

1. [x] **Lead** picklist **Line of business** + **Deal** picklists **Lost Reason** & **Competitor** — **`provision_phase2_fields.py`**; optional **layouts by profile** — [`LEADS-AND-DEALS.md`](./LEADS-AND-DEALS.md)
2. [ ] **Lead conversion mapping** → Deal (**Pipeline**, **Stage**, key fields) — [`LEADS-AND-DEALS.md`](./LEADS-AND-DEALS.md) *(UI)*
3. [x] **Deal**: **Closing date** required — **`provision_phase2_layouts.py`** or [`CONFIGURATION-ROUND8.md`](./CONFIGURATION-ROUND8.md)
4. [x] **Deal**: **Lost Reason** + **Competitor** on **Closed Lost** (required + map dependency) — **`provision_phase2_layouts.py`**; [`LEADS-AND-DEALS.md`](./LEADS-AND-DEALS.md)  
   *Picklist values from [`artifacts/zoho/picklists/`](../../artifacts/zoho/picklists/).*
5. [x] **Stage–probability mapping** — `/settings/stages` API returns probabilities (HTTP 200); default Zoho values already loaded. To set custom values: `Setup → Pipelines → Standard (Standard) → Stage-Probability` (~2 min) — [`PHASE2-AUTOMATED.md`](./PHASE2-AUTOMATED.md) §5
6. [x] **Field history** emphasis: **Stage**, **Amount** — **`provision_phase2_tracking.py`** (`make zoho-phase2-tracking`) — Stage tracking enabled; Amount tracked as followed-field of Stage History
7. [x] **Activity** discipline (training; blueprint optional) — documented in [`PHASE2-AUTOMATED.md`](./PHASE2-AUTOMATED.md) §7

---

## Phase 3 — Products & Quotes (~1–2 days)

**Automate:** `make zoho-phase3` (or `./venv/bin/python provision_phase3.py`) for steps 1, 3, 4, 5.  
Wave A import (step 2) activates once you fill the CSV with real SKUs.

1. [x] **Single IQD price book** — **`provision_phase3.py --step 1`** — `Standard IQD` created (id=`7353692000000765001`) — [`PRODUCTS-AND-QUOTES.md`](./PRODUCTS-AND-QUOTES.md)
2. [ ] **Wave A** products import — fill [`artifacts/zoho/import/products_wave_a_template.csv`](../../artifacts/zoho/import/products_wave_a_template.csv) with real SKUs, then **`provision_phase3.py --step 2`**
3. [x] **Quote** layout: **Payment Terms** picklist (10 values, id=`7353692000000763002`) — **`provision_phase3.py --step 3`** — [`PRODUCTS-AND-QUOTES.md`](./PRODUCTS-AND-QUOTES.md)
4. [x] **Attachments** on quotes (always available) — confirmed by **`provision_phase3.py --step 4`** — standard Zoho feature, no config needed
5. [x] **SharePoint** link field(s) on Deal/Quote — **`provision_phase3.py --step 3`** — `Contract Folder URL` (text) on Deals (id=`7353692000000751007`) and Quotes (id=`7353692000000759035`)

---

## Phase 4 — Data migration (small)

1. [ ] Map your CSV columns to Zoho — template [`artifacts/zoho/import/leads_import_template.csv`](../../artifacts/zoho/import/leads_import_template.csv)
2. [ ] Test import **10 rows**, then full **&lt;500** — [`CONFIGURATION-ROUND3.md`](./CONFIGURATION-ROUND3.md)

---

## Phase 5 — Pilot & rollout

1. [ ] **Pilot** 2–3 reps (mix Production + MPS if possible) — [`CONFIGURATION-ROUND7.md`](./CONFIGURATION-ROUND7.md)
2. [ ] **Weekly** pipeline review cadence — [`CONFIGURATION-ROUND8.md`](./CONFIGURATION-ROUND8.md)
3. [ ] Roll out to full **4–10** users; gather feedback; adjust layouts

---

## Phase 6 — Later (explicitly deferred)

- **Power BI** — [`CONFIGURATION-ROUND3.md`](./CONFIGURATION-ROUND3.md), [`POWER-BI-AND-LICENSING.md`](./POWER-BI-AND-LICENSING.md)
- **Web-to-lead** — [`CONFIGURATION-ROUND4.md`](./CONFIGURATION-ROUND4.md)
- **Formal forecasting** — [`CONFIGURATION-ROUND5.md`](./CONFIGURATION-ROUND5.md)
- **Zoho Books** — [`CONFIGURATION-ROUND8.md`](./CONFIGURATION-ROUND8.md)
- **Separate Radiology pipeline** — superseded by **Line of business = Radiology**; `pipelines_seed.radiology.json` archived

---

## Related index

| Doc | Role |
|-----|------|
| [LEADS-AND-DEALS.md](./LEADS-AND-DEALS.md) | Leads, conversion, lost reasons |
| [PRODUCTS-AND-QUOTES.md](./PRODUCTS-AND-QUOTES.md) | IQD, catalog waves, quotes |
| [SALES-PIPELINE-AND-STAGES.md](./SALES-PIPELINE-AND-STAGES.md) | Unified pipeline + Line of business |
| [CONFIGURATION-ROUND3.md](./CONFIGURATION-ROUND3.md) … [ROUND8.md](./CONFIGURATION-ROUND8.md) | Workshop detail |
| [../PROJECT-STATUS.md](../PROJECT-STATUS.md) | Repo status line |

Update **`PROJECT-STATUS.md`** when a **phase** completes.
