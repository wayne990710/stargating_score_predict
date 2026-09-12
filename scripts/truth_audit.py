# -*- coding: utf-8 -*-
"""Truth-source audit for a manned station (default 467550 Yushan).

Answers, with tables under results/tables/truth_audit_* and a markdown summary results/truth_audit.md:
  1. Is the satellite-retrieved cloud amount (cloud_sat) usable as a NIGHT truth?  (distribution by year x
     day/night, daytime agreement with manual cloud, monthly night means vs ERA5)
  2. What manual (human) night observations exist?  (coverage by year x hour; meaning of the -99.7 code)
  3. Evening (20/21 LST) manual climatology, with 'sky obscured' counted as not clear.
  4. Are manual gaps weather-related?  (RH / visibility of missing vs present hours)
"""
import sys
import pathlib

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hehuan import config as C, era5, clean   # noqa: E402

NIGHT = [20, 21, 22, 23, 0, 1, 2, 3, 4]
T = C.RESULTS / "tables"


def period(idx):
    hr = idx.hour
    return np.where(np.isin(hr, NIGHT), "night", np.where((hr >= 8) & (hr <= 17), "day", "twilight"))


def main(stn_id="467550"):
    h = pd.read_csv(C.PROCESSED / "hourly" / f"{stn_id}_hourly.csv.gz", index_col="time", parse_dates=["time"])
    h["period"] = period(h.index)
    e = era5.load(stn_id)
    h = h.join(e[["e_tcc", "e_lcc", "e_mcc", "e_hcc", "e_mh"]])
    md = [f"# 真值來源審核：{stn_id}\n"]

    # ---- 1. satellite ------------------------------------------------------------------------
    s = h.dropna(subset=["cloud_sat"])
    if len(s):
        dist = (s.groupby([s.index.year, "period"]).cloud_sat.value_counts(normalize=True).unstack().fillna(0) * 100).round(1)
        dist.to_csv(T / f"truth_audit_sat_distribution_{stn_id}.csv")
        n = h[h.period == "night"]; d = h[h.period == "day"]
        pm = lambda x: x.index.to_period("M")
        monthly = pd.DataFrame({
            "sat_le2_night": n.groupby(pm(n)).cloud_sat.apply(lambda x: (x <= 2).mean()),
            "sat_mean_night": n.groupby(pm(n)).cloud_sat.mean(),
            "sat_n_night": n.groupby(pm(n)).cloud_sat.count(),
            "era5_tcc_night": n.groupby(pm(n)).e_tcc.mean(),
            "era5_mh_night": n.groupby(pm(n)).e_mh.mean(),
            "rh_night": n.groupby(pm(n)).rh.mean(),
            "manual_le2_day": d.groupby(pm(d)).cloud_manual_eff.apply(lambda x: (x <= 2).mean()),
            "sat_le2_day": d.groupby(pm(d)).cloud_sat.apply(lambda x: (x <= 2).mean()),
        }).round(3)
        monthly = monthly[monthly.sat_n_night > 0]
        monthly.to_csv(T / f"truth_audit_sat_monthly_{stn_id}.csv")
        dd = d.dropna(subset=["cloud_manual_eff", "cloud_sat"])
        rows = []
        for y, g in dd.groupby(dd.index.year):
            a, b = g.cloud_manual_eff <= 2, g.cloud_sat <= 2
            rows.append(dict(year=y, n=len(g), manual_clear=int(a.sum()), sat_clear=int(b.sum()),
                             both=int((a & b).sum()), manual_clear_sat_cloudy=int((a & ~b).sum()),
                             manual_cloudy_sat_clear=int((~a & b).sum()),
                             recall_of_manual_clear=round((a & b).sum() / max(a.sum(), 1), 3),
                             kappa=round(_kappa(a, b), 3)))
        conf = pd.DataFrame(rows)
        conf.to_csv(T / f"truth_audit_sat_vs_manual_day_{stn_id}.csv", index=False)
        night_le4 = dist.xs("night", level=1)[[c for c in dist.columns if c <= 4]].sum(axis=1)
        md.append("## 1. 衛星反演雲量（cloud_sat）能不能當夜間真值？\n")
        md.append("夜間（20–04 時）衛星雲量 ≤4 的比例，按年：\n")
        md.append(night_le4.round(1).to_frame("night_le4_%").to_markdown() + "\n")
        md.append("白天（08–17 時，有人工雲量的小時）人工 vs 衛星：\n")
        md.append(conf.to_markdown(index=False) + "\n")
        md.append("結論：" + ("夜間衛星雲量在 2025 年中以前幾乎不曾出現 ≤4 的值（演算法在夜間只有紅外線，"
                          "高山冷地表被判成雲），白天與人工觀測的一致性也偏低。**衛星雲量不能作為夜間真值**，"
                          "只能當 2025-06 以後的輔助對照。" if (night_le4.iloc[0] < 1) else "見表。") + "\n")

    # ---- 2. manual night observations ----------------------------------------------------------
    m = h.cloud_manual_eff.notna()
    cov = m.groupby([h.index.year, h.index.hour]).mean().unstack().round(2)
    cov.to_csv(T / f"truth_audit_manual_coverage_{stn_id}.csv")
    hours = [c for c in (2, 5, 8, 9, 11, 14, 17, 20, 21, 23) if c in cov.columns]
    md.append("## 2. 人工雲量觀測的覆蓋率（年 × 時，含「遮蔽」）\n")
    md.append(cov[hours].to_markdown() + "\n")
    # meaning of -99.7
    raw = clean.read_raw(stn_id)
    t = pd.to_datetime(raw.DataTime); t = t + pd.to_timedelta((t.dt.minute == 59).astype(int), unit="min")
    raw.index = t
    cm = pd.to_numeric(raw["TotalCloudAmount.Instantaneous"], errors="coerce")
    vis = pd.to_numeric(raw.get("Visibility.Instantaneous"), errors="coerce")
    rh = pd.to_numeric(raw["RelativeHumidity.Instantaneous"], errors="coerce")
    rh = rh.where(rh > -90); vis = vis.where(vis > -90)
    ev = raw.index.hour.isin([5, 20, 21])
    cat = pd.Series(np.where(cm.isna(), "null", np.where(cm <= -90, "code_-99.7",
                    np.where(cm <= 2, "clear<=2", "cloudy>2"))), index=raw.index)
    df = pd.DataFrame({"cat": cat, "rh": rh, "vis": vis})[ev]
    sem = df.groupby("cat").agg(n=("rh", "size"), rh_mean=("rh", "mean"), rh_ge98=("rh", lambda x: (x >= 98).mean()),
                                vis_mean=("vis", "mean"), vis_lt1km=("vis", lambda x: (x < 1).mean())).round(2)
    sem.to_csv(T / f"truth_audit_manual_code_semantics_{stn_id}.csv")
    md.append("05/20/21 時人工雲量各類別的濕度與能見度（判讀 -99.7 的意義）：\n")
    md.append(sem.to_markdown() + "\n")
    md.append("結論：-99.7 出現時能見度幾乎都 <1 km、RH 接近飽和，是「天空被霧遮蔽」，計為不可觀星（雲量 10）；"
              "cloud 為 null 但能見度 <1 km 亦視為遮蔽。\n")

    # ---- 3. evening climatology ------------------------------------------------------------------
    ev2 = h[h.index.hour.isin([20, 21])].dropna(subset=["cloud_manual_eff"])
    if len(ev2):
        yrs = sorted(ev2.index.year.unique())
        clim = ev2.groupby([ev2.index.year, ev2.index.month]).cloud_manual_eff.apply(lambda x: (x <= 2).mean()).unstack().round(2)
        clim.loc["all"] = ev2.groupby(ev2.index.month).cloud_manual_eff.apply(lambda x: (x <= 2).mean()).round(2)
        clim.to_csv(T / f"truth_audit_evening_clear_share_{stn_id}.csv")
        md.append(f"## 3. 傍晚（20/21 時）人工雲量 ≤2 的比例，年 × 月（{yrs[0]}–{yrs[-1]}）\n")
        md.append(clim.to_markdown() + "\n")

    # ---- 4. are gaps weather-related? ------------------------------------------------------------
    evh = h[h.index.hour.isin([5, 20, 21])]
    present = evh.cloud_manual_eff.notna()
    gap = pd.DataFrame({
        "n": present.groupby(present).size(),
        "rh_mean": evh.rh.groupby(present).mean().round(1),
        "rh_ge98": evh.rh.groupby(present).apply(lambda x: (x >= 98).mean()).round(3),
        "era5_tcc": evh.e_tcc.groupby(present).mean().round(3),
    })
    gap.index = gap.index.map({True: "manual present", False: "manual missing"})
    gap.to_csv(T / f"truth_audit_manual_gap_weather_{stn_id}.csv")
    md.append("## 4. 人工觀測缺漏是否與天氣有關（05/20/21 時）\n")
    md.append(gap.to_markdown() + "\n")

    (C.RESULTS / "truth_audit.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


def _kappa(a, b):
    a = np.asarray(a, bool); b = np.asarray(b, bool)
    po = (a == b).mean()
    pe = a.mean() * b.mean() + (1 - a.mean()) * (1 - b.mean())
    return (po - pe) / (1 - pe) if pe < 1 else np.nan


if __name__ == "__main__":
    main(*(sys.argv[1:] or ["467550"]))
