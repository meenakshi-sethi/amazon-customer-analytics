# Interview Preparation — The Fine Food Review Files

STAR-structured stories and defense answers for the questions this project
invites. Every number below is real and reproducible from the pipeline.

---

## The 60-second pitch

> "I took a public dataset of 568K Amazon food reviews and turned it into a
> customer-retention and advocacy intelligence product. First I audited the
> data and found a third of it was duplicates — so I built the cleaning rules
> in SQL as a single source of truth, with an audit log and automated tests
> reconciling every removed row. Then I segmented 256K customers with an
> RF-E model — the dataset has no revenue, so I substituted engagement and
> said so openly. I scored sentiment on all 393K clean reviews and *validated*
> it against the star ratings — 58.5% agreement — which surfaced 9,246
> 'hidden detractors' who look satisfied in star dashboards but write
> complaints. Finally I took the key claims to inferential statistics:
> Mann-Whitney, chi-square, an OLS on what drives influence, and a power
> analysis sizing the next experiment. Everything feeds a dashboard that's
> generated programmatically from the pipeline's exports, so the numbers
> can never drift."

---

## STAR stories

### 1. Data quality (initiative + rigor)
- **S** — Public dataset, 568,454 rows, tutorial-grade analyses everywhere.
- **T** — Make it analysis-grade; every decision defensible.
- **A** — Wrote a SQL audit first: found 2 impossible rows (helpfulness
  numerator > denominator) and 174,521 duplicates (same user, text, second —
  cross-posted across product variants). Enforced rules in SQL, exported a
  row-level audit log, and wrote pytest checks that reconcile
  raw − removed = clean.
- **R** — 393,931 clean reviews; 30.7% of the raw file would have
  double-counted customer activity in any naive analysis.

### 2. Model validation (intellectual honesty)
- **S** — Needed sentiment; TextBlob is the standard quick tool.
- **T** — Decide whether its output can be trusted for business claims.
- **A** — Scored all 393,931 reviews (no sampling), then validated against
  the same customer's star rating: 58.5% agreement, but polarity rises
  monotonically with rating (−0.15 at 1★ → +0.46 at 5★).
- **R** — Declared the method directionally sound but individually noisy —
  and turned the *disagreement* into the headline insight: 9,246 hidden
  detractors (4–5★, negative text) and 9,573 hidden advocates (1–2★,
  positive text), both invisible to star-only dashboards.

### 3. Statistics choosing the analyst over the engineer
- **S** — Dashboard suggested Champions are the "best" customers.
- **T** — Prove or kill that assumption before anyone acts on it.
- **A** — The distributions are wildly non-normal (reviews/customer skew
  30.9; helpfulness votes log-log skewed; polarity bounded and tri-modal),
  so I used Mann-Whitney U instead of a t-test, chi-square for
  segment × sentiment, statsmodels OLS (for interpretable coefficients,
  p-values, standard errors — not sklearn's opaque predictions), and a
  power analysis for experiment sizing.
- **R** — The trust difference is real (p ≈ 10⁻¹⁵³) but *reversed*:
  Casual reviewers earn a higher median helpfulness ratio (1.00 vs 0.93).
  Volume dilutes per-review trust. OLS confirms: breadth (# products,
  β = 0.21) drives influence, volume per product drags it (β = −0.10).

---

## Defense answers (the questions that WILL come)

**"Why were 30.7% of rows duplicates?"**
Cross-posting: Amazon shows the same review on multiple product variants
(same food, different sizes/packaging). The dataset records each posting as
a row. Deduplicating on (UserId, ProfileName, Time, Text) keeps one instance
per actual review event.

**"Why RF-E instead of RFM?"**
No revenue or price column exists — inventing one would be fabrication.
Engagement (helpfulness votes earned) is the best available value proxy, and
the substitution is documented in the README and the dashboard itself.

**"Why is sentiment agreement only 58.5%?"**
Lexicon sentiment misses sarcasm, context, and short summaries. That's why
(a) the neutral band (|polarity| ≤ 0.10) is documented and challengeable,
(b) findings are framed at the group level, and (c) the disagreement itself
became the analysis — the gap groups are the deliverable.

**"Why SQL as the single source of truth?"**
So the logic can't drift between the SQL portfolio artifact and the Python
pipeline — the Python stage executes the exact same .sql file. One bug fix
propagates everywhere.

**"Why statsmodels over scikit-learn?"**
An analyst's job is explanation, not just prediction: statsmodels gives
coefficients, standard errors, and p-values per feature, so I can say *why*
breadth drives influence and by how much — and defend it under questioning.

**"What would you do with more time?"**
Cohort retention curves by acquisition month (data's already exported),
a Tableau Public edition (spec is written), and swapping TextBlob for a
transformer-based model to re-measure the agreement rate.

**"What's the business action?"**
Three plays: (1) win-back the 14,714 At-Risk heavy reviewers; (2) route the
9,246 hidden detractors to service recovery before they churn silently;
(3) activate the 30 shortlisted advocates (criteria: Champions/Loyal,
≥10 helpfulness votes, ≥60% positive summaries) in a review-incentive
program.
