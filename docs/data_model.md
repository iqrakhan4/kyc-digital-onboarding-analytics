# Analytical Data Model

## Decision summary

| Dataset role | Extract | Grain | Used for |
|---|---|---|---|
| **Primary fact** | March onboarding transactions | one row per transaction (191,524 unique IDs) | All funnel, drop-off, platform, timing and trend analysis |
| Reconciliation | February API events | one row per API event (many per transaction) | Coverage checks only |
| Reconciliation | February successful transactions | one row per successful transaction | Coverage checks only |
| Reconciliation | February document-verification events | one row per event; probably truncated | Coverage checks only |
| Reconciliation | February missing / remaining event extracts | one row per event | Understanding extract overlap |

**Why the March extract is primary:** it is the only extract with exactly one validated row
per transaction, a status for every record, and the fields (stage, platform, timing) needed
to explain outcomes.

**Why February extracts are not combined with it:** only 0% to 4.5% of March
transaction IDs appear in any February extract (see the reconciliation heatmap), the periods differ, and API-event
rows are at a different grain. Joining event rows to transaction rows would multiply
transaction counts.

## Grain rules

- **Transaction level:** one row per `transaction_id`. Counts of rows = counts of transactions.
- **Event level:** many rows per transaction. Never count event rows as transactions.
- Overlapping extracts are **never added together** to compute volumes.

## Analytical table: `onboarding_transactions`

Defined in `sql/schema/01_create_onboarding_transactions.sql`.

| Column | Type | Notes |
|---|---|---|
| transaction_id | TEXT, primary key | Validated unique, never exported |
| status | TEXT, not null | One of 8 expected values (CHECK constraint) |
| source | TEXT, not null | Event type that produced the final status |
| platform | TEXT, not null | Normalised; `missing` when absent |
| sdk_version | TEXT | |
| stage | TEXT | Generic stage label (see methodology) |
| created_date | TEXT | `YYYY-MM-DD` as recorded |
| created_hour | INTEGER | 0-23 as recorded |
| time_spent_seconds | REAL | NULL when missing or an outlier |
| total_transaction_updates | INTEGER | Separators removed |

View `vw_onboarding_outcomes` adds `outcome_group`, `is_approved` and `is_declined`, so the
status-to-outcome rules exist in exactly one place.

## Source semantics

| `source` value | Meaning (inferred) | Rows | Typical statuses |
|---|---|---:|---|
| createForRequest | Transaction created, no later event | 36,562 | started |
| finishTransaction | Journey finished by the system | 131,005 | approved, declined, cancelled, error |
| application-update-by-agent | Decision made by a human agent | 23,957 | manually approved / declined |

## Exclusions and decisions

| Item | Decision | Reason |
|---|---|---|
| Journeys > 60 minutes | Excluded from timing only | Timing artefacts; the transaction still counts in outcomes |
| `review_decision_reasons`, `country`, `error` | Not analysed | 99.5% to 100% empty |
| Raw request/response payload columns | Never loaded | Sensitive; not needed |
| Remaining-events extract | Excluded | 100% duplicate of IDs in the main API extract |
| Missing-events extract | Held separately | Partly new coverage; role undefined |
