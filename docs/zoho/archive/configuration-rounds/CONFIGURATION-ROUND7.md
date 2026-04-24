# Configuration decisions — round 7 (numbering, reporting, audit, security, go-live)

**Captured 2026-04-23**

| Topic | Decision |
|--------|----------|
| **Numbering** | **Zoho defaults** for **Quote** / **Deal** identifiers — **no** custom prefix scheme for **v1**. |
| **Fiscal / reports** | **Calendar year** (**Jan–Dec**) for reporting alignment. |
| **Audit / history** | **Medium** — prioritize visibility on **Stage** and **Amount** changes; expand field history later if needed. |
| **Security** | **MFA required** for **all** CRM users (enforce via Zoho / identity settings per org policy). |
| **Go-live** | **Pilot** — **2–3 reps** first, then broader rollout after fixes. |

## 1. Numbering

- Skip custom **auto-number** modules until the business asks for branded quote IDs.  
- **Deal name** can still follow a **text convention** (e.g. `Account — Production`) without system numbering.

## 2. Calendar-year reporting

- Dashboards and **YTD** filters use **Jan–Dec** unless finance publishes a different rule later.

## 3. Stage and amount history

- Enable or use **Field History** / **Audit Log** (per edition) for **Stage** and **Amount** on **Deals**.  
- Train managers to use **Deal History** when reviewing pipeline changes.

## 4. MFA for everyone

**Important:** MFA is usually **not** under **CRM → Setup (gear)** search. It is configured per **Zoho Account** login:

1. Open [https://accounts.zoho.com](https://accounts.zoho.com) (or [https://accounts.zoho.eu](https://accounts.zoho.eu) / [https://accounts.zoho.in](https://accounts.zoho.in) to match your region).  
2. Sign in → **profile / My Account** → **Multi-Factor Authentication** / **OneAuth** (wording varies).  
3. Each CRM user repeats for their own Zoho ID. Org-wide “force MFA” may use **Zoho Directory** / bundle-specific admin — not always visible in CRM Setup.

Help: [MFA introduction](https://help.zoho.com/portal/en/kb/accounts/multi-factor-authentication/articles/mfa-introduction).

Communicate before pilot: install **OneAuth** (or allowed method). If you use **Microsoft SSO** into Zoho, MFA may be governed by **Microsoft** instead — confirm with IT.

## 5. Pilot go-live

| Step | Action |
|------|--------|
| 1 | Pick **2–3** reps (mix **Production** and **MPS** if possible). |
| 2 | **1–2 week** pilot: real leads/deals, daily feedback. |
| 3 | Fix **layouts, picklists, assignment** issues. |
| 4 | **Roll out** to full **4–10** users with short group training. |

Document pilot **start date** in [`PROJECT-STATUS.md`](../PROJECT-STATUS.md) when set.

## Related

- [`CONFIGURATION-ROUND6.md`](./CONFIGURATION-ROUND6.md)  
- [`PROJECT-STATUS.md`](../PROJECT-STATUS.md)
