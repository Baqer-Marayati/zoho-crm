# Quote line: model, configuration, and product-scoped picklists

**Goal:** On each quote line, sales chooses **Model / speed** and two **Configuration** fields whose **allowed values depend on the selected machine** (product). Zoho’s standard **Product** lookup cannot drive dependent picklists via the map-dependency API, so we use a companion field **Machine SKU** (same value as the product’s **Product Code**).

## 1. Fields on Quoted Items (line items)

| Label (UI) | Role |
|------------|------|
| **Machine SKU** | Parent picklist. Each option is **`Product_Code - Product_Name`** (ASCII-normalized by `tools/zoho/provision_quoted_line_dependencies.py`, same as the picklist build). Drives the other three fields. In normal use, a **Deluge + workflow** sets this from the line’s **Product Name**; reps do not pick it manually. See [`QUOTE-LINE-AUTOMATION.md`](./QUOTE-LINE-AUTOMATION.md). |
| **Model / speed** | Dependent on Machine SKU — e.g. C3935i (35 ppm) vs C3922i (22 ppm) for the C3900 series. |
| **Configuration 1** | Formerly “Finisher (line)”. Dependent on Machine SKU — finishers/stackers that apply to that catalog code. |
| **Configuration 2** | Formerly “POD / paper module (line)”. Dependent on Machine SKU — paper / POD / media options for that code. |

Internal **API names** may still look like `Finisher_line` / `POD_paper_module_line` after a label rename; merge fields and PDF templates should use **labels**.

## 2. Data in this repo

| Artifact | Purpose |
|----------|---------|
| [`../artifacts/zoho/product_extensions/extensions_by_product_code.json`](../artifacts/zoho/product_extensions/extensions_by_product_code.json) | Per **Product_Code**, allowed **Configuration 1** (finishers) and **Configuration 2** (POD/paper) text. |
| `tools/zoho/provision_quoted_line_dependencies.py` | Builds **Model / speed** options (plus defaults in-script for common multi-speed families), merges picklist options, and **Map dependency** (Machine SKU → the three children). |

## 3. Provisioning (picklists + map dependency)

```bash
cd tools/zoho
./venv/bin/python provision_quote_line_extensions.py --products-only
./venv/bin/python provision_quoted_line_dependencies.py --dry-run
./venv/bin/python provision_quoted_line_dependencies.py
```

Or from the repo root:

```bash
make zoho-quoted-line-deps
```

**OAuth:** `ZohoCRM.settings.fields.UPDATE` (or `ZohoCRM.settings.fields.ALL`) and `ZohoCRM.settings.map_dependency.CREATE` (or `.ALL`) in addition to your existing CRM scopes. If the API returns `OAUTH_SCOPE_MISMATCH`, create a new refresh token with the extra scopes.

**Layout (optional):** In **Setup → Quotes → (Line items / Quoted items) layout**, order fields as **Product Name** (or “Product Name — Line”) → **Model / speed** → **Configuration 1** → **Configuration 2**; move **Machine SKU** out of the main flow or to **Unused** if the workflow in [`QUOTE-LINE-AUTOMATION.md`](./QUOTE-LINE-AUTOMATION.md) fills it in the background.

## 4. Rep workflow (intended)

1. **Product name** on the line (catalog / lookup).  
2. **Model / speed** (options filtered to that machine).  
3. **Configuration 1** and **Configuration 2** (options filtered to that machine).  
4. **Machine SKU** is **not** a manual step when the Zoho function + rule in [`QUOTE-LINE-AUTOMATION.md`](./QUOTE-LINE-AUTOMATION.md) are active.

## 5. Troubleshooting: “Machine SKU is set but Model / speed / Config stay empty or only show - None -”

**What’s going on:** Zoho’s **map dependency** uses the **parent Machine SKU** option to decide which child picklist values are allowed. The provisioning script matches each product code to a **canonical** label: `Product_Code` + ` - ` + product name, then ASCII-normalized (`_zoho_pick` in `provision_quoted_line_dependencies.py`).

- If the **label** in Zoho for that row uses a different dash (e.g. **em dash** `—` instead of ` - `) or a different product name, the old logic could not find a match and would map **only** `- None -` to the children — so **Model / speed** and **Configuration 1/2** look empty.

**Fix (repo + re-run):**

1. Re-run picklists + map dependency so **Machine SKU** and **Model / speed** option lists are merged from this repo, and mapping uses the improved **label matching** (exact, normalized, and product-code prefix):  
   `make zoho-quoted-line-deps` (or `provision_quoted_line_dependencies.py` without `--dry-run`).

2. On the quote line, set **Product** (lookup) first, then let the **workflow** fill **Machine SKU** if you use [`QUOTE-LINE-AUTOMATION.md`](./QUOTE-LINE-AUTOMATION.md). If you must pick **Machine SKU** by hand, choose the option whose text matches the **product’s code and name** from the catalog (not a similar-looking duplicate).

3. **Hide Machine SKU** (optional): **Setup → Customization → Quotes → (your quote layout) →** edit the subform/line layout **Quoted Items** and **remove** **Machine SKU** from the form (or put it in an **Unused** section). The field can still be filled in the background.

4. If you use a **Client Script** on Quotes/Quoted Items, try **disabling** it temporarily. Scripts can block or override picklist / dependent-field behavior while you test.

5. **Model / speed shows “None” or only “- Not applicable -”** for a product (e.g. `CANON-IP-V1350`): the parent picklist in map dependency must be the field with **api_name `Machine_SKU`** (label **Product (Machine)**) — not a duplicate field (e.g. `Machine_SKU1`). The provisioning script’s `MODEL_SPEED` map in `tools/zoho/provision_quoted_line_dependencies.py` must list that **Product_Code**; re-run `make zoho-quoted-line-deps` after updating it.

6. **Model / speed and Configuration 1/2 show every option (not filtered per machine):** Zoho’s **map dependency** is tied to the **Product (Machine)** picklist (`Machine_SKU`), **not** the **Product Name** lookup. If you only set **Product Name**, the parent picklist is still empty **until the quote is saved** and the **workflow** fills **Product (Machine)** — so the UI may list all child values. **Fix (instant):** add the Client Script in `artifacts/zoho/client_scripts/quote_line_sync_machine_sku_on_product_name.js` to **Quotes → Quoted_Items → onCellChange** so `Machine_SKU` is set from the product record (or from the `(...CODE)` suffix on the name) as soon as **Product Name** changes — then dependent picklists filter without Save. **Alternatives:** pick **Product (Machine)** first on the line, **or** set **Product Name** then **Save** and re-open. After any `provision_quoted_line_dependencies.py` change, run `provision_quoted_line_product_first_layout.py` so the **layout** has the picklist option ids the map needs (`make zoho-quote-line-product-first-layout`). Remove any duplicate **Machine SKU** (`Machine_SKU1`) field from the line layout if it was created by mistake.

## Related

- [`QUOTE-LINE-AUTOMATION.md`](./QUOTE-LINE-AUTOMATION.md) — Deluge function + workflow to set **Machine SKU** from the product.  
- [`PRODUCTS-AND-QUOTES.md`](./PRODUCTS-AND-QUOTES.md) — quote PDF and descriptions.
