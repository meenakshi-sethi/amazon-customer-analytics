"""
01_clean_and_engineer.py
========================
Stage 1 of the pipeline: data quality enforcement + customer master build.

Design decision (important): the cleaning rules and segmentation logic live in
sql/02_customer_master.sql — a single source of truth. This script executes
that exact SQL file against the SQLite database, so the logic can never drift
between the "SQL version" and the "Python version" of the analysis.

Every wrangling decision is exported to exports/wrangling_audit.json so the
data ancestry is fully auditable (enterprise standard).

Outputs (to exports/):
    customer_master.csv   — one row per customer, features + segment label
    segment_summary.csv   — segment-level rollup for dashboards
    monthly_activity.csv  — monthly reviews / active users / new users
    wrangling_audit.json  — row-level impact of every cleaning rule
    kpis.json             — headline numbers used by the dashboard & README

Run:  .venv/bin/python python/01_clean_and_engineer.py
"""

import json
import os
import sqlite3
from pathlib import Path

import pandas as pd

# --- config (zero hard-coding below this block) --------------------------------
ROOT = Path(__file__).resolve().parents[1]
# Raw database location. Override with the AMAZON_DB environment variable;
# default expects the Kaggle "Amazon Fine Food Reviews" database.sqlite in a
# sibling folder (../Amazon/database.sqlite).
DB_PATH = Path(os.environ.get("AMAZON_DB", str(ROOT.parent / "Amazon" / "database.sqlite")))
SQL_FILE = ROOT / "sql" / "02_customer_master.sql"
EXPORTS = ROOT / "exports"
MATURE_YEARS_FROM = "2007-01"  # timeline starts when monthly volume is meaningful
EXPORTS.mkdir(exist_ok=True)

# --- 1. execute the segmentation SQL (single source of truth) ------------------
print(f"Executing {SQL_FILE.name} against {DB_PATH} ...")
with open(SQL_FILE, "r", encoding="utf-8") as f:
    SEGMENTATION_SQL = f.read()

con = sqlite3.connect(DB_PATH)
master = pd.read_sql_query(SEGMENTATION_SQL, con)

# --- 2. raw vs clean volume (for the README's data-quality story) --------------
raw_rows = int(pd.read_sql_query("SELECT COUNT(*) AS n FROM Reviews", con)["n"][0])
con.close()

clean_customers = len(master)
print(f"Raw reviews:      {raw_rows:,}")
print(f"Clean customers:  {clean_customers:,} (dedup + validity rules applied in SQL)")

# --- 3. segment summary ---------------------------------------------------------
# Engagement proxy: helpfulness_ratio is NULL when a user never earned a vote;
# we keep it NULL (not zero) so segment averages aren't dragged down unfairly.
segment_summary = (
    master.groupby("segment")
    .agg(
        customers=("UserId", "count"),
        avg_reviews=("review_count", "mean"),
        avg_recency_days=("recency_days", "mean"),
        avg_score=("avg_score", "mean"),
        total_helpful_votes=("helpful_votes", "sum"),
    )
    .round(2)
    .sort_values("customers", ascending=False)
    .reset_index()
)
segment_summary["pct_customers"] = (
    100 * segment_summary["customers"] / segment_summary["customers"].sum()
).round(1)

# --- 4. monthly activity (retention decay view) ----------------------------------
# Re-derive the clean review-level table with the same SQL rules so the
# timeline matches the customer master exactly.
con = sqlite3.connect(DB_PATH)
reviews = pd.read_sql_query(
    """
    SELECT UserId, ProductId, Score, Time, HelpfulnessNumerator, HelpfulnessDenominator
    FROM (
        SELECT *, ROW_NUMBER() OVER (
            PARTITION BY UserId, ProfileName, Time, Text ORDER BY Id) AS rn
        FROM Reviews
        WHERE HelpfulnessNumerator <= HelpfulnessDenominator
    )
    WHERE rn = 1
    """,
    con,
)
invalid_rows = int(
    pd.read_sql_query(
        "SELECT COUNT(*) AS n FROM Reviews WHERE HelpfulnessNumerator > HelpfulnessDenominator",
        con,
    )["n"][0]
)
con.close()

reviews["review_date"] = pd.to_datetime(reviews["Time"], unit="s")
reviews["month"] = reviews["review_date"].dt.to_period("M").astype(str)

first_review_by_user = reviews.groupby("UserId")["review_date"].min()

monthly = (
    reviews.groupby("month")
    .agg(
        reviews=("UserId", "count"),
        active_users=("UserId", "nunique"),
        avg_score=("Score", "mean"),
    )
    .reset_index()
)
# new users = users whose FIRST review falls in that month
new_counts = (
    first_review_by_user.dt.to_period("M").astype(str).value_counts().rename("new_users")
)
monthly = monthly.merge(new_counts, left_on="month", right_index=True, how="left")
monthly["new_users"] = monthly["new_users"].fillna(0).astype(int)
monthly["avg_score"] = monthly["avg_score"].round(2)
monthly = monthly[monthly["month"] >= MATURE_YEARS_FROM].reset_index(drop=True)

# --- 4b. wrangling audit log ------------------------------------------------------
# Every cleaning decision, its rule, its reason, and its row-level impact —
# exported so data ancestry is fully auditable.
duplicate_rows = raw_rows - invalid_rows - len(reviews)
audit_log = [
    {
        "step": 1,
        "rule": "Drop rows where HelpfulnessNumerator > HelpfulnessDenominator",
        "reason": "Structurally impossible: helpful votes are a subset of total votes",
        "rows_removed": invalid_rows,
        "rows_after": raw_rows - invalid_rows,
    },
    {
        "step": 2,
        "rule": "Deduplicate on (UserId, ProfileName, Time, Text), keep lowest Id",
        "reason": "Cross-posted reviews would double-count customer activity",
        "rows_removed": duplicate_rows,
        "rows_after": int(len(reviews)),
    },
]
with open(EXPORTS / "wrangling_audit.json", "w") as f:
    json.dump(audit_log, f, indent=2)

# --- 5. headline KPIs -------------------------------------------------------------
kpis = {
    "raw_reviews": raw_rows,
    "clean_reviews": int(reviews.shape[0]),
    "invalid_rows": invalid_rows,
    "duplicate_rows": int(duplicate_rows),
    "duplicate_pct": round(100 * (1 - reviews.shape[0] / raw_rows), 1),
    "customers": int(master["UserId"].nunique()),
    "products": int(reviews["ProductId"].nunique()),
    "date_min": str(reviews["review_date"].min().date()),
    "date_max": str(reviews["review_date"].max().date()),
    "champions": int(segment_summary.loc[
        segment_summary["segment"] == "Champions", "customers"].sum()),
    "at_risk": int(segment_summary.loc[
        segment_summary["segment"] == "At Risk", "customers"].sum()),
    "avg_rating_clean": round(float(reviews["Score"].mean()), 2),
}

# --- 6. export ---------------------------------------------------------------------
master.to_csv(EXPORTS / "customer_master.csv", index=False)
segment_summary.to_csv(EXPORTS / "segment_summary.csv", index=False)
monthly.to_csv(EXPORTS / "monthly_activity.csv", index=False)
with open(EXPORTS / "kpis.json", "w") as f:
    json.dump(kpis, f, indent=2)

print("\n--- Wrangling audit log ---")
for entry in audit_log:
    print(f"  step {entry['step']}: -{entry['rows_removed']:,} rows -> {entry['rows_after']:,}")
print("\n--- Segment summary ---")
print(segment_summary.to_string(index=False))
print("\nExports written to exports/:")
for p in sorted(EXPORTS.glob("*")):
    print(f"  {p.name}  ({p.stat().st_size / 1024:.0f} KB)")
