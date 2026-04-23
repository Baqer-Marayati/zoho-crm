# Leads → Deals — build checklist (from workshop answers)

**Captured decisions**

| Topic | Choice |
|--------|--------|
| **Next focus** | Leads, conversion, and Deals (fields + mapping) |
| **Quotes** | Important **often** — configure Products/Quotes **right after** lead–deal basics |
| **Sector** | Reps **specialize** by **Line of business** (**Production** / **MPS** / **Radiology**); **one** Deals pipeline (**Standard**) |
| **Closed Lost** | **Standard** reason set (below) |
| **Team (0–3 mo)** | **4–10** active users — use **clear roles/profiles** |

## 1. Roles / profiles (do this first — ~30 min)

You described **specialist reps**. Mirror that in Zoho so permissions and defaults stay simple.

1. **Setup → Users and Control → Security → Roles**  
   - Example: `Sales — Production`, `Sales — MPS`, `Sales Manager`, `CRM Admin`.  
   - Hierarchy only if you truly need roll-up reporting by manager.

2. **Setup → Users and Control → Security → Profiles**  
   - Tie each profile to what they may **see** and **edit** (Leads, Deals, Quotes, Products).  
   - **4–10 users:** keep **2–3 sales profiles** by line (Production / MPS / Radiology) plus manager/admin, or one profile with workflows — see [`SALES-PIPELINE-AND-STAGES.md`](./SALES-PIPELINE-AND-STAGES.md).

3. Assign each user the **role + profile** that matches their specialty.

## 2. Lead record — fields to add or confirm

**Setup → Customization → Modules and Fields → Leads**

| Purpose | Suggestion |
|---------|------------|
| **Line of business** | Picklist: `Production`, `MPS`, `Radiology` — **required before convert** (or set by layout — see §3). Same field on **Deal** for reporting (provisioned via `provision_phase2_fields.py`). |
| **Qualification** | Fit, budget, authority, need, timeline — use standard fields or a few custom picklists. |
| **Source** | Lead source (marketing, referral, event, …). |
| **Handoff** | Owner = owning rep; use **territories** only if you already use them. |

## 3. Specialist reps — how to set **sector (Line of business)**

Pick **one** pattern (simplest first):

**Option A — Lead picklist (recommended)**  
- Field **`Line_of_Business`** (or similar): `Production` | `MPS` | `Radiology`.  
- **Production** profile: use a **Lead layout** where the field **defaults to Production** (and can be read-only).  
- Repeat for **MPS** / **Radiology** layouts as needed.  
- On **convert**, map **Line of business** to the **same field on Deal** (see §4). **Pipeline** stays **Standard (Standard)** for everyone.

**Option B — Training only**  
- Single layout; rep **manually** chooses **Line of business** on Lead/Deal. Works but easier to get wrong.

## 4. Lead conversion → Deal mapping

**Setup → Customization → Modules and Fields → Leads → ** (gear / **Map Dependent Fields** / **Convert** — exact label varies by UI version) **Lead Conversion Mapping**.

- Map **Account / Contact / Deal** fields.  
- Ensure **Deal** gets: **Line of business** (mapped from Lead); **Pipeline** = **Standard (Standard)** (default); **Stage** = first open stage; **Amount** / **Closing Date** if you use them.  
- **Deal name** rule: e.g. `Account Name — Line` or `Account — Opportunity`.

Test: create a **test Lead**, fill **Line of business**, **Convert** → confirm **Deal** has correct **Line of business**, **Standard** pipeline, and **Stage 1**.

## 5. When to create a Deal (process rule)

Agreed earlier: **after first real meeting / discovery**.  
Enforce lightly at first:

- **Lead Status** must reach a value like **Qualified** or **Meeting held** before convert (workflow or manager habit).  
- Optional later: **Blueprint** on Leads.

## 6. Closed Lost — standard reasons (picklist on Deals)

**Setup → Modules and Fields → Deals** — add or use **Lost Reason** picklist. Suggested values:

1. **Price**  
2. **Timing / not now**  
3. **Competitor**  
4. **No budget / no approval**  
5. **No decision**  
6. **Product or technical fit**  
7. **Other** (with short text note field optional)

Starter CSV (copy into Zoho): [`artifacts/zoho/picklists/lost_reasons.csv`](../../artifacts/zoho/picklists/lost_reasons.csv).

Make **Lost Reason** **required** when **Stage = Closed Lost** (field dependency, validation rule, or blueprint — per your edition).

## 7. Quotes & products (next, since you use quotes often)

After lead–deal flow is stable:

1. **Products** (SKU, price, tax, attachments if needed).  
2. **Quote** layout + **Quote Stage** / linkage to **Deal**.  
3. Optional: workflow when quote is **Accepted** → move Deal stage.

## 8. Repo

- Pipeline definitions: `tools/zoho/pipelines_seed.json` + `provision_pipelines.py --sync`.  
- Update [`PROJECT-STATUS.md`](../PROJECT-STATUS.md) when conversion mapping and lost reasons are live.

## Related

- [`SALES-PIPELINE-AND-STAGES.md`](./SALES-PIPELINE-AND-STAGES.md) — unified pipeline + Line of business.  
- [`GETTING-STARTED.md`](./GETTING-STARTED.md) — org and API.
