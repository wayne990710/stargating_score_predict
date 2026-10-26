# -*- coding: utf-8 -*-
"""Week 5: apply the operational definition of a "stargazing night" and label every night at
Taipei (466920), Hehuanshan (C0H9C0) and, for reference, Yushan (467550).

Definition (docs/week05_可觀星夜定義與標記.md):
  clear hour      = total cloud <= 2/10 (manual observation; sky obscured by fog counts as 10)
  EVENING_CLEAR   = 20:00 and 21:00 LST both clear                 <- primary, directly observed / validated
  NIGHT_A         = >= 3 consecutive clear hours within 20-04 LST, >= 6 valid hours   <- secondary, tentative

Label source per station:
  466920 Taipei      manual cloud 20/21 LST (truth), years with night observations
  467550 Yushan      manual cloud 20/21 LST (truth), 2008-2021
  C0H9C0 Hehuanshan  dew-point proxy validated at Yushan (no cloud observation at this station)

Outputs
  data/processed/labels/<stn>_night_labels.csv
  results/tables/week05_label_summary.csv        overall share and n per station x definition
  results/tables/week05_monthly_share.csv        monthly share per station x definition
  results/tables/week05_seasonal_share.csv       seasonal (DJF/MAM/JJA/SON) share
  results/figures/fig_week05_monthly_share.png
"""
import sys
import json
import pathlib

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams["font.family"] = ["Microsoft JhengHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hehuan import config as C, climatology as K   # noqa: E402

END = "2026-01-01"          # 2026 kept out (activity comparison / held-out)
SEASON = {12: "冬 DJF", 1: "冬 DJF", 2: "冬 DJF", 3: "春 MAM", 4: "春 MAM", 5: "春 MAM",
          6: "夏 JJA", 7: "夏 JJA", 8: "夏 JJA", 9: "秋 SON", 10: "秋 SON", 11: "秋 SON"}


def manual_labels(stn: str) -> pd.DataFrame:
    n = pd.read_csv(C.PROCESSED / "nights" / f"{stn}_nights.csv", index_col="night", parse_dates=["night"])
    n = n[n.index < END]
    out = pd.DataFrame(index=n.index)
    out["evening_clear"] = n["evening_clear"]
    out["source"] = np.where(n["evening_clear"].notna(), "manual_cloud_20_21", None)
    out["evening_cloud_mean"] = n["manual_cloud_2021_mean"]
    return out[out.evening_clear.notna()]


def proxy_labels(stn: str, truth_stn="467550") -> pd.DataFrame:
    th = json.load(open(C.RESULTS / "tables" / f"validation_{truth_stn}_thresholds.json", encoding="utf-8"))
    rule = {"kind": "R_dpd", **th["all_years"]["R_dpd"]}
    nh = pd.read_csv(C.PROCESSED / "night_hours" / f"{stn}_night_hours.csv.gz", index_col="time",
                     parse_dates=["time"], low_memory=False)
    nh = nh[nh.index < END]
    pn = K.proxy_nights(nh, rule)
    out = pd.DataFrame(index=pn.index)
    out["evening_clear"] = pn["evening_clear"]
    out["night_A"] = pn["def_A"]
    out["n_valid_hours"] = pn["n_valid"]
    out["longest_clear_run"] = pn["longest_clear_run"]
    out["source"] = f"proxy_dpd>={rule['threshold']:.2f}_validated_at_{truth_stn}"
    out.index.name = "night"
    return out


def summarise(labels: dict) -> tuple:
    rows, mrows, srows = [], [], []
    for (stn, name), lab in labels.items():
        for col in ("evening_clear", "night_A"):
            if col not in lab:
                continue
            v = lab[col].dropna().astype(float)
            if v.empty:
                continue
            rows.append(dict(stn_id=stn, name=name, definition=col, nights=len(v),
                             years=f"{v.index.year.min()}-{v.index.year.max()}", n_years=v.index.year.nunique(),
                             clear_nights=int(v.sum()), share=round(v.mean(), 3)))
            m = v.groupby(v.index.month).agg(["mean", "count"])
            for mo, r in m.iterrows():
                mrows.append(dict(stn_id=stn, name=name, definition=col, month=mo, share=round(r["mean"], 3), nights=int(r["count"])))
            s = v.groupby(v.index.month.map(SEASON)).agg(["mean", "count"])
            for se, r in s.iterrows():
                srows.append(dict(stn_id=stn, name=name, definition=col, season=se, share=round(r["mean"], 3), nights=int(r["count"])))
    return pd.DataFrame(rows), pd.DataFrame(mrows), pd.DataFrame(srows)


def main():
    out_dir = C.PROCESSED / "labels"
    out_dir.mkdir(parents=True, exist_ok=True)
    labels = {
        ("466920", "臺北（人工雲量）"): manual_labels("466920"),
        ("467550", "玉山（人工雲量，參考）"): manual_labels("467550"),
        ("C0H9C0", "合歡山（露點差代理）"): proxy_labels("C0H9C0"),
    }
    for (stn, _), lab in labels.items():
        lab.to_csv(out_dir / f"{stn}_night_labels.csv", float_format="%.3f")
    summ, monthly, seasonal = summarise(labels)
    T = C.RESULTS / "tables"
    summ.to_csv(T / "week05_label_summary.csv", index=False, encoding="utf-8-sig")
    monthly.to_csv(T / "week05_monthly_share.csv", index=False, encoding="utf-8-sig")
    seasonal.to_csv(T / "week05_seasonal_share.csv", index=False, encoding="utf-8-sig")
    print(summ.to_string(index=False))
    print(seasonal.pivot_table(index=["name", "definition"], columns="season", values="share").to_string())

    fig, ax = plt.subplots(figsize=(10, 4.2))
    styles = {"466920": ("tab:gray", "o"), "467550": ("tab:green", "s"), "C0H9C0": ("tab:blue", "D")}
    for (stn, name), _ in labels.items():
        d = monthly[(monthly.stn_id == stn) & (monthly.definition == "evening_clear")]
        c, mk = styles[stn]
        ax.plot(d.month, d.share, marker=mk, color=c, label=name)
    d = monthly[(monthly.stn_id == "C0H9C0") & (monthly.definition == "night_A")]
    ax.plot(d.month, d.share, ls="--", color="tab:blue", alpha=0.5, label="合歡山 整夜定義（暫定）")
    ax.set_xticks(range(1, 13)); ax.set_xticklabels([f"{m}月" for m in range(1, 13)])
    ax.set_ylim(0, 0.8); ax.set_ylabel("可觀星夜比例")
    ax.set_title("各月可觀星夜比例：傍晚 20、21 時雲量皆 ≤ 2 成")
    ax.legend(fontsize=8); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(C.RESULTS / "figures" / "fig_week05_monthly_share.png", dpi=130); plt.close(fig)


if __name__ == "__main__":
    main()
