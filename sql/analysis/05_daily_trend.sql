-- Q5. Daily volume and approval share, with a 7-day rolling average.
WITH daily AS (
    SELECT
        created_date,
        COUNT(*)                                        AS total,
        SUM(is_approved)                                AS approved
    FROM vw_onboarding_outcomes
    WHERE created_date IS NOT NULL
    GROUP BY created_date
)
SELECT
    created_date,
    total,
    approved,
    ROUND(100.0 * approved / total, 2)                  AS approved_share_pct,
    ROUND(AVG(total) OVER (
        ORDER BY created_date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ), 1)                                               AS rolling_7day_avg
FROM daily
ORDER BY created_date;
