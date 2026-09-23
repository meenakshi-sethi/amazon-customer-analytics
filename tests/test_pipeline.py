"""
test_pipeline.py
================
Schema & invariant checks for the pipeline outputs (enterprise standard:
the pipeline must fail loudly when new data breaks assumptions).

Run the pipeline first:
    .venv/bin/python python/01_clean_and_engineer.py
    .venv/bin/python python/02_sentiment_and_insights.py
    .venv/bin/python python/04_statistics_and_modeling.py
Then:
    .venv/bin/python -m pytest tests/ -v
"""

import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "exports"

EXPECTED_SEGMENTS = {"Champions", "Loyal", "At Risk", "New / Promising", "Hibernating", "Casual"}
EXPECTED_SENTIMENTS = {"Positive", "Neutral", "Negative"}


@pytest.fixture(scope="module")
def kpis():
    return json.loads((EXPORTS / "kpis.json").read_text())


@pytest.fixture(scope="module")
def master():
    return pd.read_csv(EXPORTS / "customer_master.csv")


@pytest.fixture(scope="module")
def scored():
    return pd.read_csv(EXPORTS / "reviews_scored.csv")


# --- existence -----------------------------------------------------------------

def test_all_exports_exist():
    for name in [
        "customer_master.csv", "segment_summary.csv", "monthly_activity.csv",
        "reviews_scored.csv", "sentiment_by_score.csv", "gap_summary.csv",
        "advocates.csv", "kpis.json", "wrangling_audit.json", "stats_summary.json",
    ]:
        assert (EXPORTS / name).exists(), f"missing export: {name}"


# --- schema checks ---------------------------------------------------------------

def test_customer_master_schema(master):
    required = {"UserId", "review_count", "avg_score", "recency_days",
                "r_tile", "f_tile", "segment"}
    assert required <= set(master.columns), "customer_master lost required columns"
    assert master["UserId"].notna().all(), "null UserId in customer master"
    assert master["UserId"].is_unique, "customer master is not one row per customer"
    assert set(master["segment"]) <= EXPECTED_SEGMENTS, "unexpected segment label"
    assert master["r_tile"].between(1, 5).all() and master["f_tile"].between(1, 5).all()


def test_reviews_scored_schema(scored):
    required = {"Id", "UserId", "Score", "polarity", "sentiment"}
    assert required <= set(scored.columns), "reviews_scored lost required columns"
    assert scored["Score"].between(1, 5).all(), "score outside 1-5"
    assert set(scored["sentiment"]) <= EXPECTED_SENTIMENTS, "unexpected sentiment label"
    assert scored["polarity"].between(-1, 1).all(), "polarity outside TextBlob range"
    assert scored["Id"].is_unique, "duplicate reviews survived dedup"


# --- cross-file consistency --------------------------------------------------------

def test_row_counts_reconcile(kpis, scored, master):
    assert len(scored) == kpis["clean_reviews"], "scored rows != clean_reviews KPI"
    assert len(master) == kpis["customers"], "master rows != customers KPI"
    assert kpis["raw_reviews"] > kpis["clean_reviews"], "clean > raw is impossible"


def test_wrangling_audit_adds_up(kpis):
    audit = json.loads((EXPORTS / "wrangling_audit.json").read_text())
    removed = sum(entry["rows_removed"] for entry in audit)
    assert kpis["raw_reviews"] - removed == kpis["clean_reviews"], \
        "audit log rows do not reconcile with KPIs"


# --- analytical invariants ----------------------------------------------------------

def test_sentiment_monotonic_with_rating():
    sbs = pd.read_csv(EXPORTS / "sentiment_by_score.csv")
    assert sbs["avg_polarity"].is_monotonic_increasing, \
        "avg polarity must rise with star rating — model invalidation if not"


def test_monthly_series_continuous():
    monthly = pd.read_csv(EXPORTS / "monthly_activity.csv")
    assert monthly["month"].is_unique, "duplicate months in timeline"
    assert monthly["month"].is_monotonic_increasing, "timeline not sorted"
    assert (monthly["new_users"] <= monthly["active_users"]).all(), \
        "new users cannot exceed active users in a month"


def test_advocates_meet_criteria():
    advocates = pd.read_csv(EXPORTS / "advocates.csv")
    assert set(advocates["segment"]) <= {"Champions", "Loyal"}, \
        "non-advocate segment shortlisted"
    assert (advocates["helpful_votes"] >= 0).all(), "negative helpfulness votes"
    assert (advocates["pct_positive"] >= 60).all(), "advocate below positivity bar"


def test_stats_results_present():
    stats = json.loads((EXPORTS / "stats_summary.json").read_text())
    for key in ["mannwhitney", "chi_square", "ols", "power", "correlation"]:
        assert key in stats, f"missing statistical result: {key}"
    assert 0 <= stats["mannwhitney"]["p_value"] <= 1
    assert 0 <= stats["ols"]["r_squared"] <= 1
    assert stats["power"]["n_per_group"] > 0


def test_correlation_matrix_wellformed():
    stats = json.loads((EXPORTS / "stats_summary.json").read_text())
    corr = stats["correlation"]
    n = len(corr["variables"])
    assert n >= 4, "correlation matrix too small to be informative"
    for key in ["pearson", "spearman"]:
        m = corr[key]
        assert len(m) == n and all(len(row) == n for row in m), f"{key} not square"
        for i in range(n):
            assert m[i][i] == 1.0, f"{key} diagonal must be 1.0"
            for j in range(n):
                assert -1.0 <= m[i][j] <= 1.0, f"{key} value out of [-1, 1]"
                assert m[i][j] == m[j][i], f"{key} not symmetric"
    assert len(corr["strongest"]) >= 3, "strongest pairs not exported"
