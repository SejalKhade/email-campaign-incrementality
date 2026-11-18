"""Small, tested statistical helpers for a randomized marketing test."""
from __future__ import annotations

import numpy as np
from scipy import stats


def two_proportion_test(x_t: int, n_t: int, x_c: int, n_c: int, alpha: float = 0.05) -> dict:
    """Difference in proportions (treated minus control) with a pooled z-test
    and an unpooled Wald confidence interval."""
    p_t, p_c = x_t / n_t, x_c / n_c
    diff = p_t - p_c
    p_pool = (x_t + x_c) / (n_t + n_c)
    se_pool = np.sqrt(p_pool * (1 - p_pool) * (1 / n_t + 1 / n_c))
    z = diff / se_pool
    p_value = 2 * stats.norm.sf(abs(z))
    se = np.sqrt(p_t * (1 - p_t) / n_t + p_c * (1 - p_c) / n_c)
    zc = stats.norm.ppf(1 - alpha / 2)
    return {"treated": p_t, "control": p_c, "diff": diff, "rel_lift": diff / p_c,
            "ci_low": diff - zc * se, "ci_high": diff + zc * se, "z": z, "p_value": p_value}


def welch_mean_diff(y_t: np.ndarray, y_c: np.ndarray, alpha: float = 0.05) -> dict:
    """Difference in means with Welch's t-test and CI."""
    y_t, y_c = np.asarray(y_t, float), np.asarray(y_c, float)
    diff = y_t.mean() - y_c.mean()
    v_t, v_c = y_t.var(ddof=1) / len(y_t), y_c.var(ddof=1) / len(y_c)
    se = np.sqrt(v_t + v_c)
    dof = (v_t + v_c) ** 2 / (v_t ** 2 / (len(y_t) - 1) + v_c ** 2 / (len(y_c) - 1))
    t = diff / se
    p_value = 2 * stats.t.sf(abs(t), dof)
    tc = stats.t.ppf(1 - alpha / 2, dof)
    return {"treated": y_t.mean(), "control": y_c.mean(), "diff": diff, "se": se,
            "ci_low": diff - tc * se, "ci_high": diff + tc * se, "t": t, "p_value": p_value}


def cuped_adjust(y: np.ndarray, x: np.ndarray) -> tuple[np.ndarray, float]:
    """CUPED: remove the part of the outcome explained by a pre-period covariate.
    theta is estimated on the pooled sample, so it is the same for both arms."""
    y, x = np.asarray(y, float), np.asarray(x, float)
    theta = np.cov(y, x, ddof=1)[0, 1] / np.var(x, ddof=1)
    return y - theta * (x - x.mean()), theta


def srm_test(counts: list[int]) -> float:
    """Sample ratio mismatch: chi-square p-value against an equal split."""
    counts = np.asarray(counts, float)
    expected = np.full_like(counts, counts.sum() / len(counts))
    return float(stats.chisquare(counts, expected).pvalue)


def standardized_mean_diff(a: np.ndarray, b: np.ndarray) -> float:
    """Covariate balance check. |SMD| < 0.1 is the usual 'balanced' threshold."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    pooled = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)
    return 0.0 if pooled == 0 else float((a.mean() - b.mean()) / pooled)


def qini_curve(uplift_score: np.ndarray, treated: np.ndarray, outcome: np.ndarray):
    """Cumulative incremental outcomes when targeting customers in score order.
    Returns (fraction targeted, incremental outcomes) arrays, starting at (0, 0)."""
    order = np.argsort(-np.asarray(uplift_score))
    t = np.asarray(treated)[order].astype(float)
    y = np.asarray(outcome)[order].astype(float)
    n_t, n_c = np.cumsum(t), np.cumsum(1 - t)
    y_t, y_c = np.cumsum(y * t), np.cumsum(y * (1 - t))
    with np.errstate(divide="ignore", invalid="ignore"):
        inc = y_t - np.where(n_c > 0, y_c * n_t / n_c, 0.0)
    frac = np.arange(1, len(t) + 1) / len(t)
    return np.r_[0.0, frac], np.r_[0.0, inc]
