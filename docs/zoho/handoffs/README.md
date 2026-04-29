# Agent handoffs — Deals, Quotes, workflows

Long-form prompts and blueprints that are meant to be **copied into a Cursor agent** or handed to the next implementer. They are **not** the everyday entry point; use [`../INDEX.md`](../INDEX.md) first.

| File | Purpose |
|------|---------|
| [`AGENT-PROMPT-DEALS-DELUGE-FUNCTIONS.md`](./AGENT-PROMPT-DEALS-DELUGE-FUNCTIONS.md) | End-to-end checklist: provision Deluge functions + function-backed workflow rules via `tools/zoho` + official Zoho CRM MCPs |
| [`AGENT-HANDOFF-DEALS-BLUEPRINT-WORKFLOWS.md`](./AGENT-HANDOFF-DEALS-BLUEPRINT-WORKFLOWS.md) | Business and technical spec: Deal/Quote fields, stage motion, optional Blueprint vs workflow/Deluge substitutes |

**Operational truth** for what is deployed and how to re-run it lives in [`../DEALS-QUOTES-PROCESS-PROVISIONING.md`](../DEALS-QUOTES-PROCESS-PROVISIONING.md) and `make zoho-deals-quotes-process`.
