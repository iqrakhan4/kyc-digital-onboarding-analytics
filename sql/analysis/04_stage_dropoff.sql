-- Q4. Where do users cancel? Last recorded stage of cancelled journeys.
SELECT
    stage,
    COUNT(*)                                               AS transactions,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)     AS pct_of_cancellations
FROM vw_onboarding_outcomes
WHERE status = 'user_cancelled'
GROUP BY stage
ORDER BY transactions DESC, stage;
