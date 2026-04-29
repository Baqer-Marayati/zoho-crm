# Manual upload packages (escape hatch)

Use these folders only when **API automation cannot complete** a Zoho step and you need **copy-paste or UI upload** as a last resort.

| Package | Status | See |
|---------|--------|-----|
| **Deals + Quotes process** | **Primary path is API** — run `make zoho-deals-quotes-process` from the repo root | [`deals_quotes_process/README.md`](./deals_quotes_process/README.md) |

**Canonical Deluge** for the three Deals/Quotes functions lives under `../deluge/` (`quote_recompute_deal_shared.deluge`, `quote_shared_owner_guard.deluge`, `deal_stage_gate_guard.deluge`). The `deals_quotes_process/functions/` tree holds **FULL** and **BODY_ONLY** variants for the Zoho function editor when needed.
