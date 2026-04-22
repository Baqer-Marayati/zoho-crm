# Wire `scrCRM` to the Dataverse `Opportunity` table (~5 min in studio)

**Prerequisites**

- The Dataverse `Opportunity` table exists with at least 1 row in your Developer Environment. If not, run:
  ```bash
  ./tools/dataverse/venv/bin/python ./tools/dataverse/create_opportunity.py
  ./tools/dataverse/venv/bin/python ./tools/dataverse/seed_opportunities.py
  ```
- `scrCRM.msapp` has been imported into the same environment (`canvas-app/scrCRM/README.md`).

This doc has you:

1. Add `Opportunities` as a data source.
2. Paste a few `Power Fx` formulas to make screens read live data.
3. Save & publish.

The demo `colDemoOpps` collection still loads on `App.OnStart`; once everything works you can remove it (§5).

---

## Reference: column names you'll see in studio

The script created columns under publisher prefix `new_`. In Power Fx you reference them by their **display name** (use single quotes if the name has spaces):

| Display name | Power Fx | Type | Notes |
|---|---|---|---|
| `Name` | `Name` | text | primary name column |
| `Stage` | `Stage` | choice | local picklist `'Stage (Opportunities)'` |
| `Track` | `Track` | choice | local picklist `'Track (Opportunities)'` |
| `Amount` | `Amount` | currency | also exposes `'Amount (Base)'` |
| `Reporting Amount` | `'Reporting Amount'` | currency | |
| `Close Date` | `'Close Date'` | date-only | |
| `Probability` | `Probability` | int 0–100 | |
| `Rolling Summary` | `'Rolling Summary'` | multi-line text | |
| `Competitors` | `Competitors` | multi-line text | |
| `Owner Name` | `'Owner Name'` | text | custom **string** column (free-typed name; separate from the system `Owner` lookup which also exists) |
| `Opportunity` | `Opportunity` | guid | the primary key (Power Fx exposes it with the entity display name) |

Stage option labels (use these exactly): `Discovery`, `Qualify`, `Proposal`, `Negotiation`, `Commit`, `'Closed Won'`, `'Closed Lost'`.

Track option labels: `Industrial`, `Software`, `Service`, `Aftermarket`.

---

## 1. Open `scrCRM` in studio

1. [make.powerapps.com](https://make.powerapps.com) → top-right **Environment** picker → select **Developer Environment**.
2. **Apps** → **`scrCRM`** → click the pencil **Edit**.

---

## 2. Add the data source

1. Left rail → **Data** (cylinder icon).
2. **+ Add data** → search `Opportunities` → click it.
3. If prompted, **Connect** with your work account.
4. `Opportunities` now appears under **Data**.

That's the only step that requires the studio.

---

## 3. Paste the formulas

To set a property: in the **left tree**, click the screen → expand → click the control name. In the **formula bar**, the **left dropdown** picks the property; replace the formula text.

### 3.1 Hub KPIs — `scrHub`

`kpi1Value.Text` (open opportunities count):
```powerfx
Text(
    CountRows(
        Filter(
            Opportunities,
            Stage <> 'Stage (Opportunities)'.'Closed Won'
                && Stage <> 'Stage (Opportunities)'.'Closed Lost'
        )
    )
)
```

`kpi2Value.Text` (open pipeline $):
```powerfx
Text(
    Sum(
        Filter(
            Opportunities,
            Stage <> 'Stage (Opportunities)'.'Closed Won'
                && Stage <> 'Stage (Opportunities)'.'Closed Lost'
        ),
        Amount
    ),
    "$ #,##0"
)
```

`kpi3Value.Text` (closing in next 90 days):
```powerfx
Text(
    CountRows(
        Filter(
            Opportunities,
            'Close Date' >= Today()
                && 'Close Date' < DateAdd(Today(), 90, TimeUnit.Days)
        )
    )
)
```

### 3.2 Index rows — `scrIndex`

The current index is 5 hand-built label rows. For each row N (1..5), set the `Text` property of the corresponding label to read from the Nth opportunity:

`iRow1Name.Text`:
```powerfx
Index(Opportunities, 1).Name
```
`iRow1Stage.Text`:
```powerfx
Text(Index(Opportunities, 1).Stage)
```
`iRow1Track.Text`:
```powerfx
Text(Index(Opportunities, 1).Track)
```
`iRow1Amount.Text`:
```powerfx
Text(Index(Opportunities, 1).Amount, "$ #,##0")
```
`iRow1Owner.Text`:
```powerfx
Coalesce(Index(Opportunities, 1).'Owner Name', "—")
```
`iRow1Close.Text`:
```powerfx
Text(Index(Opportunities, 1).'Close Date', "yyyy-mm-dd")
```

`iRow1Bg.OnSelect` (navigate to the record):
```powerfx
Set(varRecordId, Index(Opportunities, 1).Opportunity);
Navigate(scrRecord, ScreenTransition.None)
```

Repeat the six `Text` formulas + `OnSelect` for **rows 2–5** by replacing `Index(Opportunities, 1)` with `Index(Opportunities, 2)` … `Index(Opportunities, 5)`. (Recommended longer-term: replace the 30 row labels with one **Vertical gallery** — see §4.)

### 3.3 Record screen — `scrRecord`

`rRecName.Text`:
```powerfx
Coalesce(LookUp(Opportunities, Opportunity = varRecordId).Name, "(missing record)")
```

`rStageBadge.Text`:
```powerfx
Text(LookUp(Opportunities, Opportunity = varRecordId).Stage)
```

`rFldOwnerValue.Text`:
```powerfx
Coalesce(LookUp(Opportunities, Opportunity = varRecordId).'Owner Name', "—")
```

`rFldTrackValue.Text`:
```powerfx
Text(LookUp(Opportunities, Opportunity = varRecordId).Track)
```

`rFldAmountValue.Text`:
```powerfx
Text(LookUp(Opportunities, Opportunity = varRecordId).Amount, "$ #,##0")
```

`rFldCloseValue.Text`:
```powerfx
Text(LookUp(Opportunities, Opportunity = varRecordId).'Close Date', "yyyy-mm-dd")
```

`rFldIdValue.Text`:
```powerfx
Text(LookUp(Opportunities, Opportunity = varRecordId).Opportunity)
```

`rRightBody.Text`:
```powerfx
Coalesce(LookUp(Opportunities, Opportunity = varRecordId).'Rolling Summary', "(no summary yet)")
```

---

## 4. Save and publish

1. Top right → **Save** (the floppy disk).
2. Top right → **Publish** → **Publish this version**.
3. Top right → **▶ Play** to test: hub → index (all 5 rows live) → click row → record page shows that row's data.

---

## 5. (Optional) Refactor index into a gallery

The 5-label-row index is fine for the demo, but a real **Vertical gallery** scales to thousands of rows and supports search/sort.

1. **scrIndex** → delete `iRow1Bg` … `iRow5Close` (all 30 row controls).
2. **+ Insert** → **Vertical gallery** at `X=264, Y=220`, `Width = Parent.Width - 280`, `Height = Parent.Height - 252`.
3. (Optional) Replace the `iSearchBox` label with a **Text input** named `iSearchInput`.
4. Gallery `Items`:
   ```powerfx
   SortByColumns(
       Filter(
           Opportunities,
           IsBlank(iSearchInput.Text) || StartsWith(Name, iSearchInput.Text)
       ),
       "new_name",
       SortOrder.Ascending
   )
   ```
5. Inside the gallery template, add labels bound to `ThisItem.Name`, `Text(ThisItem.Stage)`, `Text(ThisItem.Track)`, `Text(ThisItem.Amount, "$ #,##0")`, `ThisItem.'Owner Name'`, `Text(ThisItem.'Close Date', "yyyy-mm-dd")`.
6. Gallery `OnSelect`:
   ```powerfx
   Set(varRecordId, ThisItem.Opportunity);
   Navigate(scrRecord, ScreenTransition.None)
   ```
7. **Save** → re-export the `.msapp` (File → Save as → This computer) and place it in `canvas-app/scrCRM/seed/` so the repo's `build-msapp.sh` keeps working from the new shape.

---

## 6. Clean up demo data (after everything works)

On the **App** node, set `App.OnStart` to just:
```powerfx
Navigate(scrHub, ScreenTransition.None)
```
(Removes the `ClearCollect(colDemoOpps, …)` block; demo collection is no longer used.)

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Red squiggle on `Opportunities` | Data source not added, or studio is in the wrong environment | Re-do §2 in the env that owns `scrCRM` |
| `'Stage (Opportunities)'` invalid | Choice display name differs (someone renamed it) | Use the `Choices()` picker in studio to insert the correct path |
| Row owner shows `—` | The row's `Owner Name` (custom text column) is blank | Open the row in [make.powerapps.com](https://make.powerapps.com) → Tables → Opportunity → Data → set `Owner Name` |
| All 5 index rows look identical | `Index(Opportunities, N)` returned the same row 5× because table has fewer than N rows | Re-run `tools/dataverse/seed_opportunities.py` |
| `LookUp` returns blank on `scrRecord` | `varRecordId` was set to a demo GUID by `App.OnStart` | Click a row in `scrIndex` first; that sets `varRecordId` to a real GUID |
| Studio shows "delegation warning" yellow line | A `Filter` / `Sort` predicate Dataverse can't translate | For v1, ignore. Long-term: wrap the source in `FirstN(Opportunities, 500)` |

---

## What's next

- **Edit form** on `scrRecord` so users can save changes (`EditForm` + `SubmitForm`).
- **Other objects** (Companies, People, Leads, Tasks): repeat the same Dataverse-create + canvas-wire pattern.
- **Power Automate flows**: SharePoint folder per opportunity, weekly forecast snapshot.
