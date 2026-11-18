"""Two README charts built from output/ (run src/analysis.py first)."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ate = pd.read_csv(ROOT / "output" / "ate.csv")
res = json.loads((ROOT / "output" / "results.json").read_text())
INK, MUTED, A, B = "#1f2328", "#6e7781", "#2f6fdb", "#c2571a"
plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK})

# 1. Visit lift with 95% CI
v = ate[ate.metric == "visit"].reset_index(drop=True)
fig, ax = plt.subplots(figsize=(7, 3.2))
y = [1, 0]
ax.errorbar(v["diff"] * 100, y, xerr=[(v["diff"] - v.ci_low) * 100, (v.ci_high - v["diff"]) * 100],
            fmt="o", color=INK, ecolor=MUTED, capsize=5, ms=8)
for yi, (_, r) in zip(y, v.iterrows()):
    ax.annotate(f"+{r['diff']*100:.1f} pts  (+{r.rel_lift*100:.0f}%)", (r["diff"] * 100, yi),
                xytext=(0, 12), textcoords="offset points", ha="center", color=INK)
ax.set_yticks(y, ["Men's email", "Women's email"]); ax.set_ylim(-0.6, 1.6)
ax.axvline(0, color=MUTED, lw=0.8); ax.set_xlim(0, 10)
ax.set_xlabel("Incremental visit rate vs. no-email control (percentage points, 95% CI)")
ax.set_title("Both emails lift site visits; men's email lifts more", loc="left", color=INK)
fig.tight_layout(); fig.savefig(ROOT / "docs" / "visit_lift.png", dpi=150)

# 2. Women's email lift by past purchase category
t = res["targeting_rule"]
fig, ax = plt.subplots(figsize=(7, 3.2))
vals = [t["lift_pp_womens_buyers"], t["lift_pp_non_buyers"]]
bars = ax.barh([1, 0], vals, color=[A, MUTED], height=0.55)
for b_, val in zip(bars, vals):
    ax.text(val + 0.15, b_.get_y() + b_.get_height() / 2, f"+{val:.1f} pts", va="center", color=INK)
ax.set_yticks([1, 0], ["Past women's buyers", "Everyone else"]); ax.set_xlim(0, 9)
ax.set_xlabel("Incremental visit rate from the women's email (percentage points)")
ax.set_title("The women's email only works on past women's buyers", loc="left", color=INK)
fig.tight_layout(); fig.savefig(ROOT / "docs" / "womens_targeting.png", dpi=150)
print("charts ok")
