# SAP Business One Discovery

Do this only after the first SharePoint-based app and flow are working.

## Why SAP is phase two

You said your `SAP Business One` system is hosted online and you are not yet sure what technical access exists.

That matters because Power Platform integration with SAP can vary a lot depending on:

- whether `SAP Business One` exposes a supported API or service layer
- whether your company allows outside platforms to connect
- whether a gateway, middleware, or premium licensing is needed

For a beginner, the safest path is to learn the Microsoft pattern first, then investigate SAP with IT or the SAP vendor.

## What to ask IT or the SAP vendor

Use this checklist when you are ready:

### Access and architecture

- Is this definitely `SAP Business One` and not `SAP S/4HANA` or another SAP product?
- Is there a supported `Service Layer`, `API`, or `OData` endpoint?
- Is the system reachable from Microsoft cloud services?
- Does the system require a VPN, gateway, or IP allowlisting?

### Authentication

- How do integrations authenticate?
- Are service accounts allowed?
- Can a non-interactive integration account be created?

### Data and use cases

- Do we only need to read SAP data, or also write back to SAP?
- Which specific objects are needed first: items, customers, invoices, approvals, stock, or something else?
- Is near-real-time access required, or is scheduled sync enough?

### Governance

- Are there company restrictions on Power Apps or Power Automate accessing SAP?
- Are there approved middleware tools already used in the company?
- Are there licensing or security approvals needed before integration?

## Likely integration paths

### Path 1: Power Automate Desktop

Best when:

- you only have screen-level access
- there is no confirmed API yet
- you need to automate a manual SAP task

Pros:

- fastest way to prove value without deep SAP setup
- works when the user can already perform the task manually

Cons:

- more fragile than API-based integration
- depends on screen layout and desktop runtime

## Path 2: API or service-layer integration

Best when:

- IT confirms `SAP Business One` exposes a supported integration endpoint
- the business needs cleaner, more durable integration

Pros:

- more reliable and scalable than screen automation
- better for future apps and flows

Cons:

- needs technical setup from IT or vendor
- may need premium licensing, custom connectors, or middleware

## Path 3: Middleware or custom connector

Best when:

- direct connectivity is possible but not simple
- your company already uses an integration platform

Examples may include:

- middleware approved by your IT team
- a custom connector built for Power Platform
- vendor-provided integration tooling

Pros:

- can standardize access to SAP data
- can simplify future Power Platform projects

Cons:

- takes more design and governance work
- may be too much for the first project

## Recommendation for this project

Do not assume a built-in Power Platform connector will directly solve `SAP Business One`.

Use this sequence instead:

1. build the first app and flow with SharePoint
2. confirm the business process works
3. gather SAP access facts from IT or the vendor
4. choose one SAP path based on real constraints

## First SAP proof-of-concept ideas

Pick only one small use case:

- read a simple list from SAP into a report or app
- trigger a notification when a known SAP event happens
- automate one repetitive SAP desktop task

Avoid a large end-to-end ERP app as the first SAP attempt.

## Decision table

| Situation | Recommended path |
|---|---|
| Only user login and normal SAP screens are available | `Power Automate Desktop` |
| IT can provide API or service-layer details | API-first integration |
| Company already uses middleware | Use the approved middleware path |
| No one knows the SAP integration story yet | Keep SAP out of version one |

## Exit criteria for SAP readiness

Only start SAP build work when you know:

- the target SAP objects you need
- the supported integration method
- who owns the technical setup
- what licensing or approvals are required
