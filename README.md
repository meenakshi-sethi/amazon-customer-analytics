# The Fine Food Review Files
### Amazon Customer Analytics — Retention & Advocacy Intelligence

**SQL + Python + statistical inference** — SQLite · pandas · TextBlob · scipy · statsmodels | **[Interactive Report](dashboard.html)**

An end-to-end customer analytics investigation over **568,454 Amazon fine-food reviews (Oct 1999 – Oct 2012)**: SQL-driven data quality enforcement, RF-E customer segmentation, validated sentiment analysis, inferential statistics, and an activation-ready advocate shortlist — delivered as a reproducible pipeline and an interactive, zero-dependency [dashboard](dashboard.html).

**Data background.** The dataset is the [Amazon Fine Food Reviews](https://www.kaggle.com/datasets/snap/amazon-fine-food-reviews) corpus (Kaggle / SNAP, Stanford Network Analysis Project) — **real, publicly released customer reviews** of gourmet food products sold on Amazon, collected over thirteen years (October 1999 – October 2012). It contains 568,454 reviews from 256,059 distinct customers covering 74,258 products, each row carrying the star rating (1–5), the full review text (~436 characters on average), a review summary, a timestamp, and the community's helpfulness votes on that review. Customer identifiers are pseudonymous as shipped by SNAP. Unlike a transaction log, there is no revenue or purchase-quantity data — value is proxied by engagement (helpfulness votes), which is why this project uses an R-F-E segmentation variant rather than classic RFM.

> **Read the deliverable first:** open [`dashboard.html`](dashboard.html) — an editorial-style interactive journal generated programmatically from the pipeline's exports. A Tableau Public edition is in preparation.

---

## 1. Executive Summary

**Business problem.** A food-retail marketplace knows star ratings alone are a weak signal: they hide complaining customers behind 4–5 stars and satisfied ones behind 1–2 stars. Leadership asked three questions: *Who are our customers? Which of them are we losing? Who should we activate as advocates?*

**Approach.** A four-stage, fully reproducible pipeline — audit → segmentation → sentiment (validated against ground truth) → inferential statistics — with every wrangling decision logged and every claim tested.

**Headline findings.**

| Finding | Number | So what |
|---|---|---|
| Raw data was 30.7% duplicates | 174,521 rows removed | Any tutorial-level analysis on the raw file double-counts a third of all activity |
| Customers segment into 6 RF-E groups | 10.3% Champions, 5.7% At Risk | Distinct retention vs. win-back plays per segment |
| Sentiment agrees with stars only 58.5% of the time | validated on 393,931 reviews | Lexicon sentiment is directionally sound but must be validated, not trusted |
| **9,246 hidden detractors** | 3.0% of all 4–5★ reviews | Customers who *look* satisfied in star dashboards but write complaints |
| **9,573 hidden advocates** | 1–2★ but positive text | Recovery-win candidates; often rating delivery, not product |
| Volume ≠ influence (Mann-Whitney, p ≈ 10⁻¹⁵³) | median helpfulness 1.00 (Casual) vs 0.93 (Champions) | Trust is per-review; prolific reviewers dilute it |
| 30 advocates shortlisted | scored 50% trust / 30% positivity / 20% activity | Ready list for an activation program |

---

## 2. Data Wrangling & Audit Log

Every cleaning rule lives in SQL ([`sql/`](sql/)), is executed by the Python pipeline, is exported to `exports/wrangling_audit.json`, and is reconciled by automated tests. Full data ancestry.

| Step | Rule | Reason | Rows removed | Rows after |
|---|---|---|---|---|
| 1 | Drop rows where `HelpfulnessNumerator > HelpfulnessDenominator` | Structurally impossible: helpful votes are a subset of total votes | 2 | 568,452 |
| 2 | Deduplicate on `(UserId, ProfileName, Time, Text)`, keep lowest `Id` | Cross-posted reviews double-count customer activity | 174,519 | **393,931** |

**Documented limitations (stated, not hidden):**
- No revenue column exists → classic RFM is impossible; an **R-F-E** variant (Recency, Frequency, Engagement) is used instead, with helpfulness votes as the value proxy.
- TextBlob is a lexicon method → validated against star ratings (58.5% agreement, monotonic polarity-by-rating) and every downstream claim about sentiment is framed with that error bar in mind.
- Reviews are a **self-selected sample** of buyers, not the buyer population — all findings are about the reviewing population.

---

## 3. Analytical Workflow

```
sql/01_data_quality_audit.sql     ← quantify problems before touching anything
sql/02_customer_master.sql        ← CTEs + ROW_NUMBER dedup + NTILE quintiles + CASE segments
        │                        (single source of truth — Python executes this exact file)
        ▼
python/01_clean_and_engineer.py   ← customer master, segment rollup, monthly timeline, audit log
python/02_sentiment_and_insights.py ← TextBlob on 393,931 reviews (no sampling),
                                      validation vs. ratings, gap analysis, advocate scoring
python/04_statistics_and_modeling.py ← profiling + skew, Mann-Whitney U, chi-square + Cramér's V,
                                      statsmodels OLS, power analysis, distribution figures
python/03_build_dashboard.py      ← generates dashboard.html from exports (numbers can't drift)
notebooks/exploration.ipynb       ← interactive layer over the exports (audit trail, segment
                                    profiles, sentiment gaps — uv run jupyter)
tests/test_pipeline.py            ← 13 schema & invariant checks (pytest)
```

**Statistical results (stage 4):**

| Test | Question | Result | Verdict |
|---|---|---|---|
| Mann-Whitney U | Do Champions earn higher helpfulness ratios than Casual reviewers? | U = 564M, p = 2.6e-153; medians 0.93 vs 1.00 | Significant — but *reversed*: Casual reviewers are trusted more per review |
| Chi-square | Is sentiment independent of segment? | χ² = 948.8, dof = 10, p ≈ 2e-197, Cramér's V = 0.035 | Significant, weak effect — tone differs slightly by segment |
| OLS (statsmodels) | What drives influence (log helpful votes)? | n = 256,059, adj-R² = 0.203; all four features significant | Breadth (# products) drives influence; volume per product dilutes it |
| Power analysis | Reviews needed to detect a 0.05 polarity shift? | d = 0.113 → 1,238 per group at α = 0.05, power = 0.80 | Any sentiment A/B test needs ≥ 1,238 reviews per arm |

---

## 4. Reproducibility (uv)

Zero hard-coding: all thresholds live in `CONFIG` blocks at the top of each script; seeds are explicit (`random_seed = 42`); the environment is fully pinned.

```bash
# 1. Get the data: Kaggle "Amazon Fine Food Reviews" → database.sqlite
#    https://www.kaggle.com/datasets/snap/amazon-fine-food-reviews
#    (place it anywhere, then point the pipeline at it)
export AMAZON_DB=/path/to/database.sqlite   # default: ../Amazon/database.sqlite

# 2. Reproduce the environment (requires uv: brew install uv)
uv sync

# 3. Run the pipeline end-to-end
.venv/bin/python python/01_clean_and_engineer.py
.venv/bin/python python/02_sentiment_and_insights.py     # ~35 s
.venv/bin/python python/04_statistics_and_modeling.py
.venv/bin/python python/03_build_dashboard.py            # regenerates dashboard.html

# 4. Validate
.venv/bin/python -m pytest tests/ -v                     # 13 checks, all must pass
```

---

## 5. Repository Layout

```
├── dashboard.html              ← THE deliverable (self-contained, open in any browser)
├── pyproject.toml / uv.lock    ← pinned, reproducible environment
├── sql/
│   ├── 01_data_quality_audit.sql
│   └── 02_customer_master.sql  ← all cleaning + segmentation logic
├── python/
│   ├── 01_clean_and_engineer.py
│   ├── 02_sentiment_and_insights.py
│   ├── 03_build_dashboard.py
│   └── 04_statistics_and_modeling.py
├── notebooks/exploration.ipynb  ← interactive layer over the exports (uv run jupyter)
├── tests/test_pipeline.py      ← 13 schema & invariant checks
├── docs/
│   ├── figures/                ← distribution evidence (skew)
│   └── interview_prep.md       ← STAR stories & defense answers
├── tableau/build_spec.md       ← spec for the Tableau Public edition
└── exports/                    ← small aggregates shipped; big files regenerate via pipeline
```

The 356 MB raw database and the two large exports (review-level and customer-level CSVs) are **gitignored** — the repo stays lean, and anyone can regenerate every number from the Kaggle source with the commands above. The small aggregate exports (segment summary, monthly timeline, sentiment tables, advocate list, KPIs, audit log, statistics) **are** shipped so the notebook and dashboard build work out of the box.

---

## 6. Roadmap

- [x] SQL audit + segmentation (single source of truth)
- [x] Full-dataset sentiment with validation & gap analysis
- [x] Inferential statistics + regression + power analysis
- [x] Generated interactive dashboard (this repo)
- [ ] Tableau Public edition (see `tableau/build_spec.md`)
- [ ] Cohort retention curves by acquisition month

## License

MIT — see [LICENSE](LICENSE). Data: [Amazon Fine Food Reviews](https://www.kaggle.com/datasets/snap/amazon-fine-food-reviews) (Kaggle / SNAP), used under its public research terms.

---

Built and verified by Meenakshi Sethi. Dataset: Amazon Fine Food Reviews (Kaggle / SNAP) — real customer review data.
