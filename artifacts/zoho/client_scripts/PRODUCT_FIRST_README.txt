Product-first line UX — optional real-time (before save)
==========================================================

After **Product (Machine)** (field api_name: Machine_SKU) is the rep-facing picklist and
**Product Name** (lookup) is off the layout, the Quote **workflow** custom function
still sets **Product Name** on every Save. That is enough for list price / totals, but
reps will not see the Product lookup and unit price **until the first save**.

For **instant** sync when the rep changes **Product (Machine)** on a line, add a
Zoho **Client Script** on the **Quotes** module. Zoho’s Client Script API and event
names vary by org version; use Setup → **Developer Space** (or **Customization**) →
**Client Script** in your tenant and follow the in-product template for:
  - module: **Quotes**
  - event: field change (or “record / subform” change, as offered)
  - subform: **Quoted_Items** (or “Quote Line” label)
  - field: **Machine_SKU** (display label: Product (Machine))
Logic (same as Deluge, but in the client runtime Zoho provides):
  1) Read the new picklist value as text:   "<Product_Code> - <Product_Name>"
  2) Parse the code = substring before the first  " - "  (or whole string)
  3) If you can resolve a Product id from code (Zoho’s client API may allow a lookup
     or you call a short Deluge/connection), set **Product_Name** on the current line
     to { id: <Product Id> }.

If your build does not expose a reliable subform client hook, the workflow-on-save path
is still the supported default.

Relevant Deluge (server): ../../deluge/quoted_items_sync_machine_sku.deluge
