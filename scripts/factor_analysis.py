# -*- coding: utf-8 -*-
"""Week 6: how does each weather factor relate to observed clear evenings, and monthly probabilities.

Factor relationships are measured ONLY at stations with human cloud observations (20/21 LST). Hehuan has no
cloud observation and its labels are computed from dew-point depression, so correlating Hehuan's factors with
its own labels would be circular; Hehuan appears only in the climatology and the probability table.

AUC = probability that a randomly chosen clear hour has a higher factor value than a randomly chosen
not-clear hour. 0.5 = no information; further from 0.5 (either way) = more informative.
"within_month" averages the AUC computed inside each calendar month, removing the shared seasonal cycle.

Outputs: results/tables/week06_*.csv, results/figures/fig_week06_*.png
"""
import sys
import json
import pathlib

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams["font.family"] = ["Microsoft JhengHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hehuan import config as C, climatology as K, validate as V   # noqa: E402

T, F = C.RESULTS / "tables", C.RESULTS / "figures"
STATIONS = {"466920": "臺北 6 m", "466910": "鞍部 838 m", "467530": "阿里山 2413 m", "467550": "玉山 3845 m"}
FACTORS = {"dpd": "露點差", "rh": "相對濕度", "rain_3h": "近3時雨量", "wind": "風速", "t_air": "氣溫",
           "e_lcc": "ERA5低雲", "e_mcc": "ERA5中雲", "e_hcc": "ERA5高雲", "e_tcc": "ERA5總雲量"}
MONTHS = [f"{m}月" for m in range(1, 13)]


def load_nh(stn):
    nh = pd.read_csv(C.PROCESSED / "night_hours" / f"{stn}_night_hours.csv.gz", index_col="time",
                     parse_dates=["time"], low_memory=False)
    return nh[nh.index < "2026-01-01"]


def truth_sample(stn, clear_max=2):
    d = load_nh(stn)
    d = d[d.index.hour.isin([20, 21])].dropna(subset=["cloud_manual_eff"]).copy()
    d["y"] = d.cloud_manual_eff <= clear_max
    d["month"] = d.index.month
    return d


def auc(y, x):
    m = x.notna()
    if m.sum() < 50 or y[m].nunique() < 2:
        return np.nan
    return roc_auc_score(y[m], x[m])


def factor_table(samples):
    rows = []
    for stn, d in samples.items():
        for f, name in FACTORS.items():
            within = [auc(g.y, g[f]) for _, g in d.groupby("month")]
            rows.append(dict(stn_id=stn, station=STATIONS[stn], factor=f, name=name, n=int(d[f].notna().sum()),
                             auc=auc(d.y, d[f]), auc_within_month=np.nanmean(within),
                             clear_mean=d.loc[d.y, f].mean(), notclear_mean=d.loc[~d.y, f].mean()))
    return pd.DataFrame(rows).round(3)


def dpd_curve(samples):
    bins = [-0.01, 0.5, 1, 2, 3, 5, 8, 12, 20, 60]
    labels = ["0-0.5", "0.5-1", "1-2", "2-3", "3-5", "5-8", "8-12", "12-20", ">20"]
    rows = []
    for stn, d in samples.items():
        b = pd.cut(d.dpd, bins, labels=labels)
        g = d.groupby(b, observed=False).y.agg(["mean", "count"])
        for k, r in g.iterrows():
            rows.append(dict(stn_id=stn, station=STATIONS[stn], dpd_bin=k, p_clear=r["mean"], n=int(r["count"])))
    return pd.DataFrame(rows).round(3), labels


def monthly_table():
    tp = pd.read_csv(C.PROCESSED / "labels" / "466920_night_labels.csv", index_col="night", parse_dates=["night"])
    tp["evening_clear"] = tp.evening_clear.map({True: 1.0, False: 0.0, "True": 1.0, "False": 0.0}).astype(float)
    hh = pd.read_csv(C.PROCESSED / "labels" / "C0H9C0_night_labels.csv", index_col="night", parse_dates=["night"])
    hh["evening_clear"] = hh.evening_clear.map({True: 1.0, False: 0.0, "True": 1.0, "False": 0.0}).astype(float)
    out = []
    for name, lab, col, y0, y1 in [("臺北（人工雲量 2008–2017）", tp, "evening_clear", 2008, 2017),
                                   ("合歡山（代理 2011–2025）", hh, "evening_clear", 2011, 2025),
                                   ("臺北（共同期 2012–2017）", tp, "evening_clear", 2012, 2017),
                                   ("合歡山（共同期 2012–2017）", hh, "evening_clear", 2012, 2017)]:
        d = lab[(lab.index.year >= y0) & (lab.index.year <= y1)]
        m = K.year_block_bootstrap(d, col, "month").reset_index().rename(columns={"index": "month"})
        m.insert(0, "group", name)
        out.append(m)
    return pd.concat(out, ignore_index=True), tp, hh


def threshold_sensitivity():
    """Re-fit the dew-point threshold for cloud <= 1, 2, 3 at Yushan, apply each to Hehuan and compare months."""
    hh = load_nh("C0H9C0")
    rows, base = [], None
    for k in (2, 1, 3):
        d = truth_sample("467550", k)
        d["no_rain3"] = d.rain_3h_known.astype(bool) & (d.rain_3h == 0)
        t, j = V.youden_threshold(d.dpd, d.y, "ge")
        p = (d.dpd >= t) & d.no_rain3 & d.dpd.notna()
        pn = K.proxy_nights(hh, {"kind": "R_dpd", "threshold": t})
        s = pd.to_numeric(pn.evening_clear.map({True: 1.0, False: 0.0}), errors="coerce").dropna()
        mo = s.groupby(s.index.month).mean()
        base = mo if k == 2 else base
        rows.append(dict(clear_max=k, dpd_threshold=round(t, 2), yushan_kappa=round(V.kappa(d.y, p), 3),
                         yushan_clear_share=round(d.y.mean(), 3), hehuan_annual=round(s.mean(), 3),
                         spearman_vs_cloud2=round(spearmanr(base.reindex(mo.index), mo).correlation, 3),
                         **{f"m{m:02d}": round(mo[m], 3) for m in mo.index}))
    return pd.DataFrame(rows)


def main():
    samples = {s: truth_sample(s) for s in STATIONS}
    ft = factor_table(samples)
    ft.to_csv(T / "week06_factor_auc.csv", index=False, encoding="utf-8-sig")
    print(ft.pivot(index="name", columns="station", values="auc_within_month")[list(STATIONS.values())].reindex(FACTORS.values()).to_string())
    print(ft.pivot(index="name", columns="station", values="auc")[list(STATIONS.values())].reindex(FACTORS.values()).to_string())

    curve, labels = dpd_curve(samples)
    curve.to_csv(T / "week06_pclear_by_dpd.csv", index=False, encoding="utf-8-sig")
    print(curve.pivot(index="dpd_bin", columns="station", values="p_clear").reindex(labels)[list(STATIONS.values())].to_string())

    mt, tp, hh = monthly_table()
    mt.to_csv(T / "week06_monthly_prob.csv", index=False, encoding="utf-8-sig")
    print(mt.pivot(index="group", columns="month", values="p").round(2).to_string())
    print("annual, common period 2012-2017:", {n: round(l[(l.index.year >= 2012) & (l.index.year <= 2017)].evening_clear.mean(), 3) for n, l in [("taipei", tp), ("hehuan", hh)]})

    sens = threshold_sensitivity()
    sens.to_csv(T / "week06_cloud_threshold_sensitivity.csv", index=False, encoding="utf-8-sig")
    print(sens.to_string(index=False))

    # fig 1: distributions at Yushan and Taipei
    fig, ax = plt.subplots(2, 2, figsize=(11, 6))
    for i, stn in enumerate(("467550", "466920")):
        d = samples[stn]
        for j, (col, lab, rng) in enumerate((("rh", "相對濕度 (%)", (0, 100)), ("dpd", "露點差 (°C)", (0, 40)))):
            a = ax[i, j]
            a.hist(d.loc[d.y, col].dropna(), bins=40, range=rng, density=True, alpha=.6, color="tab:blue", label="晴（雲量≤2）")
            a.hist(d.loc[~d.y, col].dropna(), bins=40, range=rng, density=True, alpha=.5, color="tab:gray", label="不晴")
            a.set_title(f"{STATIONS[stn]}：{lab}", fontsize=10); a.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(F / "fig_week06_distributions.png", dpi=130); plt.close(fig)

    # fig 2: within-month AUC heatmap
    h = ft.pivot(index="name", columns="station", values="auc_within_month")[list(STATIONS.values())].reindex(FACTORS.values())
    fig, a = plt.subplots(figsize=(7.5, 4.6))
    im = a.imshow(h.values, cmap="RdBu", vmin=0.2, vmax=0.8, aspect="auto")
    a.set_xticks(range(4)); a.set_xticklabels(h.columns); a.set_yticks(range(len(h))); a.set_yticklabels(h.index)
    for i in range(h.shape[0]):
        for j in range(h.shape[1]):
            a.text(j, i, f"{h.values[i, j]:.2f}", ha="center", va="center", fontsize=9)
    a.set_title("各因子分辨晴與不晴的能力（同月內 AUC，0.5 = 沒有資訊）", fontsize=10)
    plt.colorbar(im, ax=a); fig.tight_layout(); fig.savefig(F / "fig_week06_factor_auc.png", dpi=130); plt.close(fig)

    # fig 3: P(clear) by dew-point depression
    fig, a = plt.subplots(figsize=(8, 4))
    for stn, name in STATIONS.items():
        d = curve[curve.stn_id == stn]
        a.plot(range(len(labels)), d.p_clear, marker="o", label=name)
    a.set_xticks(range(len(labels))); a.set_xticklabels(labels); a.set_xlabel("露點差 (°C)"); a.set_ylabel("實際晴的比例")
    a.set_ylim(0, 1); a.grid(alpha=.3); a.legend(fontsize=8); a.set_title("露點差越大越容易晴嗎？海拔越高關係越強", fontsize=10)
    fig.tight_layout(); fig.savefig(F / "fig_week06_pclear_by_dpd.png", dpi=130); plt.close(fig)

    # fig 4: monthly probabilities with CI on the common period and full period
    fig, a = plt.subplots(figsize=(9, 4))
    for name, c, off in (("臺北（人工雲量 2008–2017）", "tab:gray", -.15), ("合歡山（代理 2011–2025）", "tab:blue", .15)):
        d = mt[mt.group == name].sort_values("month")
        a.errorbar(d.month + off, d.p, yerr=[d.p - d.ci_lo, d.ci_hi - d.p], fmt="o-", capsize=3, color=c, label=name)
    a.set_xticks(range(1, 13)); a.set_xticklabels(MONTHS); a.set_ylim(0, .6); a.set_ylabel("傍晚 20、21 時皆晴的機率")
    a.grid(alpha=.3); a.legend(fontsize=8); a.set_title("各月可觀星機率與 95% 信賴區間", fontsize=10)
    fig.tight_layout(); fig.savefig(F / "fig_week06_monthly_prob.png", dpi=130); plt.close(fig)


if __name__ == "__main__":
    main()
