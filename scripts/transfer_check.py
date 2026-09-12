# -*- coding: utf-8 -*-
"""Transfer evidence: is it reasonable to apply a rule validated at Yushan (3845 m) to Hehuanshan (3402 m)?

  1. Night-time feature distributions (rh, dpd, t_air, wind) by month: Yushan vs Hehuanshan vs Kunyang
  2. RH sensor behaviour per station-year (from qc/rh_sensor_by_year.csv)
  3. Hehuanshan vs Kunyang (2.5 km apart): same-hour agreement of the proxy rule and RH difference
  4. Altitude gradient of the proxy skill at manned stations, if their validation files exist
Outputs results/tables/transfer_* and results/figures/fig_transfer_feature_dist.png
"""
import sys
import json
import pathlib

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams["font.family"] = ["Microsoft JhengHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hehuan import config as C, climatology as K, validate as V   # noqa: E402

STATIONS = ["467550", "C0H9C0", "C0H990", "467530", "466910", "466920"]


def load_nh(stn):
    p = C.PROCESSED / "night_hours" / f"{stn}_night_hours.csv.gz"
    return pd.read_csv(p, index_col="time", parse_dates=["time"]) if p.exists() else None


def main():
    T, F = C.RESULTS / "tables", C.RESULTS / "figures"
    frames = {s: load_nh(s) for s in STATIONS}
    frames = {s: f for s, f in frames.items() if f is not None}
    # 1. distributions
    rows = []
    for s, f in frames.items():
        g = f.groupby(f.index.month)
        for col in ("rh", "dpd", "t_air", "wind"):
            if col in f:
                q = g[col].quantile([0.25, 0.5, 0.75]).unstack()
                for m in q.index:
                    rows.append(dict(stn_id=s, month=m, var=col, q25=q.loc[m, 0.25], q50=q.loc[m, 0.5], q75=q.loc[m, 0.75]))
    dist = pd.DataFrame(rows).round(2)
    dist.to_csv(T / "transfer_feature_dist_by_month.csv", index=False)
    fig, ax = plt.subplots(1, 3, figsize=(14, 4))
    for a, col, lab in zip(ax, ("rh", "dpd", "t_air"), ("night RH (%)", "night dew-point depression (degC)", "night air temp (degC)")):
        for s in ("467550", "C0H9C0", "C0H990", "467530"):
            d = dist[(dist.stn_id == s) & (dist["var"] == col)]
            if len(d):
                a.plot(d.month, d.q50, marker="o", label=f"{s} {C.station(s).name_zh}")
                a.fill_between(d.month, d.q25, d.q75, alpha=0.12)
        a.set_xlabel("month"); a.set_ylabel(lab); a.legend(fontsize=7)
    fig.suptitle("Night-hour (20-04 LST) median and IQR by month"); fig.tight_layout()
    fig.savefig(F / "fig_transfer_feature_dist.png", dpi=130); plt.close(fig)

    # 3. Hehuanshan vs Kunyang
    if "C0H9C0" in frames and "C0H990" in frames:
        th = json.load(open(T / "validation_467550_thresholds.json", encoding="utf-8"))
        rule = {"kind": "R_dpd", **th["all_years"]["R_dpd"]}
        a, b = frames["C0H9C0"], frames["C0H990"]
        j = a[["rh", "dpd"]].join(b[["rh", "dpd"]], lsuffix="_hh", rsuffix="_ky").dropna()
        pa = K.apply_rule(a, rule).reindex(j.index); pb = K.apply_rule(b, rule).reindex(j.index)
        out = dict(n_hours=len(j), rh_diff_mean=float((j.rh_hh - j.rh_ky).mean()), rh_diff_mad=float((j.rh_hh - j.rh_ky).abs().median()),
                   dpd_diff_mean=float((j.dpd_hh - j.dpd_ky).mean()), rule_agreement=float((pa == pb).mean()),
                   rule_kappa=float(V.kappa(pa, pb)), clear_share_hehuan=float(pa.mean()), clear_share_kunyang=float(pb.mean()))
        pd.Series(out).round(3).to_csv(T / "transfer_hehuan_vs_kunyang.csv")
        print("Hehuanshan vs Kunyang:", {k: round(v, 3) for k, v in out.items()})

    # 4. altitude gradient of skill
    rows = []
    for s in ("466920", "466910", "467530", "467550"):
        p = T / f"validation_{s}_pooled.csv"
        if p.exists():
            d = pd.read_csv(p); d = d[d.group == "all"].set_index("model")
            st = C.station(s)
            rows.append(dict(stn_id=s, name=st.name_zh, alt_m=st.alt_m, n=int(d.loc["R_dpd", "n"]),
                             clear_share=d.loc["R_dpd", "pos_rate"], kappa_R_dpd=d.loc["R_dpd", "kappa"],
                             kappa_R_rh=d.loc["R_rh", "kappa"], kappa_LR=d.loc["LR", "kappa"] if "LR" in d.index else None,
                             kappa_E_mh=d.loc["E_mh", "kappa"], kappa_CLIM=d.loc["CLIM", "kappa"],
                             kappa_combined=d.loc["R_dpd+E_mh", "kappa"] if "R_dpd+E_mh" in d.index else None))
    if rows:
        g = pd.DataFrame(rows).sort_values("alt_m").round(3)
        g.to_csv(T / "transfer_altitude_gradient.csv", index=False)
        print(g.to_string(index=False))


if __name__ == "__main__":
    main()
