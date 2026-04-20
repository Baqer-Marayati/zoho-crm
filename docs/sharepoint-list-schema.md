# SharePoint List Schema

Create one SharePoint list named `Requests`.

This list is the first datastore for both the canvas app and the approval flow.

## Why SharePoint first

For a first project, SharePoint is easier than `Dataverse` or `SAP Business One` because:

- it is already part of many Microsoft 365 environments
- it works well with both Power Apps and Power Automate
- it needs less setup for a beginner

## Recommended columns

Use the default `Title` column and add the following columns.

| Column | Type | Required | Example | Purpose |
|---|---|---|---|---|
| `Title` | Single line of text | Yes | `Printer toner request` | Short request subject |
| `Description` | Multiple lines of text | No | `Need toner for main office printer` | Longer request details |
| `RequestType` | Choice | Yes | `Supplies` | Simple grouping for requests |
| `RequestedByName` | Single line of text | Yes | `Baqer Ali` | Display name from the app |
| `RequestedByEmail` | Single line of text | Yes | `name@company.com` | Used for confirmation and filtering |
| `ManagerEmail` | Single line of text | Yes | `manager@company.com` | Approver email used by the flow |
| `Status` | Choice | Yes | `Submitted` | Current request state |
| `ManagerComment` | Multiple lines of text | No | `Approved for this month` | Decision note written by the flow |
| `SubmittedAt` | Date and time | Yes | current date and time | Submission timestamp |
| `DecisionAt` | Date and time | No | current date and time | Filled when approval ends |

## Choice values

### RequestType

Start with a short list:

- `Supplies`
- `IT`
- `Finance`
- `Other`

### Status

Use these values:

- `Submitted`
- `Pending Approval`
- `Approved`
- `Rejected`

For the first version, the app can write `Submitted`, and the flow can move it to `Pending Approval` and then to the final result.

## SharePoint creation steps

1. Open the SharePoint site you selected.
2. Create a new list named `Requests`.
3. Keep the default `Title` column.
4. Add each custom column from the table above.
5. For `Status`, set the default value to `Submitted`.
6. For `ManagerComment` and `DecisionAt`, allow blank values.

## Notes for Power Apps

These defaults make the app easier to build:

- `RequestedByName` default: `User().FullName`
- `RequestedByEmail` default: `User().Email`
- `Status` default: `Submitted`
- `SubmittedAt` default: `Now()`

## Notes for Power Automate

The flow will typically:

1. read `ManagerEmail`
2. send the approval
3. update `Status`
4. write `ManagerComment`
5. write `DecisionAt`

## Version one rules

Keep the list simple:

- do not create extra lookup tables yet
- do not add attachments yet
- do not add SAP fields yet
- do not add dozens of request types yet

You can expand the schema after the first approval loop is working.
