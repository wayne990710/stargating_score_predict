# -*- coding: utf-8 -*-
"""Week 7: stargazing index = estimated probability (0-100) that an hour is clear (cloud <= 2/10).

Weights come from a logistic regression fitted on Yushan (467550) manual cloud observations at 20/21 LST,
2008-2021. Candidate factor sets are compared by leave-one-year-out (LOYO): every year is predicted by a
model that never saw that year (scaler and monthly-climatology reference are also fitted on training years).

  AUC   : ability to rank clear above not-clear hours (0.5 = none)
  Brier : mean squared error of the probability (lower is better)
  BSS   : Brier skill score vs. the monthly climatology of the training years (0 = no better than climatology)

Transfer test: the Yushan-fitted index is applied unchanged to the other manned stations to see how well
weights carry to another site. Hehuanshan has no cloud observation, so the index there cannot be validated.

Outputs: results/tables/week07_*.csv, results/tables/index_formula.json, results/figures/fig_week07_*.png
"""
import sys
import json
import pathlib

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams["font.family"] = ["Microsoft JhengHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hehuan import config as C   # noqa: E402

T, F = C.RESULTS / "tables", C.RESULTS / "figures"
NAMES = {"ldpd": "露點差（取對數）", "rain": "近3小時有雨", "e_lcc": "ERA5 低雲", "e_mcc": "ERA5 中雲", "e_hcc": "ERA5 高雲"}
MODELS = {
    "M1 露點差": ["ldpd"],
    "M2 露點差+雨": ["ldpd", "rain"],
    "M3 露點差+雨+ERA5中高雲": ["ldpd", "rain", "e_mcc", "e_hcc"],
    "M4 露點差+雨+ERA5低中高雲": ["ldpd", "rain", "e_lcc", "e_mcc", "e_hcc"],
    "M5 只用ERA5低中高雲": ["e_lcc", "e_mcc", "e_hcc"],
}
CHOSEN_STATION_ONLY, CHOSEN_FULL = "M2 露點差+雨", "M3 露點差+雨+ERA5中高雲"
STATIONS = {"466920": "臺北 6 m", "466910": "鞍部 838 m", "467530": "阿里山 2413 m", "467550": "玉山 3845 m"}


def load_hours(stn, truth=True):
    nh = pd.read_csv(C.PROCESSED / "night_hours" / f"{stn}_night_hours.csv.gz", index_col="time",
                     parse_dates=["time"], low_memory=False)
    nh = nh[nh.index < "2026-01-01"]
    d = nh[nh.index.hour.isin([20, 21])].copy() if truth else nh[nh.index.hour.isin(C.NIGHT_HOURS)].copy()
    d["ldpd"] = np.log1p(d["dpd"].clip(lower=0))
    known = d["rain_3h_known"].astype(str).str.lower().eq("true")
    d["rain"] = np.where(known, (d["rain_3h"] > 0).astype(float), np.nan)
    d["month"], d["year"] = d.index.month, d.index.year
    if truth:
        d = d.dropna(subset=["cloud_manual_eff"])
        d["y"] = (d["cloud_manual_eff"] <= 2).astype(int)
    return d


def fit(train, feats):
    sc = StandardScaler().fit(train[feats])
    lr = LogisticRegression(max_iter=2000).fit(sc.transform(train[feats]), train["y"])
    return sc, lr


def predict(sc, lr, d, feats):
    return lr.predict_proba(sc.transform(d[feats]))[:, 1]


def scores(y, p, ref):
    b, br = np.mean((p - y) ** 2), np.mean((ref - y) ** 2)
    return dict(n=len(y), auc=roc_auc_score(y, p), brier=b, bss=1 - b / br, mean_pred=p.mean(), mean_obs=y.mean())


def loyo(d, feats):
    d = d.dropna(subset=feats)
    oof = pd.Series(np.nan, index=d.index); ref = pd.Series(np.nan, index=d.index)
    for yr in sorted(d.year.unique()):
        tr, te = d[d.year != yr], d[d.year == yr]
        sc, lr = fit(tr, feats)
        oof[te.index] = predict(sc, lr, te, feats)
        ref[te.index] = te.month.map(tr.groupby("month").y.mean()).values
    return d, oof, ref


def main():
    ys = load_hours("467550")
    all_feats = sorted({f for fs in MODELS.values() for f in fs})
    common = ys.dropna(subset=all_feats)          # same rows for every model -> fair comparison
    rows, oofs = [], {}
    for name, feats in MODELS.items():
        d, oof, ref = loyo(common, feats)
        oofs[name] = (d, oof, ref)
        rows.append(dict(model=name, **scores(d.y.values, oof.values, ref.values)))
        per_year = [roc_auc_score(g.y, oof[g.index]) for _, g in d.groupby("year")]
        rows[-1].update(auc_year_min=min(per_year), auc_year_max=max(per_year))
    comp = pd.DataFrame(rows).round(4)
    comp.to_csv(T / "week07_model_comparison.csv", index=False, encoding="utf-8-sig")
    print(comp.to_string(index=False))

    # final fits on all Yushan years -> formula
    formula, coefs = {}, []
    for key, name in (("station_only", CHOSEN_STATION_ONLY), ("full", CHOSEN_FULL)):
        feats = MODELS[name]
        d = ys.dropna(subset=feats)
        sc, lr = fit(d, feats)
        raw_w = lr.coef_[0] / sc.scale_
        raw_b = float(lr.intercept_[0] - np.sum(lr.coef_[0] * sc.mean_ / sc.scale_))
        formula[key] = dict(model=name, features=feats, intercept=round(raw_b, 4),
                            weights={f: round(float(w), 4) for f, w in zip(feats, raw_w)},
                            standardized={f: round(float(w), 3) for f, w in zip(feats, lr.coef_[0])},
                            trained_on="467550 Yushan, manual cloud 20/21 LST, 2008-2021", n=int(len(d)))
        for f, w in zip(feats, lr.coef_[0]):
            coefs.append(dict(model=name, factor=NAMES[f], standardized_weight=round(float(w), 3),
                              share=round(abs(w) / np.abs(lr.coef_[0]).sum(), 3)))
    json.dump(formula, open(T / "index_formula.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    coefs = pd.DataFrame(coefs); coefs.to_csv(T / "week07_weights.csv", index=False, encoding="utf-8-sig")
    print(coefs.to_string(index=False)); print(json.dumps(formula, ensure_ascii=False)[:600])

    # reliability of the out-of-fold index (chosen models)
    rel = []
    for name in (CHOSEN_STATION_ONLY, CHOSEN_FULL):
        d, oof, _ = oofs[name]
        b = pd.cut(oof * 100, [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100], include_lowest=True)
        g = pd.DataFrame({"y": d.y, "p": oof * 100}).groupby(b, observed=True).agg(n=("y", "size"), index_mean=("p", "mean"), observed=("y", "mean"))
        g["observed"] *= 100; g.insert(0, "model", name); rel.append(g.reset_index(names="index_bin"))
    rel = pd.concat(rel).round(1); rel.to_csv(T / "week07_reliability.csv", index=False, encoding="utf-8-sig")
    print(rel.to_string(index=False))

    # evening-level check at Yushan: mean index of 20 and 21 vs both hours clear
    d, oof, _ = oofs[CHOSEN_FULL]
    e = pd.DataFrame({"y": d.y, "p": oof, "night": d.index.normalize()}).groupby("night").agg(n=("y", "size"), both=("y", "min"), idx=("p", "mean"))
    e = e[e.n == 2]
    print("evening level: nights", len(e), "AUC", round(roc_auc_score(e.both, e.idx), 3))
    ev = dict(nights=int(len(e)), auc=round(roc_auc_score(e.both, e.idx), 3), observed=round(e.both.mean(), 3))

    # transfer: Yushan-fitted index applied unchanged elsewhere; plus each station's own LOYO for reference
    tr_rows = []
    for stn, sname in STATIONS.items():
        dd = load_hours(stn)
        for key, name in (("station_only", CHOSEN_STATION_ONLY), ("full", CHOSEN_FULL)):
            feats = MODELS[name]; d2 = dd.dropna(subset=feats)
            fm = formula[key]
            z = fm["intercept"] + sum(fm["weights"][f] * d2[f] for f in feats)
            p = 1 / (1 + np.exp(-z))
            ref = np.full(len(d2), d2.y.mean())
            own, oof2, _ = loyo(d2, feats)
            tr_rows.append(dict(station=sname, model=name, n=len(d2), auc_yushan_weights=roc_auc_score(d2.y, p),
                                auc_own_weights=roc_auc_score(own.y, oof2), mean_index=p.mean() * 100,
                                observed_clear=d2.y.mean() * 100, bss_yushan_weights=1 - np.mean((p - d2.y) ** 2) / np.mean((ref - d2.y) ** 2)))
    trn = pd.DataFrame(tr_rows).round(3); trn.to_csv(T / "week07_transfer.csv", index=False, encoding="utf-8-sig")
    print(trn.to_string(index=False))

    # apply to Hehuanshan (unvalidated there)
    hh = load_hours("C0H9C0", truth=False)
    out = {}
    for key in ("station_only", "full"):
        fm = formula[key]; d2 = hh.dropna(subset=fm["features"])
        z = fm["intercept"] + sum(fm["weights"][f] * d2[f] for f in fm["features"])
        out[key] = pd.Series(100 / (1 + np.exp(-z)), index=d2.index)
    hx = pd.DataFrame(out); hx.index.name = "time"
    hx.round(1).to_csv(C.PROCESSED / "labels" / "C0H9C0_hourly_index.csv.gz", compression="gzip")
    ev_h = hx[hx.index.hour.isin([20, 21])]
    mon = ev_h.groupby(ev_h.index.month).mean().round(1)
    rule = pd.read_csv(T / "week06_monthly_prob.csv"); rule = rule[rule.group == "合歡山（代理 2011–2025）"].set_index("month").p * 100
    mon["rule_evening_clear_pct"] = rule.round(1)
    mon.index.name = "month"; mon.to_csv(T / "week07_hehuan_monthly_index.csv", encoding="utf-8-sig")
    print(mon.T.to_string())
    print("spearman index vs rule:", mon[["station_only", "rule_evening_clear_pct"]].corr(method="spearman").iloc[0, 1].round(3),
          mon[["full", "rule_evening_clear_pct"]].corr(method="spearman").iloc[0, 1].round(3))
    json.dump(dict(evening_level_yushan=ev), open(T / "week07_extra.json", "w"), indent=1)

    # figures
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.2))
    for name, c in ((CHOSEN_STATION_ONLY, "tab:blue"), (CHOSEN_FULL, "tab:red")):
        r = rel[rel.model == name]
        ax[0].plot(r.index_mean, r.observed, "o-", color=c, label=name)
    ax[0].plot([0, 100], [0, 100], "k--", lw=1); ax[0].set_xlabel("觀星指數"); ax[0].set_ylabel("實際晴的比例 (%)")
    ax[0].set_title("指數準不準：玉山留一年驗證", fontsize=10); ax[0].legend(fontsize=8); ax[0].grid(alpha=.3)
    c2 = coefs[coefs.model == CHOSEN_FULL]
    ax[1].barh(c2.factor, c2.standardized_weight, color=["tab:blue" if w > 0 else "tab:gray" for w in c2.standardized_weight])
    ax[1].axvline(0, color="k", lw=1); ax[1].set_title("各因子權重（標準化後，正值 = 越大越容易晴）", fontsize=10); ax[1].invert_yaxis()
    ax[2].plot(mon.index, mon.station_only, "o-", label="指數：只用測站"); ax[2].plot(mon.index, mon.full, "s-", label="指數：加 ERA5 中高雲")
    ax[2].plot(mon.index, mon.rule_evening_clear_pct, "k--", label="第 6 週門檻規則（兩小時皆晴）")
    ax[2].set_xticks(range(1, 13)); ax[2].set_ylim(0, 60); ax[2].set_title("合歡山傍晚各月平均指數（未在當地驗證）", fontsize=10)
    ax[2].legend(fontsize=8); ax[2].grid(alpha=.3)
    fig.tight_layout(); fig.savefig(F / "fig_week07_index.png", dpi=130); plt.close(fig)


if __name__ == "__main__":
    main()
