# Teamspace: Direct department

This folder holds the **declarative manifest** for the Zoho CRM Next Gen teamspace **Direct department** (core sales modules in one sidebar group).

## Create in Zoho (automation)

Zoho expects **`access_type`** as lowercase (`public` / `shared`) and each **`module_folder_mappings`** row as `{"module": {"id": "..."}}` without a `folder` object (a `folder.name` value returns “Invalid Folder” in many orgs). `provision_teamspace.py` applies that shape.

From the repo root (OAuth needs **settings** scopes such as `ZohoCRM.settings.ALL`):

```bash
make zoho-provision-teamspace-direct-department
```

Or:

```bash
cd tools/zoho
./venv/bin/python provision_teamspace.py --manifest ../../artifacts/zoho/teamspace/direct_department.json --dry-run
./venv/bin/python provision_teamspace.py --manifest ../../artifacts/zoho/teamspace/direct_department.json
```

- Set **`ZOHO_TEAMSPACE_ADMIN_ID`** in `tools/zoho/.env` if the Users API is unavailable (`ZohoCRM.users.ALL` on the refresh token).
- If POST returns **duplicate teamspace name**, delete the existing teamspace in Zoho (Setup → Teamspace) or use `DELETE /crm/v8/settings/team_spaces/{id}` with **no** `wf_trigger` query parameter (that parameter can make delete fail).

## Create in Zoho (UI)

Use this if you prefer not to run the script. Official guide: [Managing Teamspaces](https://help.zoho.com/portal/en/kb/crm-nextgen/using-crm-for-everyone/teamspaces/articles/nextgen-managing-teamspaces).

After the teamspace exists, open the main CRM view and **switch the active teamspace** to **Direct department** so the **Products** module (and the rest) appear in the sidebar.
