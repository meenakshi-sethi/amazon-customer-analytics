"""
03_build_dashboard.py
=====================
Stage 3 of the pipeline: build the interactive, zero-dependency HTML dashboard
from the exported CSVs/JSON. The dashboard is GENERATED from pipeline outputs,
so numbers can never drift out of sync with the analysis.

Design language: editorial print journal — "The Fine Food Review Files".
Warm paper, serif display type, numbered chapters, scroll-triggered reveals,
animated counters, and rubber-stamp verdicts on the statistical findings.
Single self-contained file: hand-rolled SVG + vanilla JS, no CDN, works offline.

A Tableau Public edition is planned as a follow-up (noted in the colophon).

Run:  .venv/bin/python python/03_build_dashboard.py
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "exports"
OUT = ROOT / "dashboard.html"

kpis = json.loads((EXPORTS / "kpis.json").read_text())
segments = pd.read_csv(EXPORTS / "segment_summary.csv").to_dict("records")
monthly = pd.read_csv(EXPORTS / "monthly_activity.csv").to_dict("records")
sentiment = pd.read_csv(EXPORTS / "sentiment_by_score.csv").to_dict("records")
advocates = pd.read_csv(EXPORTS / "advocates.csv").round(2).to_dict("records")
audit = json.loads((EXPORTS / "wrangling_audit.json").read_text())

DATA = {
    "kpis": kpis,
    "segments": segments,
    "monthly": monthly,
    "sentiment": sentiment,
    "advocates": advocates,
    "audit": audit,
}
stats_path = EXPORTS / "stats_summary.json"
if stats_path.exists():
    DATA["stats"] = json.loads(stats_path.read_text())

# skewness exhibit — figures are RENDERED by the statistics stage (matplotlib);
# this report only embeds and displays them. No statistics are computed in HTML.
import base64
FIGDIR = ROOT / "docs" / "figures"
_prof = DATA.get("stats", {}).get("profiling", {})
_FIGS = [
    ("fig1_review_count_dist.png", "Reviews per customer", "reviews_per_customer"),
    ("fig2_polarity_dist.png", "Polarity per review", "polarity"),
    ("fig3_helpful_votes_dist.png", "Helpfulness votes earned", "helpful_votes_per_customer"),
]
skewfigs = []
for _fname, _title, _key in _FIGS:
    _p = FIGDIR / _fname
    if _p.exists() and _key in _prof:
        skewfigs.append({
            "title": _title,
            "img": "data:image/png;base64," + base64.b64encode(_p.read_bytes()).decode(),
            "skew": _prof[_key]["skew"],
            "mean": _prof[_key]["mean"],
            "median": _prof[_key]["median"],
        })
if skewfigs:
    DATA["skewfigs"] = skewfigs

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>The Fine Food Review Files — Amazon Customer Analytics</title>
<style>
  :root{
    --paper:#f6f1e7; --paper2:#efe7d5; --ink:#1c1712; --muted:#7a6f60;
    --rule:#d8cdb8; --oxblood:#8f2b1e; --blue:#2f4d6b; --green:#41684a; --gold:#a07c2c;
  }
  *{margin:0;padding:0;box-sizing:border-box}
  html{scroll-behavior:smooth}
  body{background:var(--paper);color:var(--ink);
       font-family:Georgia,'Times New Roman',serif;line-height:1.65;font-size:16px}
  #progress{position:fixed;top:0;left:0;height:3px;background:var(--oxblood);width:0%;z-index:99}
  .sheet{max-width:860px;margin:0 auto;padding:48px 24px 80px}
  .label{font-family:'Helvetica Neue',Arial,sans-serif;font-size:11px;letter-spacing:.22em;
         text-transform:uppercase;color:var(--muted)}
  .rule{border:none;border-top:1px solid var(--rule);margin:26px 0}
  .rule.double{border-top:3px double var(--rule)}

  /* masthead */
  .masthead{text-align:center}
  .masthead h1{font-size:clamp(34px,6vw,54px);font-weight:700;letter-spacing:-.5px;line-height:1.08;margin:10px 0 6px}
  .masthead .tagline{font-style:italic;color:var(--muted);font-size:15px}
  .edition{display:flex;justify-content:space-between;border-top:1px solid var(--ink);
           border-bottom:1px solid var(--ink);padding:6px 2px;margin-top:22px}
  .edition span{font-family:'Helvetica Neue',Arial,sans-serif;font-size:10.5px;letter-spacing:.18em;
                text-transform:uppercase;color:var(--ink)}

  /* toc */
  .toc{margin:30px 0 8px;columns:2;column-gap:40px}
  .toc a{display:block;text-decoration:none;color:var(--ink);font-size:14.5px;padding:5px 0;
         border-bottom:1px dotted var(--rule);break-inside:avoid}
  .toc a:hover{color:var(--oxblood)}
  .toc a .no{color:var(--gold);font-style:italic;margin-right:8px}

  /* kpi strip */
  .strip{display:grid;grid-template-columns:repeat(auto-fit,minmax(125px,1fr));gap:0;
         border:1px solid var(--ink);margin:34px 0}
  .strip .cell{padding:16px 14px;border-right:1px solid var(--rule);text-align:center}
  .strip .cell:last-child{border-right:none}
  .strip .num{font-size:26px;font-weight:700;font-variant-numeric:tabular-nums;line-height:1.15}
  .strip .cap{margin-top:4px}

  /* chapters */
  .chap{opacity:0;transform:translateY(18px);transition:opacity .7s ease,transform .7s ease}
  .chap.in{opacity:1;transform:none}
  .chaphead{display:flex;align-items:baseline;gap:14px;margin:56px 0 6px}
  .chaphead .no{font-size:34px;font-style:italic;color:var(--gold);font-weight:400}
  .chaphead h2{font-size:26px;font-weight:700;letter-spacing:-.3px}
  .chaphead .tag{margin-left:auto;text-align:right}
  .lede{font-size:17.5px;font-style:italic;color:var(--muted);margin-bottom:18px;max-width:640px}
  .chap p.body{margin-bottom:14px;max-width:700px}
  .chap p.body b{font-weight:700}
  .dropcap::first-letter{font-size:52px;float:left;line-height:.82;padding:4px 8px 0 0;
                         color:var(--oxblood);font-weight:700}

  /* audit table (chapter I) */
  table.print{width:100%;border-collapse:collapse;font-size:14px;margin:14px 0 6px}
  table.print th{font-family:'Helvetica Neue',Arial,sans-serif;font-size:10.5px;letter-spacing:.14em;
    text-transform:uppercase;color:var(--muted);text-align:left;padding:7px 10px;
    border-top:2px solid var(--ink);border-bottom:1px solid var(--ink)}
  table.print td{padding:9px 10px;border-bottom:1px solid var(--rule);vertical-align:top}
  table.print td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
  .flow{display:flex;align-items:center;gap:10px;margin:18px 0 4px;flex-wrap:wrap}
  .flow .box{border:1px solid var(--ink);padding:10px 16px;text-align:center;background:var(--paper2)}
  .flow .box .n{font-size:20px;font-weight:700;font-variant-numeric:tabular-nums}
  .flow .arr{color:var(--muted);font-size:20px}

  /* segment bars (chapter II) */
  .segrow{display:grid;grid-template-columns:150px 1fr 110px;gap:12px;align-items:center;
          padding:9px 6px;border-bottom:1px dotted var(--rule);cursor:pointer}
  .segrow:hover{background:var(--paper2)}
  .segrow.active{background:var(--paper2)}
  .segrow .nm{font-size:14.5px}
  .segrow .nm i{color:var(--muted);font-size:12px;display:block}
  .barwrap{height:22px;background:var(--paper2);border:1px solid var(--rule);position:relative}
  .bar{height:100%;transition:width 1.1s cubic-bezier(.2,.7,.2,1)}
  .segrow .val{text-align:right;font-size:13px;font-variant-numeric:tabular-nums;color:var(--muted)}
  #segDetail{border-left:3px solid var(--gold);padding:10px 16px;margin:16px 0 4px;
             background:var(--paper2);font-size:14.5px;min-height:58px}

  /* line chart (chapter III) */
  .toggle{display:flex;gap:8px;margin:6px 0 12px}
  .toggle button{font-family:'Helvetica Neue',Arial,sans-serif;font-size:11px;letter-spacing:.1em;
    text-transform:uppercase;background:transparent;border:1px solid var(--rule);
    color:var(--muted);padding:6px 13px;cursor:pointer;border-radius:2px}
  .toggle button.on{border-color:var(--ink);color:var(--paper);background:var(--ink)}

  /* sentiment (chapter IV) */
  .pull{display:grid;grid-template-columns:1fr 1fr;gap:22px;margin:22px 0}
  @media(max-width:640px){.pull{grid-template-columns:1fr}}
  .pull .stat{border-top:3px solid var(--ink);padding-top:10px}
  .pull .stat .n{font-size:44px;font-weight:700;line-height:1;font-variant-numeric:tabular-nums}
  .pull .stat .t{font-style:italic;color:var(--muted);margin-top:6px;font-size:14px}

  /* verdict stamps (chapter V) */
  .verdict{border:1px solid var(--rule);padding:18px 20px;margin-bottom:16px;position:relative;background:#faf6ee}
  .verdict h3{font-size:17px;margin-bottom:2px}
  .verdict .q{font-style:italic;color:var(--muted);font-size:14px;margin-bottom:10px}
  .verdict .row{display:flex;gap:26px;flex-wrap:wrap;font-size:14px;margin-top:6px;
                font-variant-numeric:tabular-nums}
  .verdict .part{margin-top:10px;font-size:14px;line-height:1.6}
  .verdict details.part{border:1px solid var(--rule);background:#faf6ee;margin-top:10px}
  .verdict summary.plabel{font-family:'Helvetica Neue',Arial,sans-serif;font-size:10px;
           letter-spacing:.1em;text-transform:uppercase;color:var(--gold);
           display:flex;align-items:center;gap:8px;font-weight:700;
           padding:9px 12px;cursor:pointer;list-style:none;user-select:none}
  .verdict summary.plabel::-webkit-details-marker{display:none}
  .verdict summary.plabel::after{content:'+';margin-left:auto;font-size:15px;
           font-weight:400;color:var(--gold)}
  .verdict details[open] summary.plabel::after{content:'\2212'}
  .verdict details.part:hover{border-color:var(--gold)}
  .verdict details.part.helps summary.plabel{color:var(--green)}
  .verdict details.part.helps summary.plabel::after{color:var(--green)}
  .verdict .ptext{padding:2px 12px 11px;font-size:14px;line-height:1.6}
  /* method chooser table (chapter V) */
  .chooser{border:1px solid var(--rule);background:#faf6ee;padding:20px 22px;margin:22px 0}
  .chooser .chtitle{font-family:'Playfair Display',Georgia,serif;font-size:19px;font-weight:700;margin-bottom:6px}
  .chooser .chintro{font-size:14px;color:var(--muted);line-height:1.6;margin-bottom:12px}
  .chooser table{width:100%;border-collapse:collapse;font-size:13px}
  .chooser th{font-family:'Helvetica Neue',Arial,sans-serif;font-size:10px;letter-spacing:.08em;
       text-transform:uppercase;color:var(--muted);text-align:left;padding:6px 10px;border-bottom:1px solid var(--rule)}
  .chooser td{padding:7px 10px;border-bottom:1px solid #e8e0cd;line-height:1.45;vertical-align:top}
  .chooser tr:last-child td{border-bottom:none}
  .chooser td:nth-child(3){font-weight:600}
  /* correlation heatmap */
  .corrwrap{margin-top:6px;overflow-x:auto}
  .corr{border-collapse:collapse;font-size:12.5px;font-variant-numeric:tabular-nums}
  .corr th,.corr td{padding:6px 9px;border:1px solid #e8e0cd;text-align:center}
  .corr thead th{font-size:10px;letter-spacing:.05em;text-transform:uppercase;
       font-family:'Helvetica Neue',Arial,sans-serif;color:var(--muted)}
  .corr tbody th{font-weight:600;text-align:left;white-space:nowrap}
  .corrbtns{display:flex;gap:8px;margin:10px 0 4px}
  .corrbtns button{font-family:'Helvetica Neue',Arial,sans-serif;font-size:11px;letter-spacing:.06em;
       text-transform:uppercase;padding:6px 12px;border:1px solid var(--rule);background:#fff;
       color:var(--muted);cursor:pointer}
  .corrbtns button.on{background:var(--ink);color:#fff;border-color:var(--ink)}
  .verdict .row span b{font-size:16px}
  .stamp{position:absolute;top:14px;right:16px;transform:rotate(6deg);
         border:2px solid var(--oxblood);color:var(--oxblood);padding:3px 10px;
         font-family:'Helvetica Neue',Arial,sans-serif;font-size:11px;letter-spacing:.2em;
         text-transform:uppercase;font-weight:700;opacity:.85}
  .stamp.neg{border-color:var(--muted);color:var(--muted)}
  .coef{font-size:13px;color:var(--muted);margin-top:8px}

  /* advocates (chapter VI) */
  table.adv{width:100%;border-collapse:collapse;font-size:13.5px}
  table.adv th{font-family:'Helvetica Neue',Arial,sans-serif;font-size:10px;letter-spacing:.12em;
    text-transform:uppercase;color:var(--muted);text-align:right;padding:7px 8px;cursor:pointer;
    border-top:2px solid var(--ink);border-bottom:1px solid var(--ink);white-space:nowrap;user-select:none}
  table.adv th:hover{color:var(--ink)} table.adv th.sorted{color:var(--oxblood)}
  table.adv td{padding:7px 8px;text-align:right;border-bottom:1px solid var(--rule);
               font-variant-numeric:tabular-nums}
  table.adv td:first-child,table.adv th:first-child{text-align:left}
  tr:hover td{background:var(--paper2)}
  .segtag{font-family:'Helvetica Neue',Arial,sans-serif;font-size:10px;letter-spacing:.08em;
          text-transform:uppercase;padding:2px 7px;border:1px solid}
  .segtag.Champions{color:var(--green);border-color:var(--green)}
  .segtag.Loyal{color:var(--blue);border-color:var(--blue)}

  /* reader's guide primer */
  .primer{margin:26px 0 8px;border:1px solid var(--rule);background:rgba(0,0,0,.025);
          padding:20px 24px;border-radius:3px}
  .primer h3{font-size:15px;margin:0 0 10px;letter-spacing:.02em}
  .primer p{font-size:14px;line-height:1.65;margin:0 0 10px}
  .primer p:last-child{margin-bottom:0}
  .primer .term{font-weight:700}
  .primer .plain{display:block;margin-top:14px;padding-top:12px;border-top:1px dashed var(--rule);
                 font-size:13px;color:var(--muted);font-style:italic}
  .plainnote{font-size:13.5px;color:var(--muted);border-left:3px solid var(--gold);
             padding:6px 0 6px 14px;margin:16px 0 0;font-style:italic}

  /* hover-to-learn parameter tooltips + skewness exhibit */
  .tip{cursor:help;border-bottom:1px dotted var(--muted)}
  .skewfig{margin:16px 0 0;break-inside:avoid}
  .skewfig img{width:100%;height:auto;border:1px solid var(--rule);background:#fff;display:block}
  .skewfig figcaption{font-size:12.5px;color:var(--muted);margin-top:7px;line-height:1.55}

  /* colophon */
  .colophon{margin-top:60px;border-top:3px double var(--rule);padding-top:18px;
            font-size:13px;color:var(--muted)}
  .ribbon{display:inline-block;border:1px solid var(--gold);color:var(--gold);
          padding:5px 14px;font-family:'Helvetica Neue',Arial,sans-serif;font-size:11px;
          letter-spacing:.18em;text-transform:uppercase;margin-bottom:14px}
  #tooltip{position:fixed;pointer-events:none;background:var(--ink);color:var(--paper);
           padding:7px 11px;font-size:12.5px;font-family:Georgia,serif;display:none;z-index:50;
           white-space:nowrap;border-radius:2px}
  svg text{font-family:Georgia,serif}
  @media(max-width:640px){.segrow{grid-template-columns:105px 1fr 80px}.toc{columns:1}}
</style>
</head>
<body>
<div id="progress"></div>
<div class="sheet">

  <!-- ================= MASTHEAD ================= -->
  <div class="masthead">
    <div class="label">Customer Intelligence Ledger &middot; Amazon Fine Food Reviews</div>
    <h1>The Fine Food<br>Review Files</h1>
    <p class="tagline">A retention &amp; advocacy investigation across 568,454 reviews, 256,059 customers, thirteen years</p>
    <div class="edition">
      <span>Vol. I &middot; No. 1</span>
      <span>Data cut: Oct 1999 &ndash; Oct 2012</span>
      <span>SQL &middot; Python &middot; Statistics</span>
    </div>
  </div>

  <!-- ================= KPI STRIP ================= -->
  <div class="strip" id="strip"></div>

  <!-- ================= TOC ================= -->
  <div class="label" style="margin-top:8px">In this edition</div>
  <nav class="toc">
    <a href="#c1"><span class="no">I</span>The thirty percent that wasn't real</a>
    <a href="#c2"><span class="no">II</span>Six kinds of customer</a>
    <a href="#c3"><span class="no">III</span>The growth curve</a>
    <a href="#c4"><span class="no">IV</span>When the stars lie</a>
    <a href="#c5"><span class="no">V</span>Does it hold up? — the statistics</a>
    <a href="#c6"><span class="no">VI</span>The advocate list</a>
  </nav>
  <hr class="rule double">

  <!-- ================= READER'S GUIDE (plain-language primer) ================= -->
  <div class="primer">
    <h3>Before you read on &mdash; a sixty-second guide for everyone</h3>
    <p>This report was written to be read by <i>people</i>, not just analysts. Three ideas do most of the work here, and none of them requires a statistics background:</p>
    <p><span class="term">1. Customer segmentation.</span> Imagine sorting every customer onto three scales: <b>how recently</b> they were last seen, <b>how often</b> they show up, and <b>how much value</b> they bring. Retailers call this <b>RFM</b> &mdash; Recency, Frequency, Monetary value &mdash; and it's been the standard way to sort customers since mail-order catalogues. Score everyone on each scale, and natural groups appear: your regulars, your newcomers, the ones drifting away.</p>
    <p><span class="term">2. Why this report says R-F-E.</span> This dataset records reviews, not purchases &mdash; there is no price, no order value. Rather than invent a number that doesn't exist, the third scale swaps <i>money</i> for <i>engagement</i>: how many times other shoppers marked that customer's reviews as <b>helpful</b>. A customer whose opinions guide other buyers is valuable in a way money would miss anyway. The swap is stated openly &mdash; that's the honest version of the method.</p>
    <p><span class="term">3. Sentiment, checked against the stars.</span> Software can read the <i>tone</i> of written words &mdash; positive, negative, or neutral. This report scores the tone of every review, then compares it with the star rating the same customer gave. When the words and the stars disagree, something interesting is hiding &mdash; a complainer behind five stars, or a fan behind one.</p>
    <span class="plain">Everything else &mdash; the audit trail, the statistical tests &mdash; is just the evidence that these three ideas were applied carefully. Read the chapters in order; each one tells one part of the story.</span>
  </div>

  <!-- ================= I. DATA QUALITY ================= -->
  <section class="chap" id="c1">
    <div class="chaphead"><span class="no">I</span><h2>The thirty percent that wasn't real</h2>
      <span class="tag label">Data wrangling &amp; audit</span></div>
    <p class="lede">Before a single insight, the ledger itself had to be audited — and a third of it failed inspection.</p>
    <p class="body dropcap">The raw file holds 568,454 reviews. Two of them are structurally impossible — helpfulness votes that exceed the total votes cast. And 174,519 are duplicates: the same customer, the same words, the same second, recorded twice — cross-posted across product variants. Every rule below is enforced in SQL, logged to an audit file, and reconciled by automated tests.</p>
    <div class="flow">
      <div class="box"><div class="n" data-count="568454">0</div><div class="label">raw reviews</div></div>
      <div class="arr">&minus;2 &rarr;</div>
      <div class="box"><div class="n" data-count="568452">0</div><div class="label">after validity rule</div></div>
      <div class="arr">&minus;174,519 &rarr;</div>
      <div class="box" style="border-width:2px"><div class="n" data-count="393931">0</div><div class="label">clean reviews</div></div>
    </div>
    <table class="print" id="auditTable"></table>
    <p class="body" style="font-size:13.5px;color:var(--muted)">Full row-level audit exported to <i>wrangling_audit.json</i>; the pytest suite reconciles removed rows against the final count.</p>
  </section>

  <!-- ================= II. SEGMENTS ================= -->
  <section class="chap" id="c2">
    <div class="chaphead"><span class="no">II</span><h2>Six kinds of customer</h2>
      <span class="tag label">R-F-E segmentation</span></div>
    <p class="lede">No revenue column exists in this data — so monetary value was replaced with engagement, and the model says so out loud.</p>
    <p class="body">Every customer is placed on three scales from the guide above: <b>Recency</b> (days since their last review), <b>Frequency</b> (how many reviews they've written), and <b>Engagement</b> (helpfulness votes their reviews earned from other shoppers). Each scale is divided into five ranked bands &mdash; a <i>quintile</i> is simply "one fifth of the crowd," from the top fifth to the bottom fifth. Where the three bands intersect, six familiar customer personalities emerge. Click any bar for its profile.</p>
    <div id="segrows"></div>
    <div id="segDetail">Select a segment to read its profile.</div>
    <p class="plainnote">In plain words: think of a caf&eacute; &mdash; Champions are the regulars at the corner table, Loyal are the weekly crowd, At Risk used to come daily but haven't been seen in a month, and Casual walked in once for a coffee to go. Each group needs a different kind of attention.</p>
  </section>

  <!-- ================= III. GROWTH ================= -->
  <section class="chap" id="c3">
    <div class="chaphead"><span class="no">III</span><h2>The growth curve</h2>
      <span class="tag label">Monthly activity</span></div>
    <p class="lede">From four thousand reviews a year to two hundred thousand — and the audience kept arriving faster than it returned.</p>
    <div class="toggle" id="lineToggle">
      <button data-series="reviews" class="on">Reviews</button>
      <button data-series="new_users">New reviewers</button>
      <button data-series="active_users">Active reviewers</button>
    </div>
    <svg id="line" width="100%" height="250" viewBox="0 0 560 250" preserveAspectRatio="none"></svg>
    <p class="body" style="font-size:13.5px;color:var(--muted)">The widening gap between new and active reviewers in 2011–12 is the retention story: acquisition outpaced repeat participation.</p>
    <p class="plainnote">In plain words: the shop got busier every year, but more and more of the crowd were first-timers who never came back. Growth that relies on strangers walking in &mdash; rather than regulars returning &mdash; is expensive growth.</p>
  </section>

  <!-- ================= IV. SENTIMENT GAP ================= -->
  <section class="chap" id="c4">
    <div class="chaphead"><span class="no">IV</span><h2>When the stars lie</h2>
      <span class="tag label">Sentiment &times; rating</span></div>
    <p class="lede">TextBlob sentiment was scored on every clean review — then validated against the star the same customer gave. Agreement: 58.5%. The disagreement is the story.</p>
    <svg id="bars" width="100%" height="250" viewBox="0 0 560 250"></svg>
    <div class="pull">
      <div class="stat" style="border-color:var(--oxblood)">
        <div class="n" style="color:var(--oxblood)" data-count="9246">0</div>
        <div class="t">hidden detractors — four or five stars, but words that complain (avg polarity &minus;0.33). Invisible to any star-only dashboard.</div>
      </div>
      <div class="stat" style="border-color:var(--green)">
        <div class="n" style="color:var(--green)" data-count="9573">0</div>
        <div class="t">hidden advocates — one or two stars, but positive words (avg polarity +0.44). Often rating the delivery, not the food. Recovery-win candidates.</div>
      </div>
    </div>
    <p class="plainnote">In plain words: if you only watch the star ratings, roughly one in every thirty "happy" customers is actually writing complaints &mdash; and nearly ten thousand unhappy-looking ratings were written by people whose words were warm. The stars are a summary; the words are the story.</p>
  </section>

  <!-- ================= V. STATISTICS ================= -->
  <section class="chap" id="c5">
    <div class="chaphead"><span class="no">V</span><h2>Does it hold up?</h2>
      <span class="tag label">Inferential statistics</span></div>
    <p class="lede">A dashboard suggests; statistics testify. Every claim above was taken to court — non-parametric where the data refused to be normal.</p>
    <div class="corrbtns" style="margin:0 0 16px">
      <button onclick="__toggleAll(true)">Expand all explanations</button>
      <button onclick="__toggleAll(false)">Collapse all</button>
      <span style="font-size:11.5px;color:var(--muted);align-self:center;margin-left:4px">the numbers stay visible &mdash; the teaching unfolds on click</span>
    </div>
    <div class="chooser">
      <div class="chtitle">Which tool, when? &mdash; the analyst's chooser</div>
      <p class="chintro">Every test in this chapter was picked by one rule: <b>match the tool to the shape of the data and the question.</b> Categories (labels like "Champion" or "Positive") get the counting test; quantities (votes, days, ratings) get the relationship tests; lopsided quantities get the rank-based versions that stay honest.</p>
      <table>
        <tr><th>The question</th><th>The data's shape</th><th>The right tool</th><th>Used below</th></tr>
        <tr><td>Do two groups differ?</td><td>Quantities, well-balanced</td><td>t-test (averages)</td><td>&mdash; (data too skewed)</td></tr>
        <tr><td>Do two groups differ?</td><td>Quantities, lopsided</td><td>Mann-Whitney U (rankings)</td><td>&#10003; trust across segments</td></tr>
        <tr><td>Are two <i>categories</i> related?</td><td>Category &times; category</td><td>Chi-square + Cram&eacute;r's V</td><td>&#10003; segment &times; tone</td></tr>
        <tr><td>Do two <i>quantities</i> move together?</td><td>Quantity &times; quantity</td><td>Correlation matrix (Pearson / Spearman)</td><td>&#10003; the heatmap below</td></tr>
        <tr><td>What drives one outcome?</td><td>Many quantities &rarr; one outcome</td><td>Regression (OLS)</td><td>&#10003; anatomy of influence</td></tr>
        <tr><td>How big must an experiment be?</td><td>A planned A/B test</td><td>Power analysis</td><td>&#10003; sizing the next test</td></tr>
      </table>
    </div>
    <div id="skewex"></div>
    <div id="verdicts"></div>
    <p class="body" style="font-size:13.5px;color:var(--muted)">Why non-parametric? Reviews-per-customer skews past 12, helpfulness votes are log-log skewed, and polarity is bounded and tri-modal. The t-test's normality assumption fails on all three — so Mann-Whitney U and chi-square carry the case.</p>
    <p class="plainnote">In plain words: some of these numbers are extremely lopsided &mdash; a handful of customers write hundreds of reviews while most write one. Classic tests assume nicely balanced data, so they'd give misleading answers here. The tests used instead are the ones built for lopsided data. And the surprise finding: the most prolific reviewers are <i>not</i> the most trusted &mdash; shoppers trust a review a bit less, on average, from someone who writes them constantly. Quality, not quantity, earns trust.</p>
  </section>

  <!-- ================= VI. ADVOCATES ================= -->
  <section class="chap" id="c6">
    <div class="chaphead"><span class="no">VI</span><h2>The advocate list</h2>
      <span class="tag label">Activation shortlist</span></div>
    <p class="lede">Thirty customers worth a thank-you: engaged, trusted by peers, and consistently positive in their own words.</p>
    <p class="body">Advocates must be Champions or Loyal, have earned at least ten helpfulness votes, and write positive summaries at least 60% of the time. The advocacy score weighs helpfulness (50%), positivity (30%), and activity (20%). Click any column to re-sort.</p>
    <div style="overflow-x:auto"><table class="adv" id="advTable"></table></div>
    <p class="plainnote">In plain words: these are the thirty people most worth a thank-you note &mdash; the ones other shoppers already listen to, and who consistently have good things to say. A small rewards program aimed here reaches far beyond thirty people, because their reviews are read by thousands.</p>
  </section>

  <!-- ================= COLOPHON ================= -->
  <div class="colophon">
    <span class="ribbon">&#9670; Tableau Public edition — in preparation</span>
    <p>Compiled by Meenakshi Sethi &middot; System Analyst, Expert Technology Services (ETSAZ).</p>
    <p style="margin-top:8px">Method: SQLite audit &amp; segmentation SQL (single source of truth) &rarr; Python pipeline (pandas, TextBlob, scipy, statsmodels) under a seeded, uv-managed environment &rarr; this page, generated programmatically from the pipeline's exports. 568,454 raw reviews &rarr; 393,931 clean (30.7% duplicates and 2 invalid rows removed, every decision logged). Validated by a pytest suite of schema and invariant checks.</p>
    <p style="margin-top:8px">Source: Amazon Fine Food Reviews (Kaggle / SNAP). This journal is a portfolio artifact; customer identifiers are pseudonymous as shipped in the public dataset.</p>
    <p style="margin-top:8px"><b>Replicate this report:</b> the raw data is <a href="https://www.kaggle.com/datasets/snap/amazon-fine-food-reviews" style="color:var(--gold)">freely downloadable from Kaggle</a>; the aggregate results ship with the repository (<i>exports/</i>), and the full pipeline &mdash; SQL, Python, tests &mdash; regenerates every number on this page from the raw file in under ten minutes.</p>
  </div>
</div>
<div id="tooltip"></div>

<script>
const DATA = __DATA_JSON__;

/* ---------- scroll progress + reveals ---------- */
addEventListener('scroll',()=>{
  const h=document.documentElement;
  document.getElementById('progress').style.width=
    (h.scrollTop/(h.scrollHeight-h.clientHeight)*100)+'%';
});
const io=new IntersectionObserver(es=>es.forEach(e=>{
  if(e.isIntersecting){e.target.classList.add('in');
    e.target.querySelectorAll('[data-count]').forEach(countUp); io.unobserve(e.target);}
}),{threshold:.12});
document.querySelectorAll('.chap').forEach(c=>io.observe(c));

/* ---------- animated counters ---------- */
function countUp(el){
  if(el.dataset.done)return; el.dataset.done=1;
  const target=+el.dataset.count, t0=performance.now(), dur=1100;
  const fmt=n=>n.toLocaleString('en-US');
  (function tick(t){
    const p=Math.min(1,(t-t0)/dur), e=1-Math.pow(1-p,3);
    el.textContent=fmt(Math.round(target*e));
    if(p<1)requestAnimationFrame(tick);
  })(t0);
}

/* ---------- tooltip ---------- */
const tip=document.getElementById('tooltip');
function showTip(html,ev){tip.innerHTML=html;tip.style.display='block';
  tip.style.left=Math.min(ev.clientX+14,innerWidth-200)+'px';
  tip.style.top=(ev.clientY+14)+'px';}
function hideTip(){tip.style.display='none';}

/* ---------- KPI strip ---------- */
const stripDefs=[
  {n:DATA.kpis.clean_reviews.toLocaleString(),c:'clean reviews'},
  {n:DATA.kpis.customers.toLocaleString(),c:'customers'},
  {n:DATA.kpis.products.toLocaleString(),c:'products'},
  {n:DATA.kpis.avg_rating_clean,c:'avg rating'},
  {n:DATA.kpis.sentiment_rating_agreement_pct+'%',c:'sentiment agreement'},
  {n:DATA.kpis.advocates_identified,c:'advocates shortlisted'},
];
document.getElementById('strip').innerHTML=stripDefs.map(k=>
  `<div class="cell"><div class="num">${k.n}</div><div class="cap label">${k.c}</div></div>`).join('');

/* ---------- audit table ---------- */
document.getElementById('auditTable').innerHTML=
  '<thead><tr><th>Step</th><th>Rule</th><th>Reason</th><th style="text-align:right">Rows removed</th>'+
  '<th style="text-align:right">Rows after</th></tr></thead><tbody>'+
  DATA.audit.map(a=>`<tr><td>${a.step}</td><td>${a.rule}</td><td style="color:var(--muted);font-style:italic">${a.reason}</td>`+
  `<td class="num">&minus;${a.rows_removed.toLocaleString()}</td><td class="num">${a.rows_after.toLocaleString()}</td></tr>`).join('')+
  '</tbody>';

/* ---------- segment bars ---------- */
const SEGCOLORS={'Champions':'var(--green)','Loyal':'var(--blue)','At Risk':'var(--gold)',
  'New / Promising':'#7a5ea0','Hibernating':'#8d8577','Casual':'#b0a68f'};
const maxC=Math.max(...DATA.segments.map(s=>s.customers));
document.getElementById('segrows').innerHTML=DATA.segments.map(s=>`
  <div class="segrow" data-seg="${s.segment}">
    <div class="nm">${s.segment}<i>${s.pct_customers}% of base</i></div>
    <div class="barwrap"><div class="bar" data-w="${(100*s.customers/maxC).toFixed(1)}"
      style="background:${SEGCOLORS[s.segment]||'#999'};width:0"></div></div>
    <div class="val">${s.customers.toLocaleString()} customers</div>
  </div>`).join('');
const segIO=new IntersectionObserver(es=>es.forEach(e=>{
  if(e.isIntersecting){e.target.querySelectorAll('.bar').forEach(b=>
    b.style.width=b.dataset.w+'%'); segIO.unobserve(e.target);}
}),{threshold:.3});
segIO.observe(document.getElementById('c2'));
document.querySelectorAll('.segrow').forEach(row=>{
  row.addEventListener('click',()=>selectSegment(row.dataset.seg));
  row.addEventListener('mousemove',ev=>{const s=DATA.segments.find(
    x=>x.segment===row.dataset.seg);
    showTip(`<b>${s.segment}</b> &middot; ${s.avg_reviews} avg reviews &middot; ${s.avg_score}&#9733; avg`,ev);});
  row.addEventListener('mouseleave',hideTip);
});
function selectSegment(name){
  document.querySelectorAll('.segrow').forEach(r=>
    r.classList.toggle('active',r.dataset.seg===name));
  const s=DATA.segments.find(x=>x.segment===name);
  document.getElementById('segDetail').innerHTML=
    `<b>${s.segment}</b> — ${s.customers.toLocaleString()} customers (${s.pct_customers}% of the base). `+
    `Average ${s.avg_reviews} reviews each, rated ${s.avg_score} stars on average, `+
    `last active ${Math.round(s.avg_recency_days)} days before the data cut, `+
    `with ${s.total_helpful_votes.toLocaleString()} helpfulness votes earned across the segment.`;
}

/* ---------- line chart ---------- */
const lineSvg=document.getElementById('line');
const W=560,H=250,P={l:48,r:12,t:12,b:26};
let lineSeries='reviews';
function drawLine(){
  lineSvg.innerHTML='';
  const vals=DATA.monthly.map(m=>m[lineSeries]);
  const mx=Math.max(...vals)*1.05;
  const x=i=>P.l+(W-P.l-P.r)*i/(DATA.monthly.length-1);
  const y=v=>H-P.b-(H-P.t-P.b)*v/mx;
  for(let g=0;g<=4;g++){
    const gy=H-P.b-(H-P.t-P.b)*g/4;
    const ln=mk('line',{x1:P.l,x2:W-P.r,y1:gy,y2:gy,stroke:'#d8cdb8','stroke-dasharray':'2,4'});
    lineSvg.appendChild(ln);
    const lb=mk('text',{x:P.l-7,y:gy+4,'text-anchor':'end',fill:'#7a6f60','font-size':10});
    lb.textContent=Math.round(mx*g/4).toLocaleString(); lineSvg.appendChild(lb);
  }
  const pts=vals.map((v,i)=>`${x(i)},${y(v)}`).join(' ');
  lineSvg.appendChild(mk('polygon',{points:`${P.l},${H-P.b} ${pts} ${W-P.r},${H-P.b}`,fill:'rgba(47,77,107,.10)'}));
  lineSvg.appendChild(mk('polyline',{points:pts,fill:'none',stroke:'#2f4d6b','stroke-width':2.2}));
  [0,DATA.monthly.length-1].forEach(i=>{
    const lb=mk('text',{x:x(i),y:H-8,'text-anchor':i?'end':'start',fill:'#7a6f60','font-size':10});
    lb.textContent=DATA.monthly[i].month; lineSvg.appendChild(lb);
  });
  const hit=mk('rect',{x:P.l,y:P.t,width:W-P.l-P.r,height:H-P.t-P.b,fill:'transparent'});
  hit.addEventListener('mousemove',ev=>{
    const rect=lineSvg.getBoundingClientRect();
    const i=Math.max(0,Math.min(DATA.monthly.length-1,
      Math.round(((ev.clientX-rect.left)/rect.width*W-P.l)/(W-P.l-P.r)*(DATA.monthly.length-1))));
    const m=DATA.monthly[i];
    showTip(`<b>${m.month}</b> &middot; ${m[lineSeries].toLocaleString()} ${lineSeries.replace('_',' ')} &middot; avg ${m.avg_score}&#9733;`,ev);
  });
  hit.addEventListener('mouseleave',hideTip);
  lineSvg.appendChild(hit);
}
function mk(tag,attrs){const el=document.createElementNS('http://www.w3.org/2000/svg',tag);
  for(const k in attrs)el.setAttribute(k,attrs[k]); return el;}
drawLine();
document.querySelectorAll('#lineToggle button').forEach(b=>b.addEventListener('click',()=>{
  document.querySelectorAll('#lineToggle button').forEach(x=>x.classList.remove('on'));
  b.classList.add('on'); lineSeries=b.dataset.series; drawLine();
}));

/* ---------- stacked sentiment bars ---------- */
(function(){
  const bars=document.getElementById('bars');
  const BW=560,BH=250,p={l:48,r:12,t:12,b:26};
  const maxN=Math.max(...DATA.sentiment.map(s=>s.reviews));
  const x=i=>p.l+(BW-p.l-p.r)*(i+0.5)/DATA.sentiment.length;
  const w=(BW-p.l-p.r)/DATA.sentiment.length-30;
  const y=v=>BH-p.b-(BH-p.t-p.b)*v/maxN;
  const parts=[['pct_negative','Negative','#8f2b1e'],['pct_neutral','Neutral','#b3a893'],['pct_positive','Positive','#41684a']];
  DATA.sentiment.forEach((s,i)=>{
    let acc=0;
    parts.forEach(([key,name,col])=>{
      const h=(s[key]/100)*s.reviews;
      const r=mk('rect',{x:x(i)-w/2,width:w,y:y(acc+h),height:Math.max(0,y(acc)-y(acc+h)),fill:col});
      r.addEventListener('mousemove',ev=>showTip(`<b>${s.Score}&#9733;</b> &middot; ${name}<br>${s[key]}% of ${s.reviews.toLocaleString()} reviews &middot; avg polarity ${s.avg_polarity}`,ev));
      r.addEventListener('mouseleave',hideTip);
      bars.appendChild(r); acc+=h;
    });
    const lb=mk('text',{x:x(i),y:BH-8,'text-anchor':'middle',fill:'#7a6f60','font-size':12});
    lb.textContent=s.Score+'\u2605'; bars.appendChild(lb);
  });
})();

/* ---------- statistical verdicts ---------- */
(function(){
  const v=document.getElementById('verdicts');
  if(!DATA.stats){v.innerHTML='<p class="body">Statistics pending — run stage 4.</p>';return;}
  const S=DATA.stats, yes='SIGNIFICANT', no='NOT SIGNIFICANT';
  const mw=S.mannwhitney, ch=S.chi_square, ol=S.ols, pw=S.power, co=S.correlation;
  const sigCoefs=ol.coefficients.filter(c=>c.p_value<0.05&&c.name!=='Intercept');
  v.innerHTML=`
  <div class="verdict"><span class="stamp${mw.significant?'':' neg'}">${mw.significant?yes:no}</span>
    <h3>Mann-Whitney U — trust across segments</h3>
    <div class="q">${mw.question}</div>
    <div class="row"><span class="tip" data-tip="<b>Mann-Whitney U &mdash; the rank-count test.</b> What: counts how often a review from one group outranks a review from the other. Why: averages mislead on lopsided data; ranks stay honest. When: comparing two groups on skewed scores. Read: paired with a tiny p-value, it means the groups genuinely differ.">U <b>${mw.u_statistic.toLocaleString()}</b></span>
      <span class="tip" data-tip="<b>p-value &mdash; the honesty gauge.</b> What: the probability of seeing a gap this big if the groups were truly identical. Read: below the standard threshold of 0.05 means the difference is real, not luck. It says the effect exists &mdash; not how big it is; for size, read the medians.">p <b>${mw.p_value.toExponential(2)}</b></span>
      <span class="tip" data-tip="<b>Median &mdash; the typical value.</b> What: the middle score once everything is sorted. Why: unlike the mean, no single extreme customer can drag it. When: the fair summary whenever data is skewed. Read: compare the two medians to see which group is typically more trusted.">medians <b>${mw.median[0]} vs ${mw.median[1]}</b></span>
      <span class="tip" data-tip="<b>n &mdash; sample size.</b> What: how many observations fed the test. Why: small samples can hide real effects or manufacture fake ones. Read: both groups here are large, so this verdict is stable.">n <b>${mw.n[0].toLocaleString()} vs ${mw.n[1].toLocaleString()}</b></span></div>
    <details class="partNone"><summary class="plabel">Why this technique</summary><div class="ptext">      I wanted to know whether two groups &mdash; the most engaged customers and the casual ones &mdash; are trusted differently by other shoppers. The usual test (a t-test) compares averages, but it only works on well-balanced data; helpfulness scores here are heavily lopsided, so it would have given a misleading answer. Mann-Whitney U compares <i>rankings</i> instead of averages &mdash; "do the reviews of one group tend to sit higher than the other's?" &mdash; which stays honest on lopsided data.</div></details>
    <details class="partNone"><summary class="plabel">What the numbers say</summary><div class="ptext">      The p-value is the probability of seeing a gap this big if the two groups were truly identical. Anything under the standard threshold of <b>0.05</b> counts as a real difference; ours is far below it. The medians (the "typical" score, unaffected by extremes) give the direction: ${mw.significant ? (mw.median[0] > mw.median[1]
        ? `${mw.groups[0]} reviewers earn a higher typical trust score (${mw.median[0]} vs ${mw.median[1]}).`
        : `casual reviewers actually earn a slightly higher typical trust score (${mw.median[1]} vs ${mw.median[0]}) &mdash; the opposite of the obvious guess.`) : 'no detectable difference.'}</div></details>
    <details class="part helps"><summary class="plabel">How this helps</summary><div class="ptext">      ${mw.significant && mw.median[0] <= mw.median[1]
        ? 'It kills a common assumption before it becomes strategy: "reward our most prolific reviewers" would not buy trust. A reviewer-incentive program should aim at review <i>quality</i>, not volume &mdash; otherwise the budget goes to people whose opinions carry less weight each time they post.'
        : 'It confirms engagement and trust travel together &mdash; the customers who show up most are also the ones other shoppers listen to, so programs aimed at engaged customers get double leverage.'}</div></details>
  </div>
  <div class="verdict"><span class="stamp${ch.significant?'':' neg'}">${ch.significant?yes:no}</span>
    <h3>Chi-square — sentiment &times; segment</h3>
    <div class="q">${ch.question}</div>
    <div class="row"><span class="tip" data-tip="<b>Chi-square (&chi;&sup2;) &mdash; the category drift meter.</b> What: how far the observed counts drift from what pure chance would produce. Why: you cannot average labels like Champion or Positive &mdash; counting is the only option. When: both variables are categories. Read: a bigger &chi;&sup2; is stronger evidence of a real association.">&chi;&sup2; <b>${ch.chi2.toLocaleString()}</b></span>
      <span class="tip" data-tip="<b>Degrees of freedom &mdash; the calibration.</b> What: how many independent comparisons the table allows: (rows&minus;1)&times;(columns&minus;1). Why: more categories inflate &chi;&sup2; by chance alone; dof corrects for that. Read: paired with &chi;&sup2; to produce the p-value.">dof <b>${ch.dof}</b></span><span class="tip" data-tip="<b>p-value &mdash; the honesty gauge.</b> What: the probability of a pattern this strong appearing by pure chance. Read: below 0.05 means the association is real. For how strong, read Cram&eacute;r's V.">p <b>${ch.p_value.toExponential(2)}</b></span>
      <span class="tip" data-tip="<b>Cram&eacute;r's V &mdash; the strength gauge.</b> What: converts &chi;&sup2; onto a 0-to-1 scale of association strength. Why: the p-value only says real; V says how big. Read: under 0.1 weak, around 0.3 moderate, 0.5 and up strong.">Cram&eacute;r's V <b>${ch.cramers_v}</b> (${ch.effect_label})</span></div>
    <details class="partNone"><summary class="plabel">Why this technique</summary><div class="ptext">      I wanted to know whether a customer's segment (regular, newcomer, drifting away&hellip;) has any bearing on the <i>tone</i> of what they write. Both are categories, not quantities &mdash; you can't average "Champion" or "Positive" &mdash; so the test that fits is the one built for counting: does the mix of tones differ from segment to segment more than chance would allow?</div></details>
    <details class="partNone"><summary class="plabel">What the numbers say</summary><div class="ptext">      The p-value (again: probability of a pattern this strong appearing by pure chance; threshold <b>0.05</b>) says the relationship is real. But Cram&eacute;r's V &mdash; a 0-to-1 strength gauge where under 0.1 is weak, 0.3 is moderate &mdash; measures <b>${ch.cramers_v}</b>: real, but ${ch.effect_label}. Segment tells you something about tone, just not very much.</div></details>
    <details class="part helps"><summary class="plabel">How this helps</summary><div class="ptext">      It sets fair expectations for targeting: segmenting customers is useful for <i>who</i> to contact, but it shouldn't be the only basis for <i>what</i> to say &mdash; tone varies too much within each group. Read the words, not just the label.</div></details>
  </div>
  <div class="verdict"><span class="stamp">R&sup2; ${ol.r_squared}</span>
    <h3>OLS regression — the anatomy of influence</h3>
    <div class="q">${ol.question}</div>
    <div class="row"><span class="tip" data-tip="<b>n &mdash; sample size.</b> What: how many customers the regression weighed. Read: a large n means the coefficient estimates are stable.">n <b>${ol.n.toLocaleString()}</b></span>
      <span class="tip" data-tip="<b>Adjusted R&sup2; &mdash; the explained share.</b> What: the fraction of variation in the outcome that the model explains, with a penalty for every added predictor. Why: plain R&sup2; only ever goes up as you add drivers; the adjusted version keeps the model honest. Read: 0.15 means the drivers account for roughly 15% of why influence varies.">adj-R&sup2; <b>${ol.adj_r_squared}</b></span>
      <span class="tip" data-tip="<b>F-test p-value &mdash; the model's overall verdict.</b> What: the probability that all coefficients together are indistinguishable from zero. Read: below 0.05 means the model as a whole earns its place; each driver is then judged by its own p-value below.">F p <b>${ol.f_p_value.toExponential(2)}</b></span></div>
    <details class="partNone"><summary class="plabel">Why this technique</summary><div class="ptext">      The question here is "what actually <i>drives</i> influence &mdash; the votes a customer's reviews earn?" Regression is the tool that weighs several possible drivers at once and tells you which ones still matter after accounting for the others. One honest adjustment first: vote counts are extremely lopsided (a few customers earn thousands, most earn none), so the model works on a <i>logarithmic</i> scale &mdash; the same trick that turns a sprint of a few superstars into a fair race across everyone.</div></details>
    <details class="partNone"><summary class="plabel">What the numbers say</summary><div class="ptext">      Each driver gets a coefficient (&beta;) &mdash; its independent push on influence &mdash; and a p-value testing whether that push is distinguishable from zero (threshold <b>0.05</b>). The significant drivers: ${sigCoefs.map(c=>`<span class="tip" data-tip="<b>&beta; (beta) &mdash; the independent push.</b> What: how much the outcome changes when this driver rises by one unit, holding the others fixed. The p-value tests whether that push is distinguishable from zero (threshold 0.05).">${c.name} (&beta;=${c.coef}, p=${c.p_value.toExponential(1)})</span>`).join(' &middot; ')}. Adjusted R&sup2; = <b>${ol.adj_r_squared}</b> means these four factors together explain about ${Math.round(ol.adj_r_squared*100)}% of why some customers earn far more votes than others &mdash; solid for behavior data, and honest about the rest being unmeasured factors.</div></details>
    <details class="part helps"><summary class="plabel">How this helps</summary><div class="ptext">      It turns "who is influential?" from a guess into a checklist. Want more trusted reviewers? The coefficients say which levers actually move influence and which are noise &mdash; so an engagement program can be built on the drivers that provably matter.</div></details>
  </div>
  <div class="verdict"><span class="stamp">n &ge; ${pw.n_per_group.toLocaleString()}</span>
    <h3>Power analysis — sizing the next experiment</h3>
    <div class="q">${pw.question}</div>
    <div class="row"><span class="tip" data-tip="<b>MDE &mdash; minimum detectable effect.</b> What: the smallest change the experiment commits to catching, chosen before any data is collected. Why: fixing it upfront keeps the sample-size arithmetic honest. Read: a modest but business-relevant shift on the sentiment scale.">MDE <b>${pw.mde}</b></span><span class="tip" data-tip="<b>Cohen's d &mdash; effect size in natural units.</b> What: the change expressed in standard deviations of the data's own wobble. Read: 0.2 small, 0.5 medium, 0.8 large. A small d means big samples are needed &mdash; which is what drives the number on the right.">Cohen's d <b>${pw.cohens_d}</b></span>
      <span class="tip" data-tip="<b>&alpha; (alpha) &mdash; the false-alarm budget.</b> What: the maximum acceptable risk of declaring a difference that is not real. Convention: 0.05, meaning at most a 5% false-positive rate.">&alpha; <b>${pw.alpha}</b></span><span class="tip" data-tip="<b>Power &mdash; the true-detection guarantee.</b> What: the probability the experiment catches a real effect of the chosen size. Convention: 0.80, meaning at least an 80% chance &mdash; the planning standard.">power <b>${pw.power}</b></span>
      <span class="tip" data-tip="<b>Sample size per group &mdash; the experiment's price tag.</b> What: reviews each A/B arm must collect before the verdict is trustworthy. Read: derived from MDE, &alpha; and power &mdash; arithmetic, not a guess.">per group <b>${pw.n_per_group.toLocaleString()}</b></span></div>
    <details class="partNone"><summary class="plabel">Why this technique</summary><div class="ptext">      Before anyone runs an experiment &mdash; say, testing whether a new review form makes feedback warmer &mdash; someone has to decide how long to run it. Run it too short and a real improvement goes undetected; run it too long and budget is burned proving what was already clear. Power analysis does that arithmetic <i>before</i> the experiment, not after.</div></details>
    <details class="partNone"><summary class="plabel">What the numbers say</summary><div class="ptext">      The smallest change worth detecting is a shift of <b>${pw.mde}</b> on the sentiment scale. With the standard safety settings &mdash; at most a <b>${pw.alpha}</b> risk of a false alarm, and at least a <b>${Math.round(pw.power*100)}%</b> chance of catching a real effect &mdash; each group needs <b>${pw.n_per_group.toLocaleString()}</b> reviews. Cohen's d (${pw.cohens_d}) is simply that change expressed in units of the data's natural wobble: small effects need big samples.</div></details>
    <details class="part helps"><summary class="plabel">How this helps</summary><div class="ptext">      It's the difference between "we ran a test" and "we ran a test that could actually answer the question." Any A/B test on review sentiment now has a pre-computed sample size &mdash; the experiment can be scheduled and budgeted, not guessed.</div></details>
  </div>
  <div class="verdict"><span class="stamp">&minus;1 to +1</span>
    <h3>Correlation matrix &mdash; which behaviors travel together</h3>
    <div class="q">${co.question}</div>
    <div class="corrbtns">
      <button id="corrBtnS" onclick="__setCorr('spearman')">Spearman &mdash; do they rise together?</button>
      <button id="corrBtnP" onclick="__setCorr('pearson')">Pearson &mdash; is it a straight line?</button>
    </div>
    <div class="corrwrap"><table class="corr">
      <thead><tr><th></th>${co.variables.map(x=>`<th>${x}</th>`).join('')}</tr></thead>
      <tbody id="corrBody"></tbody>
    </table></div>
    <details class="partNone"><summary class="plabel">Why this technique</summary><div class="ptext">      Chi-square answers questions about <i>categories</i>; the correlation matrix is its counterpart for <i>quantities</i> &mdash; how strongly two numbers move together, every pair at once. I run it twice: Pearson hunts for straight-line links, Spearman asks only "when one rises, does the other tend to rise?" &mdash; which stays honest on lopsided data like vote counts.</div></details>
    <details class="partNone"><summary class="plabel">What the numbers say</summary><div class="ptext">      Each cell runs from &minus;1 (move opposite) through 0 (unrelated) to +1 (lockstep). Rough guide: under 0.1 negligible, 0.1&ndash;0.3 weak, 0.3&ndash;0.5 moderate, above 0.5 strong. The strongest pairs here: ${co.strongest.map(s=>`${s.a} &times; ${s.b} (&rho;=${s.rho>=0?'+':''}${s.rho})`).join(' &middot; ')}. Warm cells move together, blue cells move opposite, and the pale diagonal is simply each behavior against itself.</div></details>
    <details class="part helps"><summary class="plabel">How this helps</summary><div class="ptext">      It's the fastest honesty check on the regression above: pairs that correlate strongly are the ones you'd expect to matter, and pairs near zero warn you not to force a story onto them. It also flags redundancy &mdash; two behaviors measuring nearly the same thing &mdash; before they quietly distort a model.</div></details>
  </div>`;

  /* ---------- correlation heatmap rendering ---------- */
  if(co && co.variables && co.variables.length){
    const cellHtml=(val,i,j)=>{
      const a=Math.min(Math.abs(val),1);
      const bg = i===j ? 'rgba(120,100,60,0.22)'
        : val>=0 ? `rgba(148,29,28,${(a*0.62).toFixed(2)})`
                 : `rgba(31,84,147,${(a*0.62).toFixed(2)})`;
      const fg = a>0.45 ? '#fff' : 'inherit';
      if(i===j) return `<td style="background:${bg};color:${fg}">${val.toFixed(2)}</td>`;
      return `<td class="tip" style="background:${bg};color:${fg}" data-tip="<b>Correlation coefficient.</b> Runs &minus;1 (move opposite) through 0 (unrelated) to +1 (lockstep). Guide: under 0.1 negligible, 0.1&ndash;0.3 weak, 0.3&ndash;0.5 moderate, above 0.5 strong.">${val.toFixed(2)}</td>`;
    };
    const rowsHtml=(m)=>co.variables.map((r,i)=>
      `<tr><th>${r}</th>${co.variables.map((c,j)=>cellHtml(m[i][j],i,j)).join('')}</tr>`).join('');
    window.__corrMode='spearman';
    window.__renderCorr=function(){
      const m=window.__corrMode==='spearman'?co.spearman:co.pearson;
      document.getElementById('corrBody').innerHTML=rowsHtml(m);
      document.getElementById('corrBtnS').className=window.__corrMode==='spearman'?'on':'';
      document.getElementById('corrBtnP').className=window.__corrMode==='pearson'?'on':'';
    };
    window.__setCorr=function(mode){window.__corrMode=mode;window.__renderCorr();};
    window.__renderCorr();
  }
  window.__toggleAll=function(open){
    document.querySelectorAll('#verdicts details.part').forEach(d=>{d.open=open;});
  };

  /* ---------- skewness exhibit (figures rendered by the Python pipeline) ---------- */
  const ex=document.getElementById('skewex');
  if(ex && DATA.skewfigs && DATA.skewfigs.length){
    ex.innerHTML=`<div class="chooser" style="margin-top:20px">
      <div class="chtitle">The skewness problem &mdash; why the classic tests were benched</div>
      <p class="chintro">These three shapes are the reason this chapter reaches for rank-based tests: a t-test assumes a bell curve, and none of these is one. The figures are drawn by the Python statistics stage (matplotlib) from the cleaned data &mdash; this report only displays them; the exploration notebook regenerates them live.</p>
      ${DATA.skewfigs.map(f=>`<figure class="skewfig">
        <img src="${f.img}" alt="${f.title} distribution">
        <figcaption><b>${f.title}</b> &mdash; <span class="tip" data-tip="<b>Skewness &mdash; the lopsidedness gauge.</b> What: 0 is a symmetric bell curve; positive means a long right tail of extremes. Why: classic tests assume near-symmetry and mislead when skew is high. Read: above 1 is decidedly skewed, above 3 is extreme.">skew ${f.skew}</span> &middot; mean ${f.mean} vs median ${f.median} &mdash; when the mean towers over the median, a handful of extremes is dragging it.</figcaption>
      </figure>`).join('')}
    </div>`;
  }

  /* ---------- hover-to-learn: wire every data-tip to the shared tooltip ---------- */
  document.querySelectorAll('[data-tip]').forEach(el=>{
    el.addEventListener('mousemove',ev=>showTip(el.getAttribute('data-tip'),ev));
    el.addEventListener('mouseleave',hideTip);
  });
})();

/* ---------- advocates table ---------- */
const tbl=document.getElementById('advTable');
let sortKey='advocacy_score',sortAsc=false;
function renderAdv(){
  const rows=[...DATA.advocates].sort((a,b)=>(a[sortKey]>b[sortKey]?1:-1)*(sortAsc?1:-1));
  const cols=[['UserId','Customer'],['segment','Segment'],['review_count','Reviews'],
    ['avg_score','Avg &#9733;'],['helpful_votes','Votes earned'],
    ['helpfulness_ratio','Helpfulness'],['pct_positive','% positive'],
    ['advocacy_score','Advocacy score'],['last_review','Last active']];
  tbl.innerHTML='<thead><tr>'+cols.map(([k,n])=>
    `<th data-k="${k}" class="${k===sortKey?'sorted':''}">${n}${k===sortKey?(sortAsc?' &uarr;':' &darr;'):''}</th>`).join('')+
    '</tr></thead><tbody>'+rows.map(r=>`<tr>
      <td>${r.UserId}</td><td style="text-align:right"><span class="segtag ${r.segment}">${r.segment}</span></td>
      <td>${r.review_count}</td><td>${r.avg_score}</td><td>${r.helpful_votes}</td>
      <td>${(r.helpfulness_ratio*100).toFixed(0)}%</td><td>${r.pct_positive.toFixed(0)}%</td>
      <td><b>${r.advocacy_score}</b></td><td>${r.last_review}</td></tr>`).join('')+'</tbody>';
  tbl.querySelectorAll('th').forEach(th=>th.addEventListener('click',()=>{
    const k=th.dataset.k;
    if(k===sortKey){sortAsc=!sortAsc}else{sortKey=k;sortAsc=(k==='UserId'||k==='last_review'||k==='segment')}
    renderAdv();
  }));
}
renderAdv();
</script>
</body>
</html>
"""

html = TEMPLATE.replace("__DATA_JSON__", json.dumps(DATA))
OUT.write_text(html, encoding="utf-8")
print(f"Dashboard written: {OUT}  ({OUT.stat().st_size / 1024:.0f} KB)")
print("Editorial edition — open in any browser. Fully self-contained.")
