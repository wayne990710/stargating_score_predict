# -*- coding: utf-8 -*-
"""Apply the validated proxy rule (from results/tables/validation_<truth_stn>_thresholds.json) to a target station
(default C0H9C0 Hehuanshan) and produce the stargazing climatology tables + figures.

    python scripts/apply_hehuan.py            # C0H9C0 with rule validated at 467550
    python scripts/apply_hehuan.py C0H990     # Kunyang (neighbour) for consistency check
"""
import sys
import json
import pathlib

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hehuan import config as C, climatology as K   # noqa: E402

MONTH_LABELS = ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"]


def main(stn_id="C0H9C0", truth_stn="467550", rule_kind="R_dpd", status="tentative"):
    th = json.load(open(C.RESULTS / "tables" / f"validation_{truth_stn}_thresholds.json", encoding="utf-8"))
    rule = {"kind": rule_kind, "threshold": th["all_years"][rule_kind]["threshold"], "source": truth_stn, "status": status}
    nh = pd.read_csv(C.PROCESSED / "night_hours" / f"{stn_id}_night_hours.csv.gz", index_col="time", parse_dates=["time"])
    nh = nh[nh.index < "2026-01-01"]                    # 2026 kept out (held-out / activity comparison)
    pn = K.proxy_nights(nh, rule)
    pn.to_csv(C.PROCESSED / "nights" / f"{stn_id}_nights_proxy.csv", float_format="%.3f")
    T, F = C.RESULTS / "tables", C.RESULTS / "figures"
    tag = stn_id.lower()
    tabs = {}
    for col in ("def_A", "def_B", "evening_clear"):
        m = K.year_block_bootstrap(pn, col, "month")
        m.index = [MONTH_LABELS[i - 1] for i in m.index]
        tabs[col] = m
        m.to_csv(T / f"{tag}_monthly_prob_{col}.csv")
        K.year_block_bootstrap(pn, col, "halfmonth").to_csv(T / f"{tag}_halfmonth_prob_{col}.csv")
    heat = K.month_hour_heatmap(nh, rule); heat.to_csv(T / f"{tag}_month_hour_clear.csv")
    pers = K.persistence(pn, "def_A"); pers.to_csv(T / f"{tag}_persistence_def_A.csv")
    yearly = pn.groupby(pn.index.year)[["def_A", "def_B", "evening_clear"]].agg(["mean", "count"]).round(3)
    yearly.to_csv(T / f"{tag}_yearly_prob.csv")
    json.dump(rule, open(T / f"{tag}_rule_used.json", "w", encoding="utf-8"), indent=1)

    # ---- figures ------------------------------------------------------------------------------
    fig, ax = plt.subplots(1, 2, figsize=(12, 4))
    for a, col, title in zip(ax, ("def_A", "evening_clear"), ("可觀星夜（連續≥3小時晴）", "傍晚 20–21 時皆晴")):
        m = tabs[col]
        a.bar(range(12), m["p"], color="tab:blue", alpha=0.8)
        a.errorbar(range(12), m["p"], yerr=[m["p"] - m["ci_lo"], m["ci_hi"] - m["p"]], fmt="none", ecolor="k", capsize=3)
        a.set_xticks(range(12)); a.set_xticklabels(m.index, fontsize=8); a.set_ylim(0, 1)
        a.set_ylabel("機率"); a.set_title(f"{stn_id} {title}  [{status}]")
        for i, (p, n) in enumerate(zip(m["p"], m["n"])):
            a.text(i, p + 0.02, f"{p:.2f}", ha="center", fontsize=7)
    fig.tight_layout(); fig.savefig(F / f"fig_{tag}_monthly_prob.png", dpi=130); plt.close(fig)

    fig, a = plt.subplots(figsize=(8, 4.5))
    im = a.imshow(heat.to_numpy(), aspect="auto", cmap="Blues", vmin=0, vmax=1)
    a.set_yticks(range(12)); a.set_yticklabels(MONTH_LABELS); a.set_xticks(range(heat.shape[1])); a.set_xticklabels([f"{h:02d}" for h in heat.columns])
    a.set_xlabel("時（小時終）"); a.set_title(f"{stn_id} 各月各時段「代理指標判定為晴」的比例  [{status}]")
    plt.colorbar(im, ax=a); fig.tight_layout(); fig.savefig(F / f"fig_{tag}_month_hour_heatmap.png", dpi=130); plt.close(fig)

    fig, a = plt.subplots(figsize=(8, 3.5))
    y = yearly[("def_A", "mean")]
    a.plot(y.index, y.values, marker="o"); a.set_ylim(0, 1); a.set_ylabel("年可觀星夜比例"); a.set_title(f"{stn_id} 逐年  [{status}]")
    fig.tight_layout(); fig.savefig(F / f"fig_{tag}_yearly.png", dpi=130); plt.close(fig)
    print(stn_id, "rule", rule)
    print(tabs["def_A"].to_string())
    print(yearly[("def_A", "mean")].to_string())


if __name__ == "__main__":
    a = sys.argv[1:]
    main(*(a if a else []))
