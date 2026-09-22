"""
04_statistics_and_modeling.py
=============================
Stage 4 of the pipeline: inferential statistics & regression.

The descriptive dashboard (stage 3) SUGGESTS patterns; this stage PROVES them
to financial-tech evidentiary standards. Every test maps a business question
to the right statistical tool, with the reasoning documented inline:

  1. Descriptive profiling — baselines + skew (why we avoid averages-only
     storytelling). Figures exported for the README.
  2. Mann-Whitney U (non-parametric) — "Are Champions more TRUSTED than Casual
     reviewers?" Helpfulness ratio is bounded in [0,1] and heavily skewed, so
     a t-test's normality assumption would be invalid. Non-parametric it is.
  3. Chi-square + Cramér's V — "Is sentiment independent of segment?" If not,
     segment membership predicts voice tone, which matters for targeting.
  4. OLS regression (statsmodels, not sklearn) — "What drives customer
     INFLUENCE (helpfulness votes earned)?" statsmodels is chosen deliberately
     because it outputs coefficients, standard errors, and p-values — an
     analyst must explain WHY a variable matters, not just predict.
  5. Power analysis — "How many reviews would we need to detect a 0.05 shift
     in sentiment after a product change?" Prevents under-powered experiments
     (useless results) and over-long ones (wasted budget).

Outputs:
    exports/stats_summary.json  — all test results for dashboard & README
    docs/figures/*.png          — distribution figures (skew evidence)

Run:  .venv/bin/python python/04_statistics_and_modeling.py
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: never try to open a window
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats as sps
from statsmodels.stats.power import TTestIndPower

# --- config (zero hard-coding below this block) ---------------------------------
CONFIG = {
    "random_seed": 42,          # explicit seed: any stakeholder reruns identically
    "alpha": 0.05,              # significance threshold (documented, challengeable)
    "target_power": 0.80,       # standard 80% power for planning
    "mde_polarity": 0.05,       # minimum detectable effect: 0.05 polarity units
    "mwu_groups": ["Champions", "Casual"],
    "mwu_min_votes": 1,         # only compare customers who earned >= 1 vote
    "ols_target": "log_helpful_votes",
    "ols_features": ["review_count", "products_reviewed", "avg_score", "recency_days"],
    "figure_dpi": 150,
}

np.random.seed(CONFIG["random_seed"])

ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "exports"
FIGURES = ROOT / "docs" / "figures"
FIGURES.mkdir(parents=True, exist_ok=True)

ALPHA = CONFIG["alpha"]

# --- load pipeline outputs -------------------------------------------------------
master = pd.read_csv(EXPORTS / "customer_master.csv")
reviews = pd.read_csv(EXPORTS / "reviews_scored.csv")
print(f"Loaded {len(master):,} customers / {len(reviews):,} scored reviews")

# --- 1. descriptive profiling (baselines + skew) ----------------------------------
profiling = {
    "reviews_per_customer": {
        "mean": round(float(master["review_count"].mean()), 2),
        "median": float(master["review_count"].median()),
        "p90": float(master["review_count"].quantile(0.90)),
        "skew": round(float(master["review_count"].skew()), 2),
    },
    "helpful_votes_per_customer": {
        "mean": round(float(master["helpful_votes"].mean()), 2),
        "median": float(master["helpful_votes"].median()),
        "p90": float(master["helpful_votes"].quantile(0.90)),
        "skew": round(float(master["helpful_votes"].skew()), 2),
    },
    "polarity": {
        "mean": round(float(reviews["polarity"].mean()), 3),
        "median": round(float(reviews["polarity"].median()), 3),
        "skew": round(float(reviews["polarity"].skew()), 2),
        "std": round(float(reviews["polarity"].std()), 3),
    },
}
print("\n--- Profiling (the skew numbers justify every non-parametric choice below) ---")
for metric, vals in profiling.items():
    print(f"  {metric}: {vals}")

# figures — ink-on-paper style to match the editorial dashboard
plt.rcParams.update({
    "figure.facecolor": "#f6f1e7", "axes.facecolor": "#f6f1e7",
    "axes.edgecolor": "#191512", "axes.labelcolor": "#191512",
    "xtick.color": "#7a6f60", "ytick.color": "#7a6f60",
    "font.family": "serif", "font.size": 10,
})

fig, ax = plt.subplots(figsize=(7, 3.2), dpi=CONFIG["figure_dpi"])
ax.hist(master["review_count"], bins=np.arange(0.5, 25.5, 1), color="#274b6d", edgecolor="#f6f1e7")
ax.set_yscale("log")
ax.set_title(f"Reviews per customer — median {profiling['reviews_per_customer']['median']:.0f}, "
             f"mean {profiling['reviews_per_customer']['mean']}, skew {profiling['reviews_per_customer']['skew']} (log scale)")
ax.set_xlabel("reviews per customer"); ax.set_ylabel("customers (log)")
fig.tight_layout(); fig.savefig(FIGURES / "fig1_review_count_dist.png"); plt.close(fig)

fig, ax = plt.subplots(figsize=(7, 3.2), dpi=CONFIG["figure_dpi"])
groups = [reviews.loc[reviews["sentiment"] == s, "polarity"]
          for s in ["Negative", "Neutral", "Positive"]]
ax.hist(groups, bins=60, stacked=True,
        color=["#8f2b1e", "#b3a893", "#41684a"], edgecolor="#f6f1e7", linewidth=0.3)
ax.axvline(0, color="#191512", linewidth=0.8, linestyle=":")
ax.set_title("TextBlob polarity distribution — bounded, tri-modal, non-normal")
ax.set_xlabel("polarity"); ax.set_ylabel("reviews")
fig.tight_layout(); fig.savefig(FIGURES / "fig2_polarity_dist.png"); plt.close(fig)

fig, ax = plt.subplots(figsize=(7, 3.2), dpi=CONFIG["figure_dpi"])
voters = master[master["helpful_votes"] > 0]
ax.hist(voters["helpful_votes"], bins=np.logspace(0, 3, 50), color="#9c2b1f", edgecolor="#f6f1e7")
ax.set_xscale("log"); ax.set_yscale("log")
ax.set_title("Helpfulness votes earned (voters only, log-log) — extreme right skew")
ax.set_xlabel("total helpful votes (log)"); ax.set_ylabel("customers (log)")
fig.tight_layout(); fig.savefig(FIGURES / "fig3_helpful_votes_dist.png"); plt.close(fig)
print(f"\nFigures written to {FIGURES}")

# --- 2. Mann-Whitney U: are Champions more trusted than Casual reviewers? ---------
g1, g2 = CONFIG["mwu_groups"]
sample = master[
    (master["segment"].isin(CONFIG["mwu_groups"]))
    & (master["total_votes"] >= CONFIG["mwu_min_votes"])
    & master["helpfulness_ratio"].notna()
]
x1 = sample.loc[sample["segment"] == g1, "helpfulness_ratio"]
x2 = sample.loc[sample["segment"] == g2, "helpfulness_ratio"]
u_stat, p_mwu = sps.mannwhitneyu(x1, x2, alternative="two-sided")
mwu = {
    "test": "Mann-Whitney U (two-sided)",
    "question": f"Do {g1} earn a higher helpfulness ratio than {g2} reviewers?",
    "why_nonparametric": "helpfulness ratio is bounded [0,1] and skewed; t-test normality invalid",
    "groups": CONFIG["mwu_groups"],
    "n": [int(x1.size), int(x2.size)],
    "median": [round(float(x1.median()), 3), round(float(x2.median()), 3)],
    "u_statistic": round(float(u_stat), 1),
    "p_value": float(p_mwu),
    "significant": bool(p_mwu < ALPHA),
}
print(f"\n--- Mann-Whitney U ({g1} vs {g2}, helpfulness ratio) ---")
print(f"  medians: {mwu['median'][0]} vs {mwu['median'][1]}  |  U={mwu['u_statistic']:,}  p={p_mwu:.2e}")

# --- 3. Chi-square: is sentiment independent of segment? ---------------------------
r = reviews.merge(master[["UserId", "segment"]], on="UserId", how="left")
ct = pd.crosstab(r["segment"], r["sentiment"])
chi2, p_chi2, dof, _ = sps.chi2_contingency(ct)
n_obs = int(ct.values.sum())
cramers_v = float(np.sqrt(chi2 / (n_obs * (min(ct.shape) - 1))))
chi2_res = {
    "test": "Chi-square test of independence",
    "question": "Is review sentiment independent of customer segment?",
    "chi2": round(float(chi2), 1),
    "dof": int(dof),
    "p_value": float(p_chi2),
    "cramers_v": round(cramers_v, 3),
    "effect_label": "weak" if cramers_v < 0.1 else ("moderate" if cramers_v < 0.3 else "strong"),
    "significant": bool(p_chi2 < ALPHA),
}
print(f"\n--- Chi-square (segment x sentiment) ---")
print(f"  chi2={chi2_res['chi2']:,} dof={dof} p={p_chi2:.2e} Cramér's V={cramers_v} ({chi2_res['effect_label']})")

# --- 4. OLS: what drives customer influence? ----------------------------------------
# Target is log1p(helpful_votes): the raw count is extremely skewed (see fig3),
# so we model the log scale — a standard, documented transformation.
ols_df = master.dropna(subset=["helpful_votes"] + CONFIG["ols_features"]).copy()
ols_df[CONFIG["ols_target"]] = np.log1p(ols_df["helpful_votes"])
formula = f"{CONFIG['ols_target']} ~ " + " + ".join(CONFIG["ols_features"])
model = smf.ols(formula, data=ols_df).fit()
coefs = [
    {"name": name, "coef": round(float(coef), 4), "p_value": float(model.pvalues[name])}
    for name, coef in model.params.items()
]
ols_res = {
    "test": "OLS regression (statsmodels)",
    "question": "What drives customer influence (helpfulness votes earned)?",
    "why_log_target": "raw votes are extremely right-skewed; log1p is the documented transform",
    "n": int(model.nobs),
    "r_squared": round(float(model.rsquared), 3),
    "adj_r_squared": round(float(model.rsquared_adj), 3),
    "f_p_value": float(model.f_pvalue),
    "coefficients": coefs,
}
print(f"\n--- OLS: {formula} ---")
print(f"  n={ols_res['n']:,}  R²={ols_res['r_squared']}  adj-R²={ols_res['adj_r_squared']}")
for c in coefs:
    star = " *" if c["p_value"] < ALPHA else ""
    print(f"  {c['name']:<20} coef={c['coef']:>9.4f}  p={c['p_value']:.2e}{star}")

# --- 5. power analysis: sizing a sentiment-shift experiment -------------------------
polarity_std = float(reviews["polarity"].std())
effect_size = CONFIG["mde_polarity"] / polarity_std  # Cohen's d
analysis = TTestIndPower()
n_per_group = int(np.ceil(
    analysis.solve_power(effect_size=effect_size, alpha=ALPHA,
                         power=CONFIG["target_power"], ratio=1.0)
))
power_res = {
    "test": "Power analysis (TTestIndPower)",
    "question": "How many reviews per group to detect a 0.05 polarity shift at 80% power?",
    "mde": CONFIG["mde_polarity"],
    "polarity_std": round(polarity_std, 3),
    "cohens_d": round(effect_size, 3),
    "alpha": ALPHA,
    "power": CONFIG["target_power"],
    "n_per_group": n_per_group,
}
print(f"\n--- Power analysis ---")
print(f"  d={power_res['cohens_d']}  ->  {n_per_group:,} reviews per group "
      f"(~{n_per_group * 2 / 480:.0f} days at 2012 review volumes)")

# --- export -------------------------------------------------------------------------
summary = {
    "config": {k: v for k, v in CONFIG.items() if k != "figure_dpi"},
    "profiling": profiling,
    "mannwhitney": mwu,
    "chi_square": chi2_res,
    "ols": ols_res,
    "power": power_res,
}
with open(EXPORTS / "stats_summary.json", "w") as f:
    json.dump(summary, f, indent=2)
print("\nExported exports/stats_summary.json")

# --- validation asserts (fail loudly if new data breaks invariants) -----------------
assert set(CONFIG["mwu_groups"]) <= set(master["segment"].unique()), "segment labels drifted"
assert 0 <= mwu["p_value"] <= 1 and 0 <= p_chi2 <= 1, "p-value out of range"
assert 0 <= model.rsquared <= 1, "R² out of range"
assert n_per_group > 0, "power analysis returned non-positive n"
print("All validation asserts passed.")
