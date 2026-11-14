# Data Dictionary — KYC & Digital Onboarding Funnel Analytics

## 1. Project Overview

This project analyses anonymised digital KYC and onboarding datasets to
understand transaction outcomes, verification activity, API performance,
customer drop-offs and operational patterns.

The source data consists of transaction records, API event logs,
document-verification activity, OCR events and face-matching events.

Company names, product names, internal identifiers and original source
filenames have intentionally been excluded from this public documentation.

The dataset descriptions below are based on technical profiling and
initial investigation. Business definitions that have not been verified
are explicitly treated as provisional.

## 2. Dataset Inventory

The project contains 14 source extracts.

| ID | Public dataset name | Rows | Data type | Analytical purpose |
|---|---|---:|---|---|
| D01 | December Successful Transactions | 124,586 | Transaction records | Examine successful transaction outcomes and attempt counts |
| D02 | Client A — API Response Logs | 9,927 | API logs | Investigate API responses, HTTP status codes and request/response patterns |
| D03 | Client A — API Request and Response Logs | 10,485 | API logs | Examine API request metadata, response payloads and transaction references |
| D04 | February — Digital Document Verification Events | 1,048,575 | API/event logs | Investigate document-verification activity and event coverage |
| D05 | February — General API Event Logs | 459,211 | API/event logs | Analyse API activity, status codes, modules and transaction-level event patterns |
| D06 | February — Successful Transactions | 114,464 | Transaction records | Examine successful outcomes and transaction attempts |
| D07 | Client B — OCR API Events (Extract 1) | 79,790 | API logs | Investigate OCR request activity, response status and response time |
| D08 | Client B — OCR API Events (Extract 2) | 59,714 | API logs | Examine additional OCR API request activity |
| D09 | Client B — Face-Matching API Events | 47,731 | API logs | Investigate face-matching API activity and response performance |
| D10 | February — Missing API Event Records | 14,392 | API/event records | Investigate event records that are not fully represented in another extract |
| D11 | February — Remaining API Event Records | 22,863 | API/event records | Investigate additional API events and their relationship with the main event extract |
| D12 | March — Onboarding Transactions | 191,524 | Transaction records | Analyse onboarding outcomes, workflow progression and failure-related attributes |
| D13 | Additional Transaction Extract | 43,230 | Transaction records | Provide supplementary transaction-level records for investigation |
| D14 | Additional API Event Extract | 38,780 | API/event logs | Examine request metadata, response status, event timestamps and API performance |

**Important notes**

- Client A and Client B are anonymised labels. They do not disclose the
  original organisations.
- Digital Document Verification Events refer to document retrieval
  and verification activity. The original product/service name is not
  disclosed in this public document.
- Dataset IDs are documentation references, not source-system IDs.
- The row counts represent the profiled source extracts, not necessarily
  unique transactions or complete business populations.

## 3. Understanding the Dataset Types

### 3.1 Transaction-level datasets

Transaction-level datasets represent onboarding or verification journeys.
They contain attributes such as transaction identifiers, statuses,
creation timestamps and transaction start timestamps.

Examples:
- December Successful Transactions
- February Successful Transactions
- March Onboarding Transactions
- Additional Transaction Extract

These datasets are useful for:
- Approval and decline analysis
- Transaction outcome distribution
- Onboarding funnel analysis
- Attempt-count analysis
- Transaction duration analysis, where timestamp definitions are verified

A transaction-level record should not automatically be assumed to
represent a unique customer.

### 3.2 API-event-level datasets

API-event datasets capture individual requests, responses or processing
events associated with onboarding activities.

Examples:
- General API Event Logs
- Digital Document Verification Events
- OCR API Events
- Face-Matching API Events
- API Request and Response Logs

A single transaction can generate multiple API events. Consequently,
the number of API rows must not be interpreted as the number of
transactions or customers.

These datasets are useful for:
- API response status analysis
- Verification-module activity
- Request and response performance
- Event coverage and missing-event investigation
- Retry and repeated-event analysis

### 3.3 Supplementary and reconciliation datasets

Some extracts appear to contain missing, remaining or supplementary
records from other API datasets.

They are being retained separately until their extraction logic,
coverage and relationship to the main datasets are verified.

They should not be combined with other extracts simply because their
column structures or transaction identifiers look similar.

## 4. Column-Level Data Dictionary

The profiling script classified 102 columns across the 14 datasets
into the following probable roles.

| Column role | Number of columns | Description |
|---|---:|---|
| Timestamp | 25 | Date and time attributes |
| Identifier | 24 | Transaction, application, request and module references |
| Status or category | 20 | Workflow statuses, response codes and categorical attributes |
| Other | 18 | Attributes requiring additional business interpretation |
| Payload or API data | 8 | Request and response content |
| Metric | 7 | Counts, attempts, durations and response-time measurements |
| **Total** | **102** | |

These classifications are automated inferences based on field names
and technical patterns. They are not confirmed business definitions.

### 4.1 Identifier fields

Examples:
- transaction_id
- app_id
- workflow_id
- request_id
- module_id
- id

Potential uses:
- Identifying records
- Connecting transaction and API-event data
- Investigating repeated events
- Reconciling extracts

A field's presence in multiple datasets does not prove that it has
identical semantics or uniqueness guarantees in every dataset.

### 4.2 Timestamp fields

Examples:
- created_at
- event_time
- transaction_start_timestamp
- @timestamp

Potential uses:
- Transaction volume trends
- Event sequencing
- Processing-time analysis
- Time-based reconciliation

These fields may represent different lifecycle events. Their precise
definitions and timezone conventions must be verified before calculating
durations or ordering events.

### 4.3 Status and categorical fields

Examples:
- status
- status_code
- res.statusCode
- latest_condition
- last_executed_module
- platform
- failure_reason
- failure_condition

Potential uses:
- Business outcome distribution
- API response analysis
- Workflow-stage analysis
- Failure categorisation

An HTTP response status is not equivalent to a business outcome.
For example, an HTTP 200 response does not independently establish
that a transaction was approved.

### 4.4 Metric fields

Examples:
- attempt_number
- responseTime
- response_time
- time_spent
- total_transaction_updates

Potential uses:
- Attempt and retry analysis
- API response-time analysis
- Transaction-duration analysis
- Workflow activity analysis

The units, calculation methods and business definitions of these
metrics must be verified before comparing or aggregating them.

### 4.5 API payload fields

Examples:
- req.bodyStr
- res.bodyStr

These fields may contain request and response payloads. They can include
sensitive operational or personal information and are excluded from
public datasets and documentation.

## 5. Data Quality Assessment

Initial profiling identified the following observations.

### 5.1 Dataset size and completeness

| Dataset | Observation |
|---|---|
| February — General API Event Logs | 459,211 rows and 142,634 unique transaction IDs |
| February — Successful Transactions | 114,464 rows and 114,396 unique transaction IDs |
| February — Digital Document Verification Events | 1,048,575 rows and 186,387 unique transaction IDs |
| March — Onboarding Transactions | 191,524 rows and 191,524 unique transaction IDs |
| February — Missing API Event Records | 14,392 rows and 3,357 unique transaction IDs |
| February — Remaining API Event Records | 22,863 rows and 7,785 unique transaction IDs |

### 5.2 Potentially incomplete extract

The February Digital Document Verification Events extract contains
exactly 1,048,575 data rows.

This is the maximum number of data rows supported by an Excel worksheet
with one header row. The extract may have been truncated during export.

Its completeness must be verified before using it as a complete
representation of document-verification activity.

### 5.3 Missing values in March onboarding data

The following fields have substantial missingness:

| Column | Missing percentage |
|---|---:|
| review_decision_reasons | 100.00% |
| country | 99.82% |
| error | 99.53% |
| failure_reason | 96.72% |
| failure_condition | 96.72% |
| latest_condition | 35.53% |
| last_executed_module | 32.61% |
| time_spent | 31.60% |
| platform | 17.91% |

Missingness must be interpreted in the context of the field.

For example, failure-related attributes may only be populated for
transactions that encountered a failure. They should not automatically
be removed from the analytical dataset.

### 5.4 Other observations

- The additional API event extract has entirely missing workflow_id
  and module_id columns.
- Some event datasets contain repeated transaction IDs. These may
  represent multiple events belonging to the same transaction.
- The February API event extract contains 24 exact duplicate rows.
- The February Digital Document Verification Events extract contains
  211,891 duplicate rows according to the initial profiling method.
  These require further investigation before removal.
- The technical profiler identified 40 potentially sensitive columns
  across the 14 datasets.

## 6. Transaction Reconciliation Findings

Transaction-level reconciliation was performed to understand how
selected extracts overlap.

| Dataset comparison | Shared transaction IDs |
|---|---:|
| February API Events vs February Digital Document Verification Events | 141,344 |
| February API Events vs February Successful Transactions | 114,218 |
| February Successful Transactions vs Digital Document Verification Events | 113,217 |
| February API Events vs Remaining API Event Records | 7,785 |
| February API Events vs Missing API Event Records | 2,067 |
| February Missing API Event Records vs Digital Document Verification Events | 3,279 |
| February Digital Document Verification Events vs March Onboarding Transactions | 8,684 |

Additional findings:

- All 7,785 unique transaction IDs in the Remaining API Event Records
  extract are present in the February API Event Logs extract.
- The API records absent from the digital document verification extract
  and the missing-event records absent from the main API extract form
  completely separate transaction-ID groups, despite having equal
  unique-ID counts of 1,290.
- The February digital document verification and March onboarding
  datasets share 8,684 transaction IDs.
- The March creation timestamps are later than the corresponding
  first-event timestamps for all 8,684 shared IDs.

These are record-level observations, not proof of a specific business
workflow or transaction lifecycle.

Overlapping extracts must not be added together to calculate transaction
volumes. Joins and KPI calculations require validated dataset grain,
date semantics and source definitions.

## 7. Privacy and Public Data Handling

The original source extracts are private working data.

The following must not be committed to the public repository:

- Original source CSV files
- Company or customer identifiers that have not been authorised for disclosure
- Transaction, application, request or workflow identifiers
- Raw request and response payloads
- Personal or financial information
- Internal URLs, endpoints or operational configuration
- Screenshots containing identifiable source records

Public demonstrations, sample datasets and dashboards should use
synthetic or appropriately anonymised data.

The automated potentially_sensitive classification is a warning
mechanism, not a complete privacy assessment. A column not flagged
by the profiler is not guaranteed to be safe for publication.

## 8. Open Questions Before Analytical Modelling

The following items require further validation:

1. What are the exact business definitions of each transaction status?
2. What do created_at, event_time and transaction_start_timestamp
   represent in each source system?
3. What is the expected relationship between transaction_id, app_id,
   request_id and workflow_id?
4. Do the API extracts represent complete event coverage or selected
   endpoints and modules?
5. Is the digital document verification extract complete?
6. Are response-time measurements recorded in milliseconds, seconds
   or another unit?
7. What are the approved definitions of approval, decline, cancellation,
   failure and customer drop-off?
8. How should repeated API events and retries be distinguished from
   duplicate records?

These questions will guide the next stage: defining the analytical
data model and validating the relationships between datasets.

## 9. Profiling Methodology

The technical inventory was generated using:

`src/preprocessing/build_data_dictionary.py`

The script processes CSV files in chunks and generates column-level
metadata and aggregate statistics without exporting raw field values.

The generated technical inventory is stored locally at:

`data/processed/data_dictionary_technical.csv`

The generated inventory is excluded from Git. This Markdown document
contains the reviewed, public-facing summary of the profiling work.
