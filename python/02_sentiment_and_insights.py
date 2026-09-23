"""
02_sentiment_and_insights.py
============================
Stage 2 of the pipeline: sentiment analysis WITH validation, rating-sentiment
gap analysis, and advocate identification.

Why this stage matters (the analytical story):
    The naive approach (the tutorial approach) computes sentiment and stops.
    A real analyst VALIDATES the model against ground truth — here, the star
    rating the same customer gave. Where text sentiment and star rating
    disagree is where the business insight lives:
      * "Hidden detractors"  — 4-5 stars but negative text. The rating looks
        fine in dashboards, but the customer is actually complaining.
      * "Hidden advocates"   — 1-2 stars but positive text. Often rating the
        delivery, not the product.
    Both groups are invisible to any star-rating-only dashboard.

Method notes:
    * TextBlob polarity on the review SUMMARY (short, dense, low-noise) —
      same method as the original tutorial, but now validated.
    * Neutral band: |polarity| <= 0.10 (TextBlob's default-ish threshold;
      documented so a reviewer can challenge it).
    * Full 393K clean reviews — no silent 50K sampling like the tutorial.

Outputs (to ../exports/):
    sentiment_by_score.csv  — avg polarity + sentiment mix per star rating
    gap_summary.csv         — hidden detractors / hidden advocates counts
    advocates.csv           — top 30 review advocates for activation program
    reviews_scored.csv      — review-level table w/ polarity (for Tableau)
    kpis.json               — updated with sentiment headline numbers

Run:  .venv/bin/python python/02_sentiment_and_insights.py   (takes ~3-5 min)
"""

import json
import os
import sqlite3
from pathlib import Path

import pandas as pd
from textblob import TextBlob

ROOT = Path(__file__).resolve().parents[1]
# Override with the AMAZON_DB environment variable; default expects the
# Kaggle database.sqlite in the project's data/ folder (gitignored).
DB_PATH = Path(os.environ.get("AMAZON_DB", str(ROOT / "data" / "database.sqlite")))
EXPORTS = ROOT / "exports"

NEUTRAL_BAND = 0.10  # |polarity| <= this => neutral. Documented, challengeable.

# --- 1. load the clean review-level table (same SQL rules as stage 1) ---------
print("Loading clean reviews from SQLite ...")
con = sqlite3.connect(DB_PATH)
reviews = pd.read_sql_query(
    """
    SELECT Id, UserId, ProductId, Score, Time, Summary, Text,
           HelpfulnessNumerator, HelpfulnessDenominator
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
con.close()
print(f"Loaded {len(reviews):,} clean reviews")

# --- 2. sentiment scoring (full dataset, no sampling) --------------------------
print("Scoring sentiment with TextBlob (full dataset, ~3-5 min) ...")


def polarity_of(text: str) -> float:
    """Return TextBlob polarity; empty/whitespace summaries score 0 (neutral).

    Unlike the tutorial's bare `except: append(0)` — which silently swallowed
    EVERY error type — we only guard the one failure mode that actually
    occurs (missing/blank summary) and let real errors surface.
    """
    if not isinstance(text, str) or not text.strip():
        return 0.0
    return TextBlob(text).sentiment.polarity


reviews["polarity"] = reviews["Summary"].map(polarity_of)


def label(p: float) -> str:
    if p > NEUTRAL_BAND:
        return "Positive"
    if p < -NEUTRAL_BAND:
        return "Negative"
    return "Neutral"


reviews["sentiment"] = reviews["polarity"].map(label)

# --- 3. VALIDATION: does text sentiment agree with the star rating? ------------
# Ground truth mapping: 4-5 stars = positive, 3 = neutral, 1-2 = negative.
def rating_label(score: int) -> str:
    return "Positive" if score >= 4 else ("Negative" if score <= 2 else "Neutral")


reviews["rating_label"] = reviews["Score"].map(rating_label)

confusion = pd.crosstab(reviews["rating_label"], reviews["sentiment"])
agreement_pct = round(
    100 * (reviews["rating_label"] == reviews["sentiment"]).mean(), 1
)
print(f"\nSentiment-vs-rating agreement: {agreement_pct}%")
print(confusion)

# --- 4. gap analysis: the invisible customers -----------------------------------
hidden_detractors = reviews[
    (reviews["Score"] >= 4) & (reviews["sentiment"] == "Negative")
]
hidden_advocates_low = reviews[
    (reviews["Score"] <= 2) & (reviews["sentiment"] == "Positive")
]
high_star = reviews[reviews["Score"] >= 4]

gap_summary = pd.DataFrame(
    {
        "group": [
            "Hidden detractors (4-5 stars, negative text)",
            "Hidden advocates (1-2 stars, positive text)",
        ],
        "reviews": [len(hidden_detractors), len(hidden_advocates_low)],
        "pct_of_high_star_reviews": [
            round(100 * len(hidden_detractors) / len(high_star), 1),
            None,
        ],
        "avg_polarity": [
            round(hidden_detractors["polarity"].mean(), 3),
            round(hidden_advocates_low["polarity"].mean(), 3),
        ],
    }
)
print("\n--- Gap analysis ---")
print(gap_summary.to_string(index=False))

# --- 5. sentiment by score (validation visual for the dashboard) ---------------
sentiment_by_score = (
    reviews.groupby("Score")
    .agg(
        reviews=("Id", "count"),
        avg_polarity=("polarity", "mean"),
        pct_positive=("sentiment", lambda s: round(100 * (s == "Positive").mean(), 1)),
        pct_neutral=("sentiment", lambda s: round(100 * (s == "Neutral").mean(), 1)),
        pct_negative=("sentiment", lambda s: round(100 * (s == "Negative").mean(), 1)),
    )
    .round(3)
    .reset_index()
)

# --- 6. advocate identification (activation-program shortlist) ------------------
# An advocate: engaged (Champions/Loyal segment), trusted (high helpfulness
# ratio), and consistently positive. Ranked by a simple advocacy score.
master = pd.read_csv(EXPORTS / "customer_master.csv")
scored = reviews.groupby("UserId").agg(
    reviews_scored=("Id", "count"),
    avg_polarity=("polarity", "mean"),
    pct_positive=("sentiment", lambda s: 100 * (s == "Positive").mean()),
)

advocates = master.merge(scored, on="UserId", how="inner")
advocates = advocates[
    advocates["segment"].isin(["Champions", "Loyal"])
    & (advocates["total_votes"] >= 10)
    & (advocates["pct_positive"] >= 60)
].copy()
advocates["advocacy_score"] = (
    advocates["helpfulness_ratio"].fillna(0) * 50
    + advocates["pct_positive"] / 100 * 30
    + advocates["review_count"].clip(upper=20) / 20 * 20
).round(1)
advocates = advocates.sort_values("advocacy_score", ascending=False).head(30)
advocates = advocates[
    [
        "UserId",
        "segment",
        "review_count",
        "avg_score",
        "helpful_votes",
        "helpfulness_ratio",
        "pct_positive",
        "advocacy_score",
        "last_review",
    ]
]

# --- 7. export --------------------------------------------------------------------
sentiment_by_score.to_csv(EXPORTS / "sentiment_by_score.csv", index=False)
gap_summary.to_csv(EXPORTS / "gap_summary.csv", index=False)
advocates.to_csv(EXPORTS / "advocates.csv", index=False)

# review-level table for Tableau (drop the long Text column to keep it light)
reviews.drop(columns=["Text"]).to_csv(EXPORTS / "reviews_scored.csv", index=False)

with open(EXPORTS / "kpis.json") as f:
    kpis = json.load(f)
kpis.update(
    {
        "sentiment_rating_agreement_pct": agreement_pct,
        "hidden_detractors": int(len(hidden_detractors)),
        "hidden_detractors_pct_of_high_star": round(
            100 * len(hidden_detractors) / len(high_star), 1
        ),
        "advocates_identified": int(len(advocates)),
        "pct_positive_overall": round(
            100 * (reviews["sentiment"] == "Positive").mean(), 1
        ),
    }
)
with open(EXPORTS / "kpis.json", "w") as f:
    json.dump(kpis, f, indent=2)

print("\n--- Sentiment by score ---")
print(sentiment_by_score.to_string(index=False))
print(f"\nAdvocates shortlisted: {len(advocates)}")
print("Exports written: sentiment_by_score.csv, gap_summary.csv, advocates.csv, reviews_scored.csv")
