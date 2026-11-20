-- ---------------------------------------------------------------------------
-- Adds business-friendly outcome groupings to every transaction.
-- Keeps the status-to-outcome rules in ONE place for all downstream queries.
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS vw_onboarding_outcomes;

CREATE VIEW vw_onboarding_outcomes AS
SELECT
    t.*,
    CASE
        WHEN status IN ('auto_approved', 'manually_approved') THEN 'Approved'
        WHEN status IN ('auto_declined', 'manually_declined') THEN 'Declined'
        WHEN status = 'user_cancelled'                        THEN 'Cancelled by user'
        WHEN status = 'started'                               THEN 'No completion recorded'
        ELSE 'Error / needs review'
    END AS outcome_group,
    CASE WHEN status IN ('auto_approved', 'manually_approved') THEN 1 ELSE 0 END AS is_approved,
    CASE WHEN status IN ('auto_declined', 'manually_declined') THEN 1 ELSE 0 END AS is_declined
FROM onboarding_transactions AS t;
