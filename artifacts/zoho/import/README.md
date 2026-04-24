# Import templates (no live data)

| File | Purpose |
|------|---------|
| `leads_import_template.csv` | Column hints for **&lt;500** row lead import — map to your org’s Zoho field API names in the import wizard |
| `products_wave_a_template.csv` | **Wave A** product skeleton — **IQD** list price; add real SKUs |
| `canon_products_wave_a_en.csv` | **Canon** English specs from `* EN.rtf` — `make zoho-build-canon-products-en` → `make zoho-phase3-canon-products`; **no SKU** column — import skips rows whose **Product_Name** already exists; **Unit_Price** `0` until pricing |
| `canon_products_five_machines_en.csv` | **Canon** line consolidated to **five** products (machine families) with **Product_Code** — `make zoho-build-canon-five-machines` → `make zoho-phase3-canon-five-machines`; see [`canon_product_line/README.md`](./canon_product_line/README.md) |

**Rules:** Do not commit files with real customer PII. Use scratch CSVs locally for real imports.

**Placeholders:** `products_wave_a_template.csv` must not contain the substring `example sku` (any case) in any cell, or `provision_phase3.py --step 2` will skip the import. For leads, replace `example.invalid` emails and demo company names before a real import.
