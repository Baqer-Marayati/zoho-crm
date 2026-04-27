/* Zoho CRM — Quotes: Quoted_Items
 * When **Product Name** (lookup) changes, set **Product (Machine)** (Machine_SKU) to
 * "Product_Code - Product_Name" (same shape as map_dependency + Deluge).
 * Then Model / speed, Configuration 1, Configuration 2 filter without Save.
 *
 * Install: Client Script on Quotes, **Subform** Quoted_Items, event **onCellChange**.
 * Upload: tools/zoho/provision_quote_line_client_script.py (needs client_scripts OAuth scope).
 */
var __Q_LINE_SUBFORM = "Quoted_Items";
var __Q_PRODUCT = "Product_Name";
var __Q_MACHINE = "Machine_SKU";

function __qLineZohoPick(s) {
  if (!s) {
    return s;
  }
  var t = String(s);
  t = t.replace(/[\u2014\u2013\u2012]/g, "-");
  t = t.split("&").join(" and ");
  t = t.replace(/[^a-zA-Z0-9 \-().,/%+]/g, " ");
  t = t.replace(/\s+/g, " ").trim();
  return t.length > 255 ? t.substring(0, 255) : t;
}

function __qLineSkuFromName(nameStr) {
  var name = (nameStr || "").trim();
  if (!name) {
    return null;
  }
  var m = name.match(/\(([A-Z0-9-]+)\)\s*$/);
  if (m) {
    var c = m[1];
    var base = name.replace(/\s*\([^)]+\)\s*$/, "").trim();
    return __qLineZohoPick(c + " - " + base);
  }
  return null;
}

/* Bind to: Subform Quoted_Items → onCellChange (Zoho Client Script event picker). */
function onCellChange(args) {
  if (typeof ZDK === "undefined" || !ZDK.Page) {
    return;
  }
  var a = args || {};
  var field = a.fieldName || a.field || a.apiName || a.colName || "";
  if (String(field) !== __Q_PRODUCT) {
    return;
  }
  var rowIndex =
    a.rowIndex !== undefined && a.rowIndex !== null
      ? parseInt(a.rowIndex, 10)
      : a.index !== undefined
        ? parseInt(a.index, 10)
        : 0;
  if (isNaN(rowIndex)) {
    rowIndex = 0;
  }
  var f = ZDK.Page.getField(__Q_LINE_SUBFORM);
  if (!f || typeof f.getValue !== "function" || typeof f.setValue !== "function") {
    return;
  }
  var val = a.value;
  if (!val || !val.id) {
    var rows0 = [].concat(f.getValue() || []);
    if (rows0[rowIndex]) {
      rows0[rowIndex][__Q_MACHINE] = null;
      f.setValue(rows0);
    }
    return;
  }
  var rows = [].concat(f.getValue() || []);
  if (!rows[rowIndex]) {
    return;
  }
  function applySku(sku) {
    if (!sku) {
      return;
    }
    var r2 = [].concat(f.getValue() || []);
    if (r2[rowIndex]) {
      r2[rowIndex][__Q_MACHINE] = sku;
      f.setValue(r2);
    }
  }
  var fromName = __qLineSkuFromName(val.name || val.Name || "");
  if (
    ZDK.Apps &&
    ZDK.Apps.CRM &&
    ZDK.Apps.CRM.Products &&
    typeof ZDK.Apps.CRM.Products.fetchById === "function"
  ) {
    var res = ZDK.Apps.CRM.Products.fetchById(String(val.id));
    if (res && typeof res.then === "function") {
      res.then(
        function (rec) {
          if (rec && (rec.Product_Code || rec["Product Code"])) {
            var code = rec.Product_Code || rec["Product Code"];
            var pn = rec.Product_Name || rec["Product Name"] || "";
            applySku(__qLineZohoPick(String(code) + " - " + String(pn).trim()));
          } else if (fromName) {
            applySku(fromName);
          }
        },
        function () {
          if (fromName) {
            applySku(fromName);
          }
        }
      );
      return;
    }
    if (res && (res.Product_Code || res["Product Code"])) {
      var code2 = res.Product_Code || res["Product Code"];
      var pn2 = res.Product_Name || res["Product Name"] || "";
      applySku(__qLineZohoPick(String(code2) + " - " + String(pn2).trim()));
      return;
    }
  }
  if (fromName) {
    applySku(fromName);
  }
}
