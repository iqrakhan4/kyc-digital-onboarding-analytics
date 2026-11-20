-- Q3. Cancellation rate by platform.
-- Restricted to 'finishTransaction' records: 'started' and agent-updated
-- records do not describe a user ending their journey.
SELECT
    platform,
    COUNT(*)                                                          AS finished_transactions,
    SUM(CASE WHEN status = 'user_cancelled' THEN 1 ELSE 0 END)        AS cancelled,
    ROUND(100.0 * SUM(CASE WHEN status = 'user_cancelled' THEN 1 ELSE 0 END) / COUNT(*), 2)
                                                                      AS cancellation_rate
FROM vw_onboarding_outcomes
WHERE source = 'finishTransaction'
GROUP BY platform
ORDER BY finished_transactions DESC, platform;
