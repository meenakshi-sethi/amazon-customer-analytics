-- ============================================================================
-- 02_customer_master.sql
-- Project : Amazon Customer Analytics — Retention & Advocacy Intelligence
-- Purpose : Build the customer master table: one row per customer with
--           behaviour features and an RF-style segment label.
--
-- Method  : This dataset has no revenue column, so classic RFM is not possible.
--           We use an R-F-E variant instead — Recency, Frequency, and
--           Engagement (helpfulness votes earned) — and state that limitation
--           openly. Customers are scored with NTILE() window functions:
--             r_tile : quintile of recency  (1 = most recent 20%)
--             f_tile : quintile of frequency (5 = most active 20%)
--           Segments follow standard CRM naming (Champions / Loyal / At Risk /
--           New / Promising / Hibernating / Casual).
--
-- NOTE    : This file is PURE SQL (no sqlite3 dot-commands) so that the Python
--           pipeline (python/01_clean_and_engineer.py) executes this exact
--           file — one source of truth for the segmentation logic.
--
-- Source  : ../Amazon/database.sqlite
-- Run     : sqlite3 -header -column ../Amazon/database.sqlite < sql/02_customer_master.sql
-- ============================================================================

WITH valid AS (
    -- Rule 1: drop structurally invalid rows (helpful votes cannot exceed
    -- total votes). Audit found 2 such rows.
    SELECT *
    FROM Reviews
    WHERE HelpfulnessNumerator <= HelpfulnessDenominator
),

deduped AS (
    -- Rule 2: deduplicate on (UserId, ProfileName, Time, Text) keeping the
    -- lowest Id. Audit found 174,521 duplicate rows (30.7% of raw data) —
    -- cross-posted reviews that would double-count customer activity.
    SELECT *
    FROM (
        SELECT *,
               ROW_NUMBER() OVER (
                   PARTITION BY UserId, ProfileName, Time, Text
                   ORDER BY Id
               ) AS rn
        FROM valid
    )
    WHERE rn = 1
),

user_agg AS (
    -- Behavioural features per customer.
    SELECT
        UserId,
        COUNT(*)                                   AS review_count,
        COUNT(DISTINCT ProductId)                  AS products_reviewed,
        ROUND(AVG(Score), 2)                       AS avg_score,
        MIN(Time)                                  AS first_review_ts,
        MAX(Time)                                  AS last_review_ts,
        SUM(HelpfulnessNumerator)                  AS helpful_votes,
        SUM(HelpfulnessDenominator)                AS total_votes
    FROM deduped
    GROUP BY UserId
),

scored AS (
    -- Recency (days since last review, measured from the dataset's most
    -- recent review) and quintile scores via window functions.
    SELECT
        *,
        CAST(JULIANDAY((SELECT MAX(Time) FROM deduped), 'unixepoch')
             - JULIANDAY(last_review_ts, 'unixepoch') AS INTEGER) AS recency_days,
        NTILE(5) OVER (ORDER BY last_review_ts DESC) AS r_tile,  -- 1 = most recent
        NTILE(5) OVER (ORDER BY review_count)        AS f_tile   -- 5 = most frequent
    FROM user_agg
)

SELECT
    UserId,
    review_count,
    products_reviewed,
    avg_score,
    recency_days,
    r_tile,
    f_tile,
    helpful_votes,
    total_votes,
    ROUND(1.0 * helpful_votes / NULLIF(total_votes, 0), 3) AS helpfulness_ratio,
    DATE(first_review_ts, 'unixepoch')                    AS first_review,
    DATE(last_review_ts,  'unixepoch')                    AS last_review,
    CASE
        WHEN r_tile <= 2 AND f_tile =  5 THEN 'Champions'       -- active & heavy
        WHEN r_tile =  3 AND f_tile =  5 THEN 'Loyal'           -- heavy, cooling off
        WHEN r_tile >= 4 AND f_tile =  5 THEN 'At Risk'         -- heavy, gone quiet
        WHEN r_tile <= 2 AND f_tile <= 2 THEN 'New / Promising' -- recent, light
        WHEN r_tile >= 4 AND f_tile <= 2 THEN 'Hibernating'     -- old, light
        ELSE 'Casual'
    END AS segment
FROM scored;
