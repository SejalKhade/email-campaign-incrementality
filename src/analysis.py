"""Email campaign incrementality analysis on the Hillstrom randomized test.

Run from the repo root:  python src/analysis.py
Writes every number it reports to output/ (results.json plus CSVs).
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from statsmodels.stats.multitest import multipletests

from stats import (cuped_adjust, qini_curve, srm_test, standardized_mean_diff,
                   two_proportion_test, welch_mean_diff)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
CONTROL = "No E-Mail"
CAMPAIGNS = ["Mens E-Mail", "Womens E-Mail"]
SEED = 42


def load() -> pd.DataFrame:
    df = pd.read_csv(ROOT / "data" / "hillstrom.csv")
    assert len(df) == 64_000, "unexpected row count"
    return df


def run_sql(con, name: str, **params) -> pd.DataFrame:
    sql = (ROOT / "sql" / name).read_text()
    for k, v in params.items():
        sql = sql.replace("{" + k + "}", v)
    return con.execute(sql).df()


def main() -> dict:
    OUT.mkdir(exist_ok=True)
    df = load()
    con = duckdb.connect()
    con.register("hillstrom", df)
    res: dict = {"rows": len(df)}

    # 1. Funnel by arm (SQL)
    funnel = run_sql(con, "01_campaign_funnel.sql")
    funnel.to_csv(OUT / "funnel_by_arm.csv", index=False)

    # 2. Randomization checks
    counts = df.segment.value_counts()
    res["arm_sizes"] = counts.to_dict()
    res["srm_p_value"] = srm_test(counts.values.tolist())
    covs = ["recency", "history", "mens", "womens", "newbie"]
    ctrl = df[df.segment == CONTROL]
    res["max_abs_smd"] = max(
        abs(standardized_mean_diff(df.loc[df.segment == c, v], ctrl[v]))
        for c in CAMPAIGNS for v in covs)

    # 3. Average treatment effects, Holm-corrected across 6 tests
    rows = []
    for camp in CAMPAIGNS:
        t = df[df.segment == camp]
        for m in ["visit", "conversion"]:
            r = two_proportion_test(t[m].sum(), len(t), ctrl[m].sum(), len(ctrl))
            rows.append({"campaign": camp, "metric": m, **r})
        r = welch_mean_diff(t.spend, ctrl.spend)
        r["rel_lift"] = r["diff"] / r["control"]
        rows.append({"campaign": camp, "metric": "spend", **r})
    ate = pd.DataFrame(rows)
    ate["p_holm"] = multipletests(ate.p_value, method="holm")[1]
    ate.to_csv(OUT / "ate.csv", index=False)
    res["ate"] = ate.drop(columns=[c for c in ("z", "t", "se") if c in ate]).to_dict("records")

    # 4. CUPED on spend using pre-period history (dollars spent last year)
    cuped = {}
    for camp in CAMPAIGNS:
        sub = df[df.segment.isin([camp, CONTROL])]
        adj, theta = cuped_adjust(sub.spend, sub.history)
        is_t = (sub.segment == camp).values
        raw = welch_mean_diff(sub.spend[is_t], sub.spend[~is_t])
        cup = welch_mean_diff(adj[is_t], adj[~is_t])
        cuped[camp] = {"theta": theta, "raw_se": raw["se"], "cuped_se": cup["se"],
                       "variance_reduction": 1 - (cup["se"] / raw["se"]) ** 2,
                       "raw_p": raw["p_value"], "cuped_p": cup["p_value"],
                       "cuped_diff": cup["diff"]}
    res["cuped"] = cuped

    # 5. Lift by customer attribute (SQL)
    seg_frames = []
    for dim in ["channel", "zip_code", "newbie", "history_segment"]:
        s = run_sql(con, "02_lift_by_segment.sql", dim=dim)
        s.insert(0, "dimension", dim)
        seg_frames.append(s)
    seg = pd.concat(seg_frames, ignore_index=True)
    seg.to_csv(OUT / "lift_by_segment.csv", index=False)

    # 6. Economics: incremental outcomes per 1,000 emails sent
    econ = {}
    for camp in CAMPAIGNS:
        a = ate[ate.campaign == camp].set_index("metric")
        econ[camp] = {"incremental_visits_per_1000": a.loc["visit", "diff"] * 1000,
                      "incremental_orders_per_1000": a.loc["conversion", "diff"] * 1000,
                      "incremental_revenue_per_1000": a.loc["spend", "diff"] * 1000,
                      "break_even_cost_per_email": a.loc["spend", "diff"]}
    res["economics"] = econ

    # 6b. Targeting rule: does campaign/category match drive the lift?
    #     Interaction test (logistic regression) + simulation of sending the
    #     Womens email only to past womens-category buyers.
    import statsmodels.formula.api as smf
    w = df[df.segment.isin(["Womens E-Mail", CONTROL])].copy()
    w["treated"] = (w.segment == "Womens E-Mail").astype(int)
    fit = smf.logit("visit ~ treated * womens", data=w).fit(disp=0)
    lift = {}
    for v in (0, 1):
        g = w[w.womens == v]
        lift[v] = g[g.treated == 1].visit.mean() - g[g.treated == 0].visit.mean()
    treated_w = w[w.treated == 1]
    share_buyers = (treated_w.womens == 1).mean()
    inc_all = lift[1] * share_buyers + lift[0] * (1 - share_buyers)   # per email sent to everyone
    inc_targeted = lift[1] * share_buyers                              # per customer, only buyers emailed
    res["targeting_rule"] = {
        "lift_pp_womens_buyers": lift[1] * 100, "lift_pp_non_buyers": lift[0] * 100,
        "interaction_p_value": float(fit.pvalues["treated:womens"]),
        "share_of_list_womens_buyers": float(share_buyers),
        "emails_saved_share": float(1 - share_buyers),
        "incremental_visits_retained_share": float(inc_targeted / inc_all),
    }

    # 7. Uplift model (T-learner) for the Mens campaign on visits, scored on a holdout
    camp = "Mens E-Mail"
    sub = df[df.segment.isin([camp, CONTROL])].copy()
    sub["treated"] = (sub.segment == camp).astype(int)
    X = pd.get_dummies(sub[["recency", "history", "mens", "womens", "newbie",
                            "zip_code", "channel"]], drop_first=True).astype(float)
    strat = sub.treated.astype(str) + sub.visit.astype(str)
    Xtr, Xte, str_, ste = train_test_split(X, sub, test_size=0.3, random_state=SEED, stratify=strat)
    gb = dict(n_estimators=200, max_depth=3, learning_rate=0.05, random_state=SEED)
    m_t = GradientBoostingClassifier(**gb).fit(Xtr[str_.treated == 1], str_.visit[str_.treated == 1])
    m_c = GradientBoostingClassifier(**gb).fit(Xtr[str_.treated == 0], str_.visit[str_.treated == 0])
    score = m_t.predict_proba(Xte)[:, 1] - m_c.predict_proba(Xte)[:, 1]
    frac, inc = qini_curve(score, ste.treated.values, ste.visit.values)
    total = inc[-1]
    def at(p):  # incremental visits captured when targeting the top p of customers
        return float(np.interp(p, frac, inc))
    qini_area = float(np.trapezoid(inc - frac * total, frac))
    res["uplift_model"] = {
        "campaign": camp, "holdout_customers": int(len(ste)),
        "holdout_total_incremental_visits": float(total),
        "share_captured_top_30pct": at(0.3) / total,
        "share_captured_top_50pct": at(0.5) / total,
        "random_targeting_top_30pct": 0.30,
        "qini_area": qini_area,
    }
    pd.DataFrame({"fraction_targeted": frac, "incremental_visits": inc}).iloc[::50].to_csv(
        OUT / "qini_curve.csv", index=False)

    # 8. Dashboard extract (Looker Studio / Tableau ready): one tidy row per arm x attribute value
    extract = (df.melt(id_vars=["segment", "visit", "conversion", "spend"],
                       value_vars=["channel", "zip_code", "history_segment"],
                       var_name="dimension", value_name="dimension_value")
                 .groupby(["segment", "dimension", "dimension_value"])
                 .agg(customers=("visit", "size"), visits=("visit", "sum"),
                      conversions=("conversion", "sum"), revenue=("spend", "sum"))
                 .reset_index())
    extract.to_csv(OUT / "dashboard_extract.csv", index=False)

    (OUT / "results.json").write_text(json.dumps(res, indent=2, default=float))
    return res


if __name__ == "__main__":
    r = main()
    print(json.dumps(r, indent=2, default=float))
