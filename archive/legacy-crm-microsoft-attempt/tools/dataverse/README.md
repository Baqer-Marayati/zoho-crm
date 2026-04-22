# Dataverse Web API helper

Python scripts that talk to the Dataverse Web API to create / seed / verify
the `Opportunity` table for `scrCRM`. They use MSAL device-code auth
(no admin app registration needed).

## Setup (once)

```bash
cd tools/dataverse
python3 -m venv venv
./venv/bin/pip install --quiet --upgrade pip
./venv/bin/pip install --quiet msal requests
```

## Scripts

| Script | What it does |
|---|---|
| `create_opportunity.py` | Creates the `new_Opportunity` table + 10 custom columns + 2 choice sets, scoped to the `scrCRMDataverse` solution. Idempotent — re-running on an existing table just publishes. |
| `seed_opportunities.py` | Upserts 5 demo opportunity rows by name. Idempotent. |
| `verify_opportunity.py` | Lists the table's custom columns and confirms it's a member of the solution. |

## Auth

First run pops a device code; paste it into <https://login.microsoft.com/device>
and sign in as your environment user. The token is cached in
`.token_cache.json` (gitignored, `chmod 600`) and reused on subsequent runs
until it expires (~60 min).

## Configuration

Override via env vars before invoking:

```bash
DATAVERSE_URL=https://yourorg.crm.dynamics.com \
SOLUTION_UNIQUE_NAME=YourSolution \
PUBLISHER_PREFIX=yp \
TENANT_ID=00000000-0000-0000-0000-000000000000 \
./venv/bin/python ./create_opportunity.py
```

If your copy still contains a specific org or tenant, replace with your own
`DATAVERSE_URL` and `TENANT_ID` and **do not** commit those values in shared docs.

## Why a Python script (not the .NET SDK)?

The classic Dataverse SDK fights you over target frameworks and read-only
metadata properties. The Web API is plain HTTPS + JSON, runs anywhere
Python runs, and the OData payload structure mirrors the official
Microsoft docs 1:1.
