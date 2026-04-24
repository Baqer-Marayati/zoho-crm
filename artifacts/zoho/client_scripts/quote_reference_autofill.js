/* Zoho CRM Client Script - Quotes
 * - auto-fill Reference (field API name: Subject)
 * - default Valid Until to today + 14 days on create
 * Pattern: Q + 9-char alphanumeric uppercase (example: Q7K2M9Q4P1)
 * Recommended event: Create Page (Standard) -> onLoad
 */
var __REF_SUBJECT_API = "Subject";
var __REF_LEN = 10;
var __REF_PREFIX = "Q";
var __REF_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
var __VALID_TILL_API = "Valid_Till";
var __VALID_DAYS_OFFSET = 14;

function __refIsAutoPattern(v) {
  if (!v) {
    return false;
  }
  return /^Q[A-Z0-9]{9}$/.test(v);
}

function __refRandomIndex(max) {
  if (
    typeof window !== "undefined" &&
    window.crypto &&
    window.crypto.getRandomValues &&
    max > 0 &&
    max <= 256
  ) {
    var arr = new Uint8Array(1);
    window.crypto.getRandomValues(arr);
    return arr[0] % max;
  }
  return Math.floor(Math.random() * max);
}

function __refBuildCode() {
  var out = __REF_PREFIX;
  for (var i = out.length; i < __REF_LEN; i++) {
    var idx = __refRandomIndex(__REF_CHARS.length);
    out += __REF_CHARS.charAt(idx);
  }
  return out;
}

function __refApply() {
  var f = ZDK.Page.getField(__REF_SUBJECT_API);
  if (!f) {
    return;
  }
  var curr = "";
  try {
    curr = String(f.getValue() || "").trim().toUpperCase();
  } catch (e) {}
  /* Keep custom values; only replace blank or previous auto-generated values. */
  if (curr && !__refIsAutoPattern(curr)) {
    return;
  }
  f.setValue(__refBuildCode());
}

function __toYmd(d) {
  var y = d.getFullYear();
  var m = String(d.getMonth() + 1).padStart(2, "0");
  var day = String(d.getDate()).padStart(2, "0");
  return y + "-" + m + "-" + day;
}

function __validTillApplyDefault() {
  var f = ZDK.Page.getField(__VALID_TILL_API);
  if (!f) {
    return;
  }
  try {
    var curr = f.getValue();
    if (curr && String(curr).trim() !== "") {
      return;
    }
  } catch (e) {}

  var d = new Date();
  if (isNaN(d.getTime())) {
    return;
  }
  d.setDate(d.getDate() + __VALID_DAYS_OFFSET);
  f.setValue(__toYmd(d));
}

__refApply();
__validTillApplyDefault();
