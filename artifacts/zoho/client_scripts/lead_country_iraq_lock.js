/* Zoho CRM Client Script - Leads
 * Bind in Developer Hub: Page event = onLoad (do NOT wrap the whole file in
 * `function onLoad() { }` - the editor already runs this body for onLoad, and
 * a named `onLoad` function is often never invoked, so the field would not update.)
 *
 * - Create Page (Standard) and Edit Page (Standard): separate script entries if needed.
 * Workflow field update still enforces Iraq after Save.
 */
var __LEAD_COUNTRY_API = "Country";
var __LEAD_COUNTRY_VALUE = "Iraq";

function __leadCountryApplyIraq() {
  if (typeof ZDK === "undefined" || !ZDK.Page) {
    return;
  }
  var f = ZDK.Page.getField(__LEAD_COUNTRY_API);
  if (f) {
    try {
      f.setValue(__LEAD_COUNTRY_VALUE);
    } catch (e1) {}
    try {
      f.setReadOnly(true);
    } catch (e2) {}
    return;
  }
  /* Some orgs: Address subfield only binds after compound init — try form-level set. */
  var form = ZDK.Page.getForm && ZDK.Page.getForm();
  if (form && typeof form.setValues === "function") {
    try {
      var row = {};
      row[__LEAD_COUNTRY_API] = __LEAD_COUNTRY_VALUE;
      form.setValues(row);
    } catch (e3) {}
  }
}

__leadCountryApplyIraq();
