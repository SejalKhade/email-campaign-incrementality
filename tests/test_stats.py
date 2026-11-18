import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy import stats as sps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from stats import (cuped_adjust, qini_curve, srm_test, standardized_mean_diff,  # noqa: E402
                   two_proportion_test, welch_mean_diff)


def test_two_proportion_matches_scipy_chi2():
    r = two_proportion_test(180, 1000, 100, 1000)
    table = np.array([[180, 820], [100, 900]])
    chi2_p = sps.chi2_contingency(table, correction=False)[1]
    assert r["diff"] == pytest.approx(0.08)
    assert r["p_value"] == pytest.approx(chi2_p, rel=1e-9)
    assert r["ci_low"] < 0.08 < r["ci_high"]


def test_welch_matches_scipy():
    rng = np.random.default_rng(0)
    a, b = rng.normal(1.0, 2.0, 500), rng.normal(0.5, 1.0, 700)
    r = welch_mean_diff(a, b)
    assert r["p_value"] == pytest.approx(sps.ttest_ind(a, b, equal_var=False).pvalue, rel=1e-9)


def test_cuped_reduces_variance_when_covariate_is_predictive():
    rng = np.random.default_rng(1)
    x = rng.normal(size=5000)
    y = 3 * x + rng.normal(size=5000)
    adj, theta = cuped_adjust(y, x)
    assert theta == pytest.approx(3, abs=0.1)
    assert adj.var() < 0.2 * y.var()
    assert adj.mean() == pytest.approx(y.mean())


def test_srm_flags_bad_split_only():
    assert srm_test([1000, 1000, 1000]) > 0.9
    assert srm_test([1000, 1000, 1300]) < 0.001


def test_smd_zero_for_identical_groups():
    assert standardized_mean_diff([1, 2, 3], [1, 2, 3]) == 0


def test_qini_perfect_score_front_loads_gain():
    treated = np.array([1, 1, 0, 0])
    outcome = np.array([1, 0, 0, 1])
    frac, inc = qini_curve(np.array([4, 1, 3, 2]), treated, outcome)
    assert frac[0] == 0 and inc[0] == 0 and frac[-1] == 1
    assert inc[-1] == pytest.approx(0.0)  # 1 treated success - 1 control success, scaled 2/2


@pytest.mark.skipif(not (ROOT / "output" / "r_ate.csv").exists(), reason="run R/incrementality.R first")
def test_python_and_r_agree():
    py = pd.read_csv(ROOT / "output" / "ate.csv").set_index(["campaign", "metric"])
    r = pd.read_csv(ROOT / "output" / "r_ate.csv").set_index(["campaign", "metric"])
    for idx in py.index:
        assert py.loc[idx, "diff"] == pytest.approx(r.loc[idx, "diff"], rel=1e-9)
        assert py.loc[idx, "p_holm"] == pytest.approx(r.loc[idx, "p_holm"], rel=1e-3)


@pytest.mark.skipif(not (ROOT / "output" / "results.json").exists(), reason="run src/analysis.py first")
def test_randomization_is_clean():
    res = json.loads((ROOT / "output" / "results.json").read_text())
    assert res["srm_p_value"] > 0.05
    assert res["max_abs_smd"] < 0.1
