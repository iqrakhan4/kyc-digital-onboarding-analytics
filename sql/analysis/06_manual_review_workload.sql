-- Q6. Size and outcome of the manual (agent) decision queue.
SELECT
    status,
    COUNT(*)                                                         AS transactions,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)               AS pct_of_manual_decisions,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM onboarding_transactions), 2)
                                                                     AS pct_of_all_transactions
FROM vw_onboarding_outcomes
WHERE source = 'application-update-by-agent'
GROUP BY status
ORDER BY transactions DESC, status;
