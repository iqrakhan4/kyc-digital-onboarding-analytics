-- Q1. How do onboarding attempts end?
-- Window function gives each status's share of all attempts in one pass.
SELECT
    status,
    COUNT(*)                                                AS transactions,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)      AS percentage
FROM vw_onboarding_outcomes
GROUP BY status
ORDER BY transactions DESC, status;
