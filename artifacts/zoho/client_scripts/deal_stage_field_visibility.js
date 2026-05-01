/* Zoho CRM Client Script - Deals (Standard layout)
 *
 * Progressive visibility: keep **Qualification** lean; reveal fields as the deal advances.
 * Stage labels must match the unified pipeline in `tools/zoho/pipelines_seed.json`.
 *
 * Bind in **Setup -> Developer Space -> Client Scripts** (same body for each):
 *   - **Create Page (Standard)** -> Page -> **onLoad**
 *   - **Create Page (Standard)** -> Page -> **onChange** (any field change refreshes Stage-dependent UI)
 *   - **Edit Page (Standard)**   -> Page -> **onLoad**
 *   - **Edit Page (Standard)**   -> Page -> **onChange**
 *
 * Do not wrap this file in `function onLoad() { }` - the host invokes the script body directly.
 */
var __DEAL_STAGE_API = "Stage";

var __STAGE_QUALIFICATION = "Qualification";
var __STAGE_NEEDS_ANALYSIS = "Needs Analysis";
var __STAGE_PROPOSAL_QUOTE = "Proposal / Quote";
var __STAGE_NEGOTIATION = "Negotiation";
var __STAGE_CLOSED_WON = "Closed Won";
var __STAGE_CLOSED_LOST = "Closed Lost";

/** Shown only after Qualification (discovery / early pursuit). */
var __FIELDS_AFTER_QUALIFICATION = [
  "Competitor",
  "Discovery_summary",
  "Applications",
  "Budget_financing_status",
  "Next_try_follow_up_date",
  "Current_machines_setup"
];

/** Quote-related - once a formal quote exists in the motion. */
var __FIELDS_QUOTE_PHASE = [
  "Any_quote_shared_with_customer",
  "Primary_Quote"
];

/** Late pipeline notes. */
var __FIELDS_WON_NOTES = ["Won_handoff_notes"];

/** Outcome - both APIs may exist in the same org (legacy + custom). */
var __FIELDS_LOST = ["Lost_Reason", "Reason_For_Loss__s"];

var __DISCOVERY_GATE_FIELDS = [
  { api: "Discovery_summary", label: "Discovery summary" },
  { api: "Current_machines_setup", label: "Current machines / setup" },
  { api: "Applications", label: "Applications" },
  { api: "Budget_financing_status", label: "Budget / financing status" }
];

function __dealStageLabel() {
  if (typeof ZDK === "undefined" || !ZDK.Page) {
    return "";
  }
  var st = ZDK.Page.getField(__DEAL_STAGE_API);
  if (!st) {
    return "";
  }
  var v;
  try {
    v = st.getValue();
  } catch (e1) {
    return "";
  }
  if (v == null || v === undefined) {
    return "";
  }
  if (typeof v === "string") {
    return v.trim();
  }
  if (typeof v === "object") {
    if (v.name) {
      return String(v.name).trim();
    }
    if (v.display_value) {
      return String(v.display_value).trim();
    }
  }
  return String(v).trim();
}

function __dealIndexOfStage(label) {
  var order = [
    __STAGE_QUALIFICATION,
    __STAGE_NEEDS_ANALYSIS,
    __STAGE_PROPOSAL_QUOTE,
    __STAGE_NEGOTIATION,
    __STAGE_CLOSED_WON,
    __STAGE_CLOSED_LOST
  ];
  for (var i = 0; i < order.length; i++) {
    if (order[i] === label) {
      return i;
    }
  }
  return -1;
}

function __dealSetFieldVisible(apiName, visible) {
  if (typeof ZDK === "undefined" || !ZDK.Page) {
    return;
  }
  var f;
  try {
    f = ZDK.Page.getField(apiName);
  } catch (e0) {
    return;
  }
  if (!f) {
    return;
  }
  try {
    if (typeof f.setVisibility === "function") {
      f.setVisibility(visible);
      return;
    }
  } catch (e1) {}
  try {
    if (typeof f.setVisible === "function") {
      f.setVisible(visible);
    }
  } catch (e2) {}
}

function __dealFieldValue(apiName) {
  if (typeof ZDK === "undefined" || !ZDK.Page) {
    return "";
  }
  var f;
  try {
    f = ZDK.Page.getField(apiName);
  } catch (e0) {
    return "";
  }
  if (!f) {
    return "";
  }
  var v;
  try {
    v = f.getValue();
  } catch (e1) {
    return "";
  }
  if (v == null || v === undefined) {
    return "";
  }
  if (typeof v === "string") {
    return v.trim();
  }
  if (typeof v === "object") {
    if (v.name) {
      return String(v.name).trim();
    }
    if (v.display_value) {
      return String(v.display_value).trim();
    }
    if (v.id) {
      return String(v.id).trim();
    }
  }
  return String(v).trim();
}

function __dealSetFieldValue(apiName, value) {
  if (typeof ZDK === "undefined" || !ZDK.Page) {
    return;
  }
  var f;
  try {
    f = ZDK.Page.getField(apiName);
  } catch (e0) {
    return;
  }
  if (!f) {
    return;
  }
  try {
    if (typeof f.setValue === "function") {
      f.setValue(value);
    }
  } catch (e1) {}
}

function __dealMissingDiscoveryFields() {
  var missing = [];
  __dealEach(__DISCOVERY_GATE_FIELDS, function (item) {
    var value = __dealFieldValue(item.api);
    if (!value || value === "-None-") {
      missing.push(item.label + " (" + item.api + ")");
    }
  });
  return missing;
}

function __dealShowError(message) {
  try {
    if (typeof ZDK !== "undefined" && ZDK.Client && ZDK.Client.showMessage) {
      ZDK.Client.showMessage(message, { type: "error" });
      return;
    }
  } catch (e0) {}
  try {
    alert(message);
  } catch (e1) {}
}

function __dealEach(arr, fn) {
  for (var i = 0; i < arr.length; i++) {
    fn(arr[i]);
  }
}

function __dealApplyStageVisibility() {
  var label = __dealStageLabel();
  var idx = __dealIndexOfStage(label);
  /* On create pages, Zoho can run onLoad before Stage is hydrated; default to the first stage. */
  var isQualification = !label || label === __STAGE_QUALIFICATION || idx === 0;
  var isClosedLost =
    label.indexOf("Closed Lost") >= 0 || label === __STAGE_CLOSED_LOST;
  var isClosedWon = label === __STAGE_CLOSED_WON;
  var proposalQuoteIdx = __dealIndexOfStage(__STAGE_PROPOSAL_QUOTE);
  var inQuotePhase = idx >= proposalQuoteIdx && proposalQuoteIdx >= 0;
  var negotiationOrWon =
    label === __STAGE_NEGOTIATION || isClosedWon;

  __dealEach(__FIELDS_AFTER_QUALIFICATION, function (a) {
    __dealSetFieldVisible(a, !isQualification);
  });

  __dealEach(__FIELDS_QUOTE_PHASE, function (a) {
    __dealSetFieldVisible(a, inQuotePhase || isClosedLost);
  });

  __dealEach(__FIELDS_WON_NOTES, function (a) {
    __dealSetFieldVisible(a, negotiationOrWon);
  });

  __dealEach(__FIELDS_LOST, function (a) {
    __dealSetFieldVisible(a, isClosedLost);
  });
}

__dealApplyStageVisibility();

if (__dealStageLabel() === __STAGE_PROPOSAL_QUOTE) {
  var __missingDiscovery = __dealMissingDiscoveryFields();
  if (__missingDiscovery.length > 0) {
    __dealShowError(
      "Proposal / Quote is blocked until these discovery fields are complete:\n- " +
        __missingDiscovery.join("\n- ") +
        "\n\nBudget / financing status must be a picklist choice."
    );
    __dealSetFieldValue(__DEAL_STAGE_API, __STAGE_NEEDS_ANALYSIS);
    return false;
  }
}
