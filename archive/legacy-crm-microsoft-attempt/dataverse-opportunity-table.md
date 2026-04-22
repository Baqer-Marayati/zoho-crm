# Dataverse: create the `Opportunity` table

> **Update — automated.** This is now a one-command script. The earlier manual maker-portal walkthrough is preserved at the bottom for reference, but you don't need it.

## TL;DR — run two scripts

```bash
# 1. Create the table + columns + choice sets, scoped to scrCRMDataverse solution
./tools/dataverse/venv/bin/python ./tools/dataverse/create_opportunity.py

# 2. (optional) Seed 5 demo rows so the wired app shows real data immediately
./tools/dataverse/venv/bin/python ./tools/dataverse/seed_opportunities.py

# 3. Verify
./tools/dataverse/venv/bin/python ./tools/dataverse/verify_opportunity.py
```

The first script asks you to sign in once via device code (paste the code into <https://login.microsoft.com/device>); subsequent runs reuse the cached token.

When it finishes, head to **`docs/wire-scrcrm-to-dataverse.md`** to point the canvas app at the new table.

---

## What the script creates

Custom table under publisher prefix `new_`, scoped to the `scrCRMDataverse` solution:

| Column (display) | Type | Notes |
|---|---|---|
| `Name` | text(200) | primary name |
| `Stage` | choice (local) | `Discovery`, `Qualify`, `Proposal`, `Negotiation`, `Commit`, `Closed Won`, `Closed Lost` |
| `Track` | choice (local) | `Industrial`, `Software`, `Service`, `Aftermarket` |
| `Amount` | currency | + auto `Amount (Base)` |
| `Reporting Amount` | currency | + auto `Reporting Amount (Base)` |
| `Close Date` | date-only | required |
| `Probability` | int 0–100 | |
| `Rolling Summary` | multiline text(4000) | |
| `Competitors` | multiline text(4000) | |
| `Owner Name` | text(200) | custom string column (separate from the system Owner lookup, which also exists) |

Plus all standard system columns (`createdon`, `modifiedon`, `statecode`, `Owner` lookup, …).

The script is **idempotent**: if the table already exists it just publishes and exits.

---

## Tweaking the script

The script is in [`tools/dataverse/create_opportunity.py`](../tools/dataverse/create_opportunity.py). Each column type has a tiny helper (`_string`, `_picklist`, `_money`, `_date`, `_integer`, `_memo`); add another column by appending one entry to the `attributes` list inside `build_entity_payload()`.

Environment variables you can override:

| Var | Default | Purpose |
|---|---|---|
| `DATAVERSE_URL` | `https://org05dfdf92.crm4.dynamics.com` | Target environment |
| `TENANT_ID` | `53ea674b-813e-46a3-9961-f0b04a117e08` | Entra tenant for device-code auth |
| `SOLUTION_UNIQUE_NAME` | `scrCRMDataverse` | Solution to add components to (must already exist) |
| `PUBLISHER_PREFIX` | `new` | Publisher prefix for new schema names |
| `CLIENT_ID` | Azure CLI public client | Override only if you provisioned your own app reg |

---

## Reference: legacy manual flow

> Keep this only if you ever need to bootstrap a fresh environment without the script.

### 1. Open the maker portal

Go to <https://make.powerapps.com>, top-right **Environment** picker → choose your dev env, left rail → **Tables**.

### 2. New table

**+ New table → Set advanced properties**:
- Display name: `Opportunity`
- Plural display name: `Opportunities`
- Primary column display name: `Name`

### 3. Add columns (matching the table above)

For each column, **+ New column**, set type, save. Use the column list in the section above.

### 4. Choice option labels

When creating each Choice column, on the right panel pick **+ New choice** and add the labels (in order) listed above.

### 5. Sample rows

**Data → + New row**, repeat 3–5 times. Or just run `seed_opportunities.py` — it works even if you created the table manually, as long as the schema names match (`new_name`, `new_stage`, etc.).
