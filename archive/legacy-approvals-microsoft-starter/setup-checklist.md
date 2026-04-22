# Setup Checklist

Use this checklist before building the app or the flow.

## 1. Account and portal access

Confirm you can sign in with your work account to:

- [Power Apps](https://make.powerapps.com)
- [Power Automate](https://make.powerautomate.com)
- your SharePoint team site

If any of these fail, stop and ask IT for access before continuing.

## 2. Power Platform environment

In the top-right corner of Power Apps, confirm:

- you can see at least one environment
- you can select the intended environment
- you can create a canvas app
- you can create a cloud flow

Record the answers here once known:

- Environment name: `________________`
- Can create apps: `Yes / No`
- Can create flows: `Yes / No`

## 3. SharePoint access

Confirm you have access to a SharePoint site where the first list can live.

Record the answers here once known:

- SharePoint site name: `________________`
- SharePoint site URL: `________________`
- Can create lists: `Yes / No`
- Can other users access the site: `Yes / No`

If you cannot create lists yourself, ask the site owner to create one using the schema in `docs/sharepoint-list-schema.md`.

## 4. Connections and permissions

The first project should use only standard Microsoft connections:

- `SharePoint`
- `Office 365 Outlook`
- `Microsoft Teams` (optional)
- `Approvals`

Before building, confirm:

- you can create a SharePoint connection
- you can send approval emails
- you can use Teams notifications if needed

## 5. Starter build checklist

Complete these steps in order:

- [ ] Open Power Apps and confirm environment access
- [ ] Open Power Automate and confirm environment access
- [ ] Confirm SharePoint site and list permissions
- [ ] Create the SharePoint list
- [ ] Build and save the approval flow
- [ ] Test the flow with a manual list item
- [ ] Build the canvas app
- [ ] Submit a request from the app
- [ ] Confirm approval updates the SharePoint item
- [ ] Confirm requester receives notification

## 6. Basic governance notes

Before sharing with real users, capture these details:

- App owner: `________________`
- Flow owner: `________________`
- Backup owner: `________________`
- Test users: `________________`
- Manager approver: `________________`

## 7. What not to do yet

Avoid these in the first version:

- direct `SAP Business One` integration
- premium connectors unless approved by IT
- complex multi-stage approvals
- large numbers of screens
- multiple data sources

Keep version one small and easy to troubleshoot.
