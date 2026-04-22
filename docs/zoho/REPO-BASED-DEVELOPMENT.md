# Repository-based development with Zoho

## What “everything in Git” really means

| In Git (good fit) | In Zoho / Power BI (expected) |
|-------------------|------------------------------|
| Python/Node **scripts** that call Zoho APIs | **Org configuration** (many screens in admin) |
| `.env.example` and **local** `.env` (never commit secrets) | **OAuth refresh tokens** and Zoho user passwords |
| **Copies** of Deluge and validation logic (as `.md` or `.ds` in repo) | **Authoritative** copy in Zoho’s script editors |
| **Power Query M** and **DAX** snippets as text, or a checked-in `.pbip` if you use PBIP | **Authoritative** model and report in Power BI; publish from Desktop |
| **Runbooks** and checklists for releases | Clicks in Zoho to deploy certain changes |

## Typical workflow

1. **Change design** in a doc or a PR (field list, pipeline stages, new automation rule in plain language).
2. **Implement in Zoho** (admin) or **in a script** in this repo.
3. If **scripted**, run it locally: `source .env && python tools/zoho/...` (exact commands to be added with each script).
4. **Test** in a Zoho **sandbox** if your plan includes one, or in a limited pilot in production (your risk call).
5. **Document** the outcome in `../PROJECT-STATUS.md`.

## What the AI in Cursor can do

- Author and edit **files in this repo** (code, docs, M queries, checklists).
- You run **terminal commands** in your environment; the AI does **not** have your Zoho session.

## What is *not* realistic

- A single `import` that recreates a full Zoho org from Git with **no** product interaction.
- Storing long-lived Zoho **passwords** or **refresh tokens** in the repository.

That model is still **feasible** for day-to-day work: **short checklists** for one-time or rare admin steps, and **automation** for everything repetitive (bulk data, custom integrations).
