-- ---------------------------------------------------------------------------
-- Analytical table: one row per onboarding transaction.
--
-- Grain        : one row per transaction_id (validated unique).
-- Source       : cleaned transaction-level extract (see docs/data_model.md).
-- Portability  : plain ANSI types; runs on SQLite (used by the pipeline) and
--                is written to be PostgreSQL-compatible.
-- ---------------------------------------------------------------------------
DROP VIEW  IF EXISTS vw_onboarding_outcomes;
DROP TABLE IF EXISTS onboarding_transactions;

CREATE TABLE onboarding_transactions (
    transaction_id             TEXT    PRIMARY KEY,
    status                     TEXT    NOT NULL,
    source                     TEXT    NOT NULL,
    platform                   TEXT    NOT NULL,   -- normalised; 'missing' if absent
    sdk_version                TEXT,
    stage                      TEXT,               -- generic stage label
    created_date               TEXT,               -- YYYY-MM-DD as recorded
    created_hour               INTEGER,
    time_spent_seconds         REAL,               -- NULL when missing / outlier
    total_transaction_updates  INTEGER,
    CHECK (status IN (
        'auto_approved', 'manually_approved',
        'auto_declined', 'manually_declined',
        'user_cancelled', 'started', 'error', 'needs_review'
    ))
);

CREATE INDEX idx_onboarding_status   ON onboarding_transactions (status);
CREATE INDEX idx_onboarding_platform ON onboarding_transactions (platform);
CREATE INDEX idx_onboarding_date     ON onboarding_transactions (created_date);
