-- Incremental visit rate (treated minus control) for each campaign,
-- broken out by a customer attribute. {dim} is substituted by the caller
-- with one of: channel, zip_code, newbie, history_segment.
WITH rates AS (
    SELECT
        CAST({dim} AS VARCHAR) AS dim_value,
        segment,
        COUNT(*)    AS n,
        AVG(visit)  AS visit_rate,
        AVG(spend)  AS spend_per_customer
    FROM hillstrom
    GROUP BY 1, 2
)
SELECT
    t.dim_value,
    t.segment                                   AS campaign,
    t.n                                         AS treated_n,
    c.n                                         AS control_n,
    t.visit_rate - c.visit_rate                 AS visit_lift_pp,
    t.spend_per_customer - c.spend_per_customer AS spend_lift
FROM rates t
JOIN rates c
  ON c.dim_value = t.dim_value AND c.segment = 'No E-Mail'
WHERE t.segment <> 'No E-Mail'
ORDER BY campaign, visit_lift_pp DESC;
