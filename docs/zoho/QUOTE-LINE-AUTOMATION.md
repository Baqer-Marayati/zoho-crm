# Quote line: auto-fill Machine SKU (Product only → speed → configurations)

**Goal:** Reps only pick **Product Name** on the line, then **Model / speed**, then **Configuration 1**, then **Configuration 2**. They do **not** manually set **Machine SKU** — a workflow fills it from the product’s **Product Code** and **Product Name** so the dependent picklists work.

**Why a hidden field exists:** Zoho’s dependent picklists are wired to a **parent picklist** (Machine SKU), not the Product lookup. Filling that picklist in the background keeps the same behaviour without an extra user step.

## 1) Create the Deluge function (API or UI)

**Option A — from this repo (recommended):** with a refresh token that includes **workflow** and **automation** settings scopes (e.g. `ZohoCRM.settings.ALL`), run:

```bash
cd tools/zoho
./venv/bin/python provision_quoted_line_machine_sku_workflow.py
```

Or: `make zoho-quote-line-machine-sku-wf` from the repo root.

The script loads the Deluge from  
[`../../artifacts/zoho/deluge/quoted_items_sync_machine_sku.deluge`](../../artifacts/zoho/deluge/quoted_items_sync_machine_sku.deluge)  
and uses the API to create the **workflow rule** on **Quoted_Items** (running the function when **Product Name** is not empty).

**Custom function upload:** In many orgs, `POST /crm/v8/settings/automation/functions` returns `INVALID_DATA` for the raw Deluge body (Zoho validates an internal `arguments.function` shape). If that happens, create the function **once in the CRM UI** (same name: `quoted_items_sync_machine_sku`), paste the Deluge from the file above, associate with **Quotes** (or your line module), save — then run the script again: it will **find the function by name** and create the rule. You can also pass `--function-id=<id>` from the function’s detail screen. Use `--dry-run` to print JSON only, or `--print-only` to dump Deluge and sample JSON **without** calling Zoho (e.g. when the OAuth server is rate-limiting token refresh).

**Option B — UI:**  

1. Zoho CRM → **Setup** (gear) → **Developer Space** (or **Functions** under **Developer**).
2. **Functions** → **+ New** → **Write your own**. Language: **Deluge**; associate with **CRM** if asked.
3. **Function name (example):** `quoted_items_sync_machine_sku`
4. **Return type:** `void` (or a Map if you prefer).
5. Paste the code from:  
   [`../../artifacts/zoho/deluge/quoted_items_sync_machine_sku.deluge`](../../artifacts/zoho/deluge/quoted_items_sync_machine_sku.deluge)  
6. **Save**; production use is through a rule (below).

The script: loads the **Product** from the line’s **Product Name** lookup, builds the same `Product_Code - Product_Name` string as the **Machine SKU** picklist, updates the line, and uses **`trigger: []`** so the same workflow does not loop forever.

## 2) Create the workflow (Quoted_Items)

If you already ran `provision_quoted_line_machine_sku_workflow.py`, the rule **Quoted line sync Machine SKU from product** should exist on **Quoted_Items** — confirm it is **active** in **Setup → Automation → Workflow Rules** (filter module **Quoted Items**).

**Manual setup:**

1. **Setup** → **Automation** → **Workflow Rules** (or **Actions** / **Rules** for your UI).
2. **Create rule** (or **Workflow**).
3. **Module:** **Quoted Items** (API name is often `Quoted_Items`).
4. **When:** **Create** and **Edit** (or **all records** on create / edit).
5. **Condition (optional but recommended):** **Product Name** *is not empty*.
6. **Instant action:** **Function** → choose `quoted_items_sync_machine_sku` (or the name you used).
7. **Save** and **Activate** the rule.

## 3) Rep flow (and layout)

**Order of user choices:**

1. **Product Name** (line product)
2. **Model / speed**
3. **Configuration 1**
4. **Configuration 2**

**Machine SKU** can stay on the **layout** for debugging, or you can **remove it from the “Quoted Items / Product details” form** (or move it to an **Unused** section) so only admins see it:  
**Setup** → **Customization** → **Modules** → **Quotes** (or the line item module) → **Layouts** → edit the **Quote line / Quoted Items** layout and remove **Machine SKU** from the form users see. The field is still updated by the workflow.

## 4) If Machine SKU does not set

- **Exact label:** Picklist options are built in Python with `_zoho_pick("Product_Code - Product_Name")` in `tools/zoho/provision_quoted_line_dependencies.py` (Unicode → ASCII, `&` → ` and `, restricted characters → spaces, then trim). The Deluge sample builds `code + " - " + pname` as plain text; for **ASCII** catalog names that usually **matches** the option. If the line update fails with a picklist error or the field stays empty, the CRM **Product Name** may not match the provisioned string (e.g. after renaming the product) — re-run:  
  `cd tools/zoho && ./venv/bin/python provision_quoted_line_dependencies.py`  
  so picklist options stay aligned with the catalog, or adjust **Product Name** to match the existing option.
- Check **Setup** → **Process automation** (or **Workflow logs**) for Deluge errors on that function.

## 5) Local helper (API names)

To print field **API names** for Quotes / Quoted_Items in your org:

```bash
cd tools/zoho && ./venv/bin/python dump_quoted_item_field_api_names.py
```

## Related

- [`QUOTE-LINE-EXTENSIONS.md`](./QUOTE-LINE-EXTENSIONS.md) — field roles and `provision_quoted_line_dependencies.py`
- Deluge source: [`../../artifacts/zoho/deluge/quoted_items_sync_machine_sku.deluge`](../../artifacts/zoho/deluge/quoted_items_sync_machine_sku.deluge)
