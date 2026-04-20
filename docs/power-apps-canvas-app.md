# Power Apps Canvas App

This guide builds the first app for the project.

## Goal

Create a simple canvas app where the user can:

1. submit a new request
2. save it into the SharePoint `Requests` list
3. view their previous requests and statuses

## App type

Use a `Canvas app`.

If you are unsure whether to choose phone or tablet, start with:

- `Phone layout`

It keeps the first version smaller and easier to understand.

## Data source

Connect the app to the SharePoint list:

- site: your chosen SharePoint site
- list: `Requests`

Rename the connection in your mind as `Requests` and keep it consistent across the app.

## Recommended screens

Create these screens:

- `scrHome`
- `scrSubmitRequest`
- `scrMyRequests`

## Screen 1: Home

Add:

- title label: `Request Portal`
- button: `New Request`
- button: `My Requests`

Set button navigation:

```powerfx
Navigate(scrSubmitRequest, ScreenTransition.Fade)
```

```powerfx
Navigate(scrMyRequests, ScreenTransition.Fade)
```

## Screen 2: Submit request

Add an `Edit form` connected to the `Requests` SharePoint list.

Name it:

- `frmRequest`

Set:

- `DataSource`: `Requests`
- `DefaultMode`: `FormMode.New`

### Recommended form fields

Show these cards:

- `Title`
- `Description`
- `RequestType`
- `RequestedByName`
- `RequestedByEmail`
- `ManagerEmail`
- `Status`
- `SubmittedAt`

Hide these cards in the first version:

- `ManagerComment`
- `DecisionAt`

### Default values for beginner-friendly automation

Use defaults so the user does not need to fill system fields manually.

For the card or input backing `RequestedByName`, set the default to:

```powerfx
User().FullName
```

For `RequestedByEmail`, set the default to:

```powerfx
User().Email
```

For `Status`, set the default to:

```powerfx
"Submitted"
```

For `SubmittedAt`, set the default to:

```powerfx
Now()
```

### Submit button

Add a button labeled `Submit Request`.

Set `OnSelect` to:

```powerfx
SubmitForm(frmRequest)
```

### Form success behavior

Set `frmRequest.OnSuccess` to:

```powerfx
Notify(
    "Request submitted. The approval flow has started.",
    NotificationType.Success
);
ResetForm(frmRequest);
Navigate(scrMyRequests, ScreenTransition.Fade)
```

### Form failure behavior

Set `frmRequest.OnFailure` to:

```powerfx
Notify(
    "The request could not be submitted. Please try again.",
    NotificationType.Error
)
```

## Screen 3: My requests

Add a vertical gallery and connect it to the same list.

Set the gallery `Items` property to:

```powerfx
SortByColumns(
    Filter(
        Requests,
        RequestedByEmail = User().Email
    ),
    "Created",
    SortOrder.Descending
)
```

Inside the gallery, show:

- `Title`
- `Status`
- `RequestType`
- `SubmittedAt`
- `ManagerComment`

This gives the user a basic request history without building an admin screen yet.

## Useful design tips

Keep the first app clean and obvious:

- one primary action per screen
- short labels
- clear status badges or colored text
- no complex formulas unless necessary

## Test steps

Test in this order:

1. Open the app.
2. Create a request with a real manager email.
3. Submit the form.
4. Confirm a new row appears in SharePoint.
5. Confirm the approval flow starts.
6. Approve or reject the request.
7. Return to `My Requests` and confirm the status updates.

## Common beginner issues

### Submit button does nothing

Check:

- the form is connected to the correct data source
- required fields are filled
- the button uses `SubmitForm(frmRequest)`

### User fields are blank

Check:

- the default value is set on the correct input or data card
- the app is running under a signed-in work account

### Gallery shows nothing

Check:

- `RequestedByEmail` is being saved correctly
- the gallery formula points to the correct list

### Flow never triggers after app submit

Check:

- the form created a new row
- the flow is listening to the same SharePoint list
- the app wrote the manager email correctly

## Version two ideas

Once version one works, consider:

- request detail screen
- manager-only approval dashboard
- file attachments
- conditional fields by request type
- Teams deep links back to the request
