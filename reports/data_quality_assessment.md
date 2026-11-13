# Data Quality Assessment

## 1. Overview

An initial assessment was performed on the available digital
onboarding and verification datasets.

The objective was to understand dataset structure, missing values,
duplicate records, identifier uniqueness and timestamp quality
before developing the analytical data model.

## 2. Key Findings

### Missing Values

The onboarding transaction extract contains several sparsely
populated attributes, including failure reasons, failure
conditions and error details.

These fields will be retained for conditional analysis rather
than removed based solely on missing-value percentages.

Some attributes, including review decision reasons and country,
were entirely or almost entirely unpopulated.

### Duplicate Records

Verification event datasets contain repeated transaction
identifiers.

These repetitions may represent multiple verification events
or attempts associated with a single onboarding transaction.

Therefore, transaction identifier repetition will not
automatically be treated as duplicate data.

### Identifier Uniqueness

The onboarding transaction extract contains 191,524 records
with 191,524 distinct transaction identifiers.

The February verification API extract contains 459,211
events associated with 142,634 distinct transaction identifiers.

This suggests a potential one-to-many relationship between
onboarding transactions and verification events.

This relationship requires further validation.

### Dataset Completeness

One verification extract contains exactly 1,048,575 data rows,
which corresponds to the maximum number of data rows supported
by an Excel worksheet.

The extract may therefore be truncated and will not be treated
as a complete event population.

### Timestamp Quality

Initial profiling identified suspicious parsed dates in
duration and numeric fields.

The timestamp profiling logic is being refined to distinguish
actual timestamps from response durations and transaction
counters.

Mixed timestamp formats will also be investigated.

## 3. Data Quality Decisions

| Issue | Planned action |
|---|---|
| Sparse failure attributes | Retain for conditional analysis |
| Entirely missing columns | Exclude from analytical model unless required later |
| Repeated transaction IDs in event data | Preserve legitimate event records |
| Exact duplicate event rows | Investigate before removal |
| Potentially truncated exports | Exclude from complete-population analysis |
| Mixed timestamp formats | Standardise after validation |
| Missing platform values | Investigate and categorise as unknown where appropriate |

## 4. Next Steps

1. Validate timestamp formats and date ranges.
2. Investigate exact duplicate event records.
3. Validate transaction identifier relationships.
4. Identify overlapping and potentially redundant extracts.
5. Define the final analytical datasets.
6. Develop the preprocessing pipeline.

## 5. Privacy

Original operational extracts are maintained outside the
public repository.

Only approved synthetic or appropriately anonymised
datasets will be used in the public project.
