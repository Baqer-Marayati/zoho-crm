# Power Automate Approval Flow

This guide builds the first cloud flow for the project.

## Goal

When a new request is created in the SharePoint `Requests` list:

1. start an approval
2. wait for the manager response
3. update the same SharePoint item
4. notify the requester

## Flow name

Use a clear name such as:

- `Request Approval - SharePoint`

## Before you begin

Make sure these are ready:

- SharePoint list `Requests` exists
- `ManagerEmail` column exists
- `RequestedByEmail` column exists
- `Status` column exists

## Build steps

### 1. Create the flow

1. Open [Power Automate](https://make.powerautomate.com).
2. Select the correct environment.
3. Choose `Create`.
4. Choose `Automated cloud flow`.
5. Name it `Request Approval - SharePoint`.
6. Use the trigger `When an item is created` from `SharePoint`.

### 2. Configure the trigger

Set:

- `Site Address`: your SharePoint site
- `List Name`: `Requests`

## 3. Update the item to show approval has started

Add action: `Update item` from SharePoint.

Use:

- same `Site Address`
- same `List Name`
- `Id`: `ID` from the trigger
- `Title`: `Title` from the trigger
- `Description`: `Description` from the trigger
- `RequestType`: `RequestType` from the trigger
- `RequestedByName`: `RequestedByName` from the trigger
- `RequestedByEmail`: `RequestedByEmail` from the trigger
- `ManagerEmail`: `ManagerEmail` from the trigger
- `SubmittedAt`: `SubmittedAt` from the trigger
- `Status`: `Pending Approval`

This makes the current state visible in SharePoint before the approval result comes back.

## 4. Start the approval

Add action: `Start and wait for an approval`.

Recommended settings:

- `Approval type`: `Approve/Reject - First to respond`
- `Title`: `New request: @{triggerOutputs()?['body/Title']}`
- `Assigned to`: `ManagerEmail` from the trigger
- `Details`: include `Title`, `Description`, `RequestType`, and `RequestedByName`

If your company prefers Teams approvals, this same approval can still appear in Teams while the flow stays the same.

## 5. Handle the outcome

Add a `Condition` after the approval.

Check whether:

- approval `Outcome` is equal to `Approve`

### If yes

Add `Update item` and set:

- `Status`: `Approved`
- `ManagerComment`: approval `Comments`
- `DecisionAt`: `utcNow()`

Make sure all the other fields are also filled from the trigger or earlier steps, because SharePoint `Update item` overwrites the full row.

Then add `Send an email (V2)`:

- `To`: `RequestedByEmail`
- `Subject`: `Your request was approved`
- `Body`: include the request title and manager comment

Optional: also add a Teams message action.

### If no

Add another `Update item` and set:

- `Status`: `Rejected`
- `ManagerComment`: approval `Comments`
- `DecisionAt`: `utcNow()`

Then add `Send an email (V2)`:

- `To`: `RequestedByEmail`
- `Subject`: `Your request was rejected`
- `Body`: include the request title and manager comment

## 6. Save and test

Test the flow with a real SharePoint item:

1. Create a new item in the `Requests` list manually.
2. Set `ManagerEmail` to a real approver address.
3. Save the item.
4. Watch the flow run history.
5. Approve or reject the request.
6. Confirm the SharePoint item updates correctly.
7. Confirm the requester email arrives.

## Suggested details text

Use a readable approval message, for example:

```text
Request title: Title
Request type: RequestType
Requested by: RequestedByName
Description: Description
```

Build the same layout using dynamic content in the approval action.

## Common beginner issues

### The flow does not trigger

Check:

- correct environment
- correct SharePoint site
- correct list
- the item was newly created, not just edited

### The approval is sent to nobody

Check:

- `ManagerEmail` contains a valid email address
- the field value is not blank

### The SharePoint item loses data after update

This usually means the `Update item` action did not map all fields. Refill every important column, not only the one you changed.

### The requester never gets the result

Check:

- `RequestedByEmail` was captured by the app
- the email action uses the correct dynamic content

## Version two ideas

After version one works, you can add:

- attachments
- more request types
- escalation reminders
- Teams adaptive cards
- a separate approver view in Power Apps
