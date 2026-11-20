# Methodology

How the analysis is built, which definitions it uses, and what it assumes.

## 1. Pipeline

```text
data/raw (private CSVs)
   |
   v
load + validate  ------ fails loudly on: missing columns, missing/duplicate IDs,
   |                    missing status/source, unexpected status values
   v
clean + enrich   ------ parse timestamps, parse numbers, flag outliers,
   |                    map raw modules to generic stage labels
   v
aggregate        ------ pandas summaries (CSV)  <---- cross-checked ---->  SQL queries (SQLite)
   |
   v
charts (reports/figures)  +  documentation
```

Run it with `make real` (private data) or `make demo` (synthetic data).

## 2. Validation rules (fail-fast)

The loader refuses to continue, rather than producing a misleading result, when:

| Condition | Why it matters |
|---|---|
| A required column is missing | Metrics would silently be wrong |
| A transaction ID is missing | Records cannot be reconciled |
| A transaction ID is duplicated | Counts would be inflated; grain is one row per transaction |
| Status or source is missing | Grouping would drop or mislabel records |
| A status outside the expected set appears | KPI definitions assume a known set of outcomes |

These rules are covered by automated tests.

## 3. Metric definitions

| Metric | Definition |
|---|---|
| Approval share (all) | (auto + manually approved) / all transactions |
| Approval rate (decided) | approved / (approved + declined). Excludes cancelled, started and error |
| Cancellation share | `user_cancelled` / all transactions |
| No completion | `started`: a creation record with no later outcome in the extract |
| Platform cancellation rate | cancelled / all `finishTransaction` records for that platform |
| Stage drop-off | distribution of the *last executed module* for cancelled transactions |
| Journey duration | `time_spent`, converted to seconds; > 60 min treated as an artefact |

**Why platform rates use `finishTransaction` only:** `started` records never reached a
finish event and agent-updated records are decisions made by staff. Including them would
dilute the cancellation rate with records where the user did not end the journey.

## 4. Outcome grouping

| Raw status | Outcome group |
|---|---|
| auto_approved, manually_approved | Approved |
| auto_declined, manually_declined | Declined |
| user_cancelled | Cancelled by user |
| started | No completion recorded |
| error, needs_review | Error / needs review |

The same grouping is implemented in Python (`OUTCOME_GROUPS`) and SQL
(`sql/views/01_vw_onboarding_outcomes.sql`).

## 5. Stage labelling

Raw `last_executed_module` values are internal identifiers and can contain provider
names. They are translated to generic labels (for example "Document verification") using
keyword rules from `config/stage_mapping.*.json`.

- `stage_mapping.example.json` is committed and generic.
- `stage_mapping.local.json` is git-ignored and may add provider-specific keywords.

## 6. SQL layer

`sql/` holds a schema, one view and six analysis queries written in portable ANSI-style
SQL. `src/database/run_sql_analysis.py` runs them on SQLite and then **asserts that the
SQL results equal the pandas results** (outcome counts, KPIs, platform cancellations and
stage drop-off). Two independent implementations of one metric agreeing is a
reconciliation control. The queries avoid vendor-specific functions so they should run on
PostgreSQL, but they have only been executed against SQLite.

## 7. Privacy approach

- Raw data, generated outputs and local configuration are git-ignored.
- Reconciliation reports counts and percentages only; identifiers are never printed or saved.
- Provider names and raw filenames live only in local configuration.
- `make check-privacy` fails if data files or local config become tracked, and optionally
  scans for terms listed in a private `config/banned_terms.local.txt`.
- Published charts contain aggregates only. Demo runs are labelled **SYNTHETIC DEMO DATA**.

## 8. Power BI export

`src/export/export_powerbi_data.py` aggregates the cleaned data into a small star schema:

| Table | Grain |
|---|---|
| `fact_onboarding` | date x hour x platform x status x source x stage x SDK x duration band (counts, duration sums) |
| `dim_date`, `dim_status`, `dim_platform`, `dim_stage` | one row per member |
| `dataset_overlap` | one row per ordered dataset pair (real data only) |

Controls: the export asserts that the cube's totals equal the source totals and that no
identifier column exists. Tests also verify referential integrity (every fact key exists in its
dimension) and emulate the DAX measure logic in pandas against the independently computed
summaries. Medians cannot be recovered from pre-aggregated data, so the dashboard shows mean
durations and duration-band distributions instead.

## 9. Assumptions (unverified)

These affect interpretation and should be confirmed with the data owner.

1. `time_spent` is in **milliseconds**. Seconds would imply multi-hour journeys.
2. Timestamps are shown as recorded; the **timezone is unknown**, so the hour-of-day
   pattern may be shifted.
3. `started` means a creation record with no finishing event. Whether the journey was
   abandoned or the event was lost cannot be determined.
4. `last_executed_module` is the last module reached, not necessarily where the user left.
5. `platform` reflects the device/OS reported by the client; its relationship to the
   SDK or web/mobile channel is unverified.
6. `total_transaction_updates` has no confirmed definition and is used only descriptively.

## 10. Limitations

- One month of data; no seasonality can be assessed.
- Observational: associations (for example platform vs cancellation) are not causal.
- No customer identifier, so repeat attempts by one person cannot be linked.
- The document-verification extract is probably truncated at 1,048,575 rows.
- No entry counts per stage, so step-level conversion rates cannot be computed.
