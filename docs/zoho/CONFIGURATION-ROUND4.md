# Configuration decisions — round 4

**Captured 2026-04-23**

| Topic | Decision |
|--------|----------|
| **After-sales / support** | **Sales-only CRM** — no **Cases** / service module in scope for the foreseeable future. |
| **Web / ad leads** | **Later** — not part of **v1** (no automatic web-to-lead yet). |
| **CRM language** | **English** UI and picklists (training materials can still be bilingual if needed). |
| **Competitors** | **Yes** — track **competitor** on deals; treat as **required when Stage = Closed Lost** (and optionally optional earlier). |
| **Sandbox** | **No** separate sandbox — **configure carefully in production**; use **export/notes** before big layout changes. |

## 1. Sales-only scope

- Do **not** enable or train **Cases** for v1.  
- If support is needed later, revisit **Cases** or **Zoho Desk** integration.

## 2. Competitor field

1. **Setup → Modules and Fields → Deals** — add picklist **Competitor** (values: your main rivals + **None / Unknown**).  
2. Make it **required** when **Stage = Closed Lost** (field dependency, validation, or blueprint — per edition).  
3. Optional: require or prompt when moving to **Negotiation** if you want early competitive tracking.

## 3. English UI

- Set user **language** to English in Zoho where profile allows.  
- Keep **picklist values** in English for consistency with this repo’s seed files (`pipelines_seed.json`, etc.).

## 4. No sandbox discipline

- Before **major** changes: screenshot or export field lists; change **one** area at a time.  
- Prefer **off-hours** for layout edits if many users are live.

## Related

- [`CONFIGURATION-ROUND3.md`](./CONFIGURATION-ROUND3.md)  
- [`LEADS-AND-DEALS.md`](./LEADS-AND-DEALS.md)  
- [`PROJECT-STATUS.md`](../PROJECT-STATUS.md)
