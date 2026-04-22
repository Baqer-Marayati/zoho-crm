# PowerPlatform-Approvals

Git repository root is this folder (on disk it may live under a parent named **Power Platform**). The solution name remains **PowerPlatform-Approvals**.

This project is a beginner-friendly starter for building a Microsoft Power Platform solution with:

- `Power Apps` for the user-facing app
- `Power Automate` for approvals and notifications
- `SharePoint` for the first datastore

The first version deliberately avoids direct `SAP Business One` integration. The goal is to learn the core Microsoft pattern first, then add SAP safely once the technical access path is confirmed.

## First project

Build a simple approval app where a user:

1. submits a request from a canvas app
2. creates a new item in a SharePoint list
3. triggers a Power Automate approval flow
4. receives the approval result by email or Teams

## Project structure

- `docs/overview.md`: architecture, scope, and delivery order
- `docs/setup-checklist.md`: tenant, environment, permissions, and setup checklist
- `docs/sharepoint-list-schema.md`: first SharePoint list design
- `docs/power-automate-approval-flow.md`: step-by-step flow build guide
- `docs/power-apps-canvas-app.md`: step-by-step canvas app build guide
- `docs/sap-business-one-discovery.md`: second-phase SAP integration paths and questions
- `artifacts/`: solution exports and optional unpacked metadata; see `artifacts/README.md` for naming and git rules

## Build order

1. Confirm you can access Power Apps, Power Automate, and SharePoint.
2. Create the SharePoint list.
3. Build and test the approval flow.
4. Build the canvas app against the same list.
5. Test the full loop end to end.
6. Start SAP discovery only after the first version is working.

## Success criteria

You should end with:

- one working Power Apps canvas app
- one working Power Automate approval flow
- one SharePoint list storing the requests
- one documented path for future SAP Business One integration

## Notes

- Do not store passwords, connection secrets, or tenant-only sensitive URLs in this repo.
- Solution exports and PAC unpack output live under `artifacts/` (not inside `docs/`). Follow `artifacts/README.md` for filenames and review workflow.
