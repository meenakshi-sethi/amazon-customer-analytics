# Tableau Public Edition — Build Spec

Status: **in preparation** (noted in the HTML dashboard's colophon as the
follow-up deliverable). This spec is complete enough to build in one sitting.

## Data source

`exports/reviews_scored.csv` (regenerate via the pipeline; ~37 MB, 393,931
rows) — review-level, one row per clean review:

| Column | Type | Use |
|---|---|---|
| Id, UserId, ProductId | dim keys | detail / drill-down |
| Score | int 1–5 | rating distributions |
| Time / review_date | datetime | timeline |
| Summary | text | tooltip context |
| polarity | float −1..1 | sentiment axis |
| sentiment | Positive/Neutral/Negative | color encoding |
| rating_label | Positive/Neutral/Negative | validation & gap analysis |
| HelpfulnessNumerator/Denominator | int | trust metrics |
| segment | 6 RF-E labels | segmentation filters |

Join `exports/customer_master.csv` (256,059 rows) on UserId for
customer-level features (recency_days, r_tile, f_tile, helpfulness_ratio).

## Sheets

1. **Segment Map** — packed bubbles or treemap, size = customers, color =
   segment. Filter action → all other sheets.
2. **Retention Timeline** — line: monthly active vs. new reviewers
   (dual-axis), 2007–2012. Annotate the widening 2011–12 gap.
3. **Stars vs. Words** — side-by-side bars: rating_label vs. sentiment
   (100% stacked). This is the validation visual — the off-diagonal cells
   ARE the story.
4. **Hidden Detractors** — filtered table: Score ≥ 4 AND sentiment =
   Negative, sorted by polarity ascending, Summary in tooltip.
5. **Influence Drivers** — scatter: review_count (x) vs helpful_votes (y),
   size = products_reviewed, color = segment; log axes.
6. **Advocate Leaderboard** — top 30 by advocacy_score, highlight
   Champions/Loyal.

## Dashboard layout (1280×800)

- Top band: KPI tiles (clean reviews, customers, agreement %, hidden
  detractors, advocates) — same numbers as the HTML edition.
- Left: Segment Map (filter for everything).
- Center: Retention Timeline above Stars vs. Words.
- Right: Hidden Detractors table + Advocate Leaderboard stacked.
- Footer: methodology note (dedup rules, RF-E substitution, TextBlob
  validation) — transparency is part of the design language.

## Publishing checklist

- [ ] Tableau Public profile linked from the README roadmap
- [ ] Same palette as the HTML edition (paper #f6f1e7, ink #1c1712,
      oxblood #8f2b1e, blue #2f4d6b, green #41684a) for brand continuity
- [ ] Tooltip summaries limited to 200 chars (privacy + readability)
- [ ] "How these numbers were produced" caption pointing to this repo
