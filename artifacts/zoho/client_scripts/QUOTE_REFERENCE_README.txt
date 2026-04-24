Quote "Subject" → Reference + autofill
====================================

**API name** stays **Subject** (Zoho does not let you rename the API name). The on-screen
label is **Reference** (via `tools/zoho/provision_quote_reference_field.py`).

**Autofill (required so reps do not type Reference)**  
Try automated push: `make zoho-quote-reference-full` from repo root (runs
`tools/zoho/provision_quote_client_script.py`). If that returns **401**, add
`ZohoCRM.settings.client_scripts.ALL` to the API Console, regenerate the refresh token,
then re-run. If your org still blocks the REST call, add a **Client Script** in CRM by hand:

1. **Setup** → **Developer Space** (or **Customization** → **Developer Space**) → **Client Script** → **+ New**.
2. **Module:** Quotes.
3. Paste the full contents of **`quote_reference_autofill.js`** (from the first
   `/*` comment through `__refApply();`).
4. Wire events (names vary by CRM version; use what the UI offers):
   - **Create** page, **onLoad** — run the script.
   - **Create** page, **onChange** on **Deal_Name** — same script.
   - **Create** page, **onChange** on **Account_Name** — same script.
5. Save and test **New Quote** with no data → Reference should get a `Quote — …` or
   timestamp string; with **Deal** set → should mirror deal name (trimmed to 120 chars).

If **setValue** does not run, the field may be **read-only** on the layout. In that case
run `provision_quote_reference_field.py --no-read-only` or in **Layouts** open the
**Reference** field and clear read-only, then re-test.

**Hiding or moving the field**  
The Layouts API **cannot** move system-mandatory fields out of a section. To put
**Reference** at the bottom of the form or in a separate block:

- **Setup** → **Customization** → **Modules and Fields** → **Quotes** → your layout
  (e.g. **Standard**).
- **Drag** the **Reference** field to the end of **Quote Information**, or add a
  small section (e.g. "Internal") and drag it there.  
- You still cannot remove the field from the layout.

**Print / PDF**  
The repo quote template may show the column as "Reference" if re-provisioned
(`provision_quote_template.py`). The merge field remains `${Quotes.Subject}`.
