-- Funnel and per-customer value by campaign arm.
-- One row per arm: customers, visits, conversions, spend, and rates.
SELECT
    segment                                   AS arm,
    COUNT(*)                                  AS customers,
    SUM(visit)                                AS visits,
    SUM(conversion)                           AS conversions,
    ROUND(SUM(spend), 2)                      AS revenue,
    AVG(visit)                                AS visit_rate,
    AVG(conversion)                           AS conversion_rate,
    SUM(conversion) * 1.0 / NULLIF(SUM(visit), 0) AS visit_to_purchase_rate,
    AVG(spend)                                AS revenue_per_customer
FROM hillstrom
GROUP BY segment
ORDER BY segment;
