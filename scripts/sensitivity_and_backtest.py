# -*- coding: utf-8 -*-
"""(1) Definition / threshold sensitivity of the Hehuanshan monthly ranking.
    (2) Leave-one-year-out backtest of the recommendation ranking ("lift").

Sensitivity: for rule thresholds dpd in {X-0.5, X, X+0.5} x definitions {def_A, def_B, evening_clear} x
             min_run {2,3,4}: monthly probability table and Spearman rank correlation with the base case.
Lift:        for each year Y, compute half-month probabilities from the other years, rank the nights of Y by
             p_climate x dark_frac, and compare the observed clear share of the top 20 % nights with the
             overall share of that year (lift = ratio). Also a moon-only ranking as a control.
"""
import sys
import json
import pathlib

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hehuan import config as C, climatology as K, nights as N   # noqa: E402


def main(stn_id="C0H9C0", truth_stn="467550"):
    T = C.RESULTS / "tables"
    th = json.load(open(T / f"validation_{truth_stn}_thresholds.json", encoding="utf-8"))
    X = th["all_years"]["R_dpd"]["threshold"]
    nh = pd.read_csv(C.PROCESSED / "night_hours" / f"{stn_id}_night_hours.csv.gz", index_col="time", parse_dates=["time"])
    nh = nh[nh.index < "2026-01-01"]
    base_rule = {"kind": "R_dpd", "threshold": X}
    base = K.proxy_nights(nh, base_rule)
    base_p = K.month_prob(base, "def_A")["p"]
    rows = []
    for dx in (-1.0, -0.5, 0.0, 0.5, 1.0):
        rule = {"kind": "R_dpd", "threshold": X + dx}
        clear = K.apply_rule(nh, rule); valid = K.hourly_valid(nh, rule)
        dummy = pd.Series(np.where(clear, 0.0, 10.0), index=nh.index).where(valid)
        for min_run in (2, 3, 4):
            lab = N.label_from_clear(clear, valid, dummy, min_run=min_run)
            for col in ("def_A", "def_B"):
                p = K.month_prob(lab, col)["p"]
                rho = spearmanr(base_p.reindex(p.index), p).correlation
                rows.append(dict(dpd_threshold=round(X + dx, 2), min_run=min_run, definition=col,
                                 spearman_vs_base=round(rho, 3), annual_mean=round(p.mean(), 3),
                                 **{f"m{m:02d}": round(p.get(m, np.nan), 3) for m in range(1, 13)}))
        pe = K.proxy_nights(nh, rule)
        p = K.month_prob(pe, "evening_clear")["p"]
        rows.append(dict(dpd_threshold=round(X + dx, 2), min_run=np.nan, definition="evening_clear",
                         spearman_vs_base=round(spearmanr(base_p.reindex(p.index), p).correlation, 3),
                         annual_mean=round(p.mean(), 3), **{f"m{m:02d}": round(p.get(m, np.nan), 3) for m in range(1, 13)}))
    sens = pd.DataFrame(rows)
    sens.to_csv(T / f"{stn_id.lower()}_sensitivity.csv", index=False)
    print("sensitivity: Spearman vs base ranges", sens.spearman_vs_base.min(), "-", sens.spearman_vs_base.max())

    # ---- LOYO lift backtest ---------------------------------------------------------------------
    astro = pd.read_csv(C.PROCESSED / "astro" / "hehuan_nights_astro_2008_2027.csv", parse_dates=["night"]).set_index("night")
    out = []
    for col in ("def_A", "evening_clear"):
        d = base[[col]].join(astro[["dark_frac", "dark_hours"]]).dropna()
        d[col] = d[col].astype(float)
        d["year"] = d.index.year
        d["half"] = d.index.month.astype(str).str.zfill(2) + np.where(d.index.day <= 15, "a", "b")
        for y in sorted(d.year.unique()):
            tr, te = d[d.year != y], d[d.year == y].copy()
            if len(te) < 100:
                continue
            clim = tr.groupby("half")[col].mean()
            te["score"] = (te["half"].map(clim) * te["dark_frac"]).astype(float)
            te["score_moon"] = te["dark_frac"].astype(float)
            te["score_clim"] = te["half"].map(clim).astype(float)
            k = max(int(len(te) * 0.2), 1)
            for name in ("score", "score_moon", "score_clim"):
                top = te.nlargest(k, name)
                out.append(dict(definition=col, year=y, ranking=name, n=len(te), base_rate=te[col].mean(),
                                top20_rate=top[col].mean(), lift=top[col].mean() / max(te[col].mean(), 1e-9)))
    lift = pd.DataFrame(out).round(3)
    lift.to_csv(T / f"{stn_id.lower()}_recommend_lift_by_year.csv", index=False)
    summ = lift.groupby(["definition", "ranking"]).agg(base_rate=("base_rate", "mean"), top20_rate=("top20_rate", "mean"),
                                                        lift_mean=("lift", "mean"), lift_min=("lift", "min"), lift_max=("lift", "max"),
                                                        years=("year", "count")).round(3)
    summ.to_csv(T / f"{stn_id.lower()}_recommend_lift_summary.csv")
    print(summ.to_string())


if __name__ == "__main__":
    main(*sys.argv[1:])
