-- Q2. Headline KPIs.
-- 'approval_rate_among_decided' excludes cancelled / abandoned / error
-- records so that it is not distorted by journeys that never reached a decision.
SELECT
    COUNT(*)                                                         AS total_transactions,
    SUM(is_approved)                                                 AS approved_transactions,
    SUM(is_declined)                                                 AS declined_transactions,
    ROUND(100.0 * SUM(is_approved) / COUNT(*), 2)                    AS approval_share_all,
    ROUND(100.0 * SUM(is_approved) / (SUM(is_approved) + SUM(is_declined)), 2)
                                                                     AS approval_rate_among_decided,
    ROUND(100.0 * SUM(CASE WHEN status = 'user_cancelled' THEN 1 ELSE 0 END) / COUNT(*), 2)
                                                                     AS cancellation_share_all
FROM vw_onboarding_outcomes;
