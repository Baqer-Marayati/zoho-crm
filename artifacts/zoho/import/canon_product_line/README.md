# Canon product line — five Zoho products

This folder documents the **consolidated** catalog: **five** Products in Zoho (one per machine line), with speed tiers and options merged into **Description** for review. Quote-line picklists for speed / license / configuration are still to be added in Zoho layouts.

| File | Role |
|------|------|
| `../canon_products_five_machines_en.csv` | Import file: `Product_Name`, `Product_Code`, `Unit_Price`, `Qty_in_Stock`, `Description` |
| `five_machines_manifest.json` | SKU roots, suggested attachment filenames, row counts from the flat spec CSV |

## Regenerate from flat Canon EN export

After updating `../canon_products_wave_a_en.csv` (from `make zoho-build-canon-products-en`):

```bash
cd tools/zoho
./venv/bin/python build_canon_five_machines_csv.py
```

## Upload to Zoho

**Recommended (removes overlapping 23-row Wave-A products by name, then imports five):**

```bash
make zoho-sync-canon-five-products
```

Import only (no deletes):

```bash
make zoho-phase3-canon-five-machines
```

Or:

```bash
cd tools/zoho
./venv/bin/python sync_canon_five_products_zoho.py
./venv/bin/python provision_phase3.py --step 2 --products-csv ../../artifacts/zoho/import/canon_products_five_machines_en.csv
```

**If you already imported the older 23-row file**, run `zoho-sync-canon-five-products` so legacy names are removed before the five-machine rows exist—avoids duplicate engines/accessories.

After import: attach **hero image**, **datasheet**, and **brochure** per product using the filename prefix in `five_machines_manifest.json`.

**Bulk PDF upload:** From the repo, `make zoho-upload-canon-product-pdfs` runs `tools/zoho/upload_canon_product_pdfs.py`, which uploads all `*.pdf` files from `~/Dropbox/Work/Canon/Canon machine specs for SAP/{VarioPrint 6000 TITAN,imagePRESS V1000,…}` to the corresponding Zoho product’s **Attachments**.

## Product Description (short vs configuration)

- **`Description`** on each product is a **short catalog blurb** (same whenever that product is used). Edit copy in `tools/zoho/build_canon_five_machines_csv.py` (`CURATED_DESCRIPTIONS`), run `make zoho-build-canon-five-machines`, then `make zoho-sync-canon-product-descriptions` to refresh Zoho.
- **Chosen speed, finisher, and POD** should **not** rewrite the product record; they belong on the **quote line** (and in line-item description/PDF if you map it). That keeps the catalog stable and avoids contradictory product text.
- Deep spec remains in **attachments** and in the **Compatible finishers** / **Compatible POD / paper** text areas (from `provision_quote_line_extensions.py`).
- To regenerate the old one-field spec dump (not recommended), run `build_canon_five_machines_csv.py --long-spec`.
