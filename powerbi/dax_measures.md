# DAX Measures

Create these in a dedicated **`_Measures`** table (Home > Enter data > name it `_Measures`,
then delete the placeholder column) so they stay together in the Fields pane.

Table and column names match the files exported by `make export-powerbi`
(see [README.md](README.md#2-load-the-data)).

> **Status:** written to the Power BI / DAX documentation and checked by reasoning against the
> exported tables. They have **not** been executed in Power BI Desktop by the author of this
> repository. Use the [validation checklist](README.md#5-validate-the-numbers) to confirm them.

---

## Volume and outcomes

```dax
Total Attempts =
SUM ( fact_onboarding[transactions] )
```

```dax
Approved =
CALCULATE ( [Total Attempts], dim_status[is_approved] = 1 )
```

```dax
Declined =
CALCULATE ( [Total Attempts], dim_status[is_declined] = 1 )
```

```dax
Cancelled =
CALCULATE ( [Total Attempts], dim_status[status] = "user_cancelled" )
```

```dax
No Completion =
CALCULATE ( [Total Attempts], dim_status[status] = "started" )
```

```dax
Errors and Review =
CALCULATE ( [Total Attempts], dim_status[status] IN { "error", "needs_review" } )
```

```dax
Decided = [Approved] + [Declined]
```

## Rates

```dax
Approval Share = DIVIDE ( [Approved], [Total Attempts] )
```

```dax
Approval Rate (Decided) = DIVIDE ( [Approved], [Decided] )
```

```dax
Cancellation Share = DIVIDE ( [Cancelled], [Total Attempts] )
```

```dax
No Decision Share =
DIVIDE ( [Cancelled] + [No Completion] + [Errors and Review], [Total Attempts] )
```

Set the four rate measures to **Percentage** with 1 decimal place.

> **Which approval rate?** `Approval Share` divides by *all* attempts; `Approval Rate (Decided)`
> divides by attempts that reached a decision. They answer different questions. Always label which
> one a visual shows.

## Manual review

```dax
Manual Decisions =
CALCULATE ( [Total Attempts], fact_onboarding[source] = "application-update-by-agent" )
```

```dax
Manual Review Share = DIVIDE ( [Manual Decisions], [Total Attempts] )
```

```dax
Manual Approval Rate =
DIVIDE (
    CALCULATE ( [Manual Decisions], dim_status[status] = "manually_approved" ),
    [Manual Decisions]
)
```

## Platform and drop-off

Platform rates use **only `finishTransaction` records**, because "started" and agent-updated records
do not describe a user ending their journey (see `docs/methodology.md`).

```dax
Finished Attempts =
CALCULATE ( [Total Attempts], fact_onboarding[source] = "finishTransaction" )
```

```dax
Finished Cancellation Rate =
DIVIDE (
    CALCULATE ( [Cancelled], fact_onboarding[source] = "finishTransaction" ),
    [Finished Attempts]
)
```

```dax
Cancellation Share by Stage =
DIVIDE (
    [Cancelled],
    CALCULATE ( [Cancelled], ALL ( dim_stage ) )
)
```

`ALL ( dim_stage )` removes only the stage filter, so slicers (platform, SDK, dates) still apply.

## Timing

```dax
Avg Journey (min) =
DIVIDE (
    SUM ( fact_onboarding[time_spent_sum_seconds] ),
    SUM ( fact_onboarding[time_spent_count] )
) / 60
```

This is a **mean**. Medians cannot be computed from pre-aggregated data. The documented medians
(for example approved ~3.1 min) come from `docs`/`reports`, and the mean is higher because the
distribution is right-skewed. Use the duration-band chart to show the distribution instead.

## Time patterns

```dax
Avg Attempts per Day =
DIVIDE ( [Total Attempts], DISTINCTCOUNT ( dim_date[date] ) )
```

Use in the weekday x hour matrix. `dim_date` is filtered by weekday only (relationship direction is
date -> fact), so the denominator is the number of that weekday in the period.

```dax
Attempts 7-Day Avg =
AVERAGEX (
    DATESINPERIOD ( dim_date[date], MAX ( dim_date[date] ), -7, DAY ),
    [Total Attempts]
)
```

Requires `dim_date` to be marked as a date table. The first six days average over fewer than 7 days.

## Optional: dynamic card subtitle

```dax
Headline Subtitle =
FORMAT ( [Approval Rate (Decided)], "0.0%" ) & " of decided cases are approved"
```
