-- ============================================================================
-- 01_data_quality_audit.sql
-- Project : Amazon Customer Analytics — Retention & Advocacy Intelligence
-- Purpose : Quantify data quality issues in the raw Reviews table BEFORE any
--           analysis, so every cleaning decision downstream is documented and
--           defensible. This is the "audit" step a real analyst performs first.
-- Source  : ../Amazon/database.sqlite  (Amazon Fine Food Reviews, 568K rows)
-- Run     : sqlite3 ../Amazon/database.sqlite < sql/01_data_quality_audit.sql
-- ============================================================================

.mode column
.headers on
.width 32 14

.print '============================================================';
.print '  DATA QUALITY AUDIT — raw Reviews table';
.print '============================================================';
.print '';

-- 1. Overall volume -----------------------------------------------------------
.print '--- 1. Volume ---';
SELECT
    COUNT(*)                                        AS total_reviews,
    COUNT(DISTINCT UserId)                          AS distinct_users,
    COUNT(DISTINCT ProductId)                       AS distinct_products,
    COUNT(DISTINCT strftime('%Y-%m', Time, 'unixepoch')) AS distinct_months
FROM Reviews;

-- 2. Structurally invalid rows ------------------------------------------------
-- HelpfulnessNumerator can never legitimately exceed HelpfulnessDenominator:
-- the denominator counts everyone who voted, the numerator only the "helpful"
-- votes. Rows violating this invariant are corrupt and must be excluded.
.print '';
.print '--- 2. Invalid rows (Numerator > Denominator) ---';
SELECT
    COUNT(*) AS invalid_rows,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM Reviews), 2) AS pct_of_total
FROM Reviews
WHERE HelpfulnessNumerator > HelpfulnessDenominator;

-- 3. Duplicate reviews --------------------------------------------------------
-- Same user, same profile, same second, same text => almost certainly the same
-- review recorded twice (typically cross-posted across product variants).
-- Keeping them would double-count customer activity.
.print '';
.print '--- 3. Duplicates on (UserId, ProfileName, Time, Text) ---';
SELECT
    COUNT(*) AS duplicate_rows,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM Reviews), 2) AS pct_of_total
FROM Reviews
WHERE rowid NOT IN (
    SELECT MIN(Id)
    FROM Reviews
    GROUP BY UserId, ProfileName, Time, Text
);

-- 4. Missing values in analysis-critical columns ------------------------------
.print '';
.print '--- 4. Missing values ---';
SELECT
    SUM(CASE WHEN UserId     IS NULL THEN 1 ELSE 0 END) AS null_userid,
    SUM(CASE WHEN ProductId  IS NULL THEN 1 ELSE 0 END) AS null_productid,
    SUM(CASE WHEN Score      IS NULL THEN 1 ELSE 0 END) AS null_score,
    SUM(CASE WHEN Time       IS NULL THEN 1 ELSE 0 END) AS null_time,
    SUM(CASE WHEN Summary    IS NULL OR Summary = '' THEN 1 ELSE 0 END) AS null_summary,
    SUM(CASE WHEN Text       IS NULL OR Text    = '' THEN 1 ELSE 0 END) AS null_text
FROM Reviews;

-- 5. Score distribution (validating the 1–5 rating scale) --------------------
.print '';
.print '--- 5. Score distribution ---';
SELECT Score, COUNT(*) AS n,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM Reviews), 1) AS pct
FROM Reviews
GROUP BY Score
ORDER BY Score;

-- 6. Activity by year (coverage check for time-based analysis) ---------------
.print '';
.print '--- 6. Reviews per year ---';
SELECT strftime('%Y', Time, 'unixepoch') AS yr, COUNT(*) AS reviews
FROM Reviews
GROUP BY yr
ORDER BY yr;

-- 7. Expected clean dataset size ----------------------------------------------
.print '';
.print '--- 7. Expected clean dataset ---';
WITH valid AS (
    SELECT * FROM Reviews
    WHERE HelpfulnessNumerator <= HelpfulnessDenominator
),
deduped AS (
    SELECT *, ROW_NUMBER() OVER (
                 PARTITION BY UserId, ProfileName, Time, Text
                 ORDER BY Id) AS rn
    FROM valid
)
SELECT COUNT(*) AS clean_rows,
       COUNT(DISTINCT UserId) AS clean_users,
       COUNT(DISTINCT ProductId) AS clean_products
FROM deduped
WHERE rn = 1;
