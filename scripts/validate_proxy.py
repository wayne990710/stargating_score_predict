# -*- coding: utf-8 -*-
"""Validate the humidity/rain proxy against manual night cloud at a manned station (default Yushan 467550).

Outputs (results/tables, results/figures, results/validation_<stn>.md):
  validation_<stn>_by_fold.csv       metrics per model x held-out year
  validation_<stn>_pooled.csv        out-of-fold pooled metrics, plus by cold/warm and dry/wet season
  validation_<stn>_monthly_bias.csv  monthly clear share: observed vs each model (out-of-fold)
  validation_<stn>_thresholds.json   thresholds/coefficients per fold + final fit on all years
  fig_validation_<stn>_features.png  rh / dpd distributions for clear vs not-clear hours
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
from hehuan import config as C, validate as V   # noqa: E402

MODELS = ["R_dpd", "R_rh", "R_dpd+E_mh", "LR", "E_tcc", "E_mh", "CLIM"]


def main(stn_id="467550", hours=(20, 21), months=None, tag=""):
    nh = pd.read_csv(C.PROCESSED / "night_hours" / f"{stn_id}_night_hours.csv.gz", index_col="time", parse_dates=["time"])
    d = V.prepare(nh, hours)
    if months:
        d = d[d.month.isin(months)]
    stn_id = stn_id + tag
    years = sorted(d.year.unique())
    print(f"{stn_id}: {len(d)} truth hours, years {years[0]}-{years[-1]}, clear share {d.y.mean():.3f}")
    by_fold, oof, ths = V.loyo(d, MODELS)
    T, F = C.RESULTS / "tables", C.RESULTS / "figures"
    by_fold.round(3).to_csv(T / f"validation_{stn_id}_by_fold.csv", index=False)
    pooled = pd.concat([V.pooled_metrics(oof, MODELS), V.pooled_metrics(oof, MODELS, "cold").assign(group=lambda x: "cold_" + x.group.astype(str)),
                        V.pooled_metrics(oof, MODELS, "wet_season").assign(group=lambda x: "wet_" + x.group.astype(str))])
    pooled.round(3).to_csv(T / f"validation_{stn_id}_pooled.csv", index=False)
    mb = V.monthly_bias(oof, MODELS)
    mb.to_csv(T / f"validation_{stn_id}_monthly_bias.csv")
    # final fit on all years (for transfer to Hehuanshan)
    _, th_all = V.fit_predict(d, d)
    json.dump({"folds": ths, "all_years": th_all, "truth_hours": list(hours), "years": [int(y) for y in years],
               "n_hours": int(len(d)), "clear_share": round(float(d.y.mean()), 4)},
              open(T / f"validation_{stn_id}_thresholds.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    # figure: feature distributions
    fig, ax = plt.subplots(1, 3, figsize=(13, 3.8))
    for a, col, lab in zip(ax, ["rh", "dpd", "e_tcc"], ["Relative humidity (%)", "Dew-point depression (degC)", "ERA5 total cloud (0-1)"]):
        for flag, name, color in ((True, "clear (manual <= 2)", "tab:blue"), (False, "not clear", "tab:gray")):
            a.hist(d.loc[d.y == flag, col].dropna(), bins=40, alpha=0.55, density=True, label=name, color=color)
        a.set_xlabel(lab); a.legend(fontsize=8)
    ax[0].set_title(f"{stn_id} night hours {hours}, {years[0]}-{years[-1]}")
    fig.tight_layout(); fig.savefig(F / f"fig_validation_{stn_id}_features.png", dpi=130); plt.close(fig)
    # markdown summary
    pooled_all = pooled[pooled.group == "all"].set_index("model")[["n", "pos_rate", "pred_rate", "precision", "recall", "f1", "bal_acc", "kappa"]].round(3)
    md = [f"# 代理指標驗證：{stn_id}（人工夜間雲量真值，{hours} 時，{years[0]}–{years[-1]}，n={len(d)}）\n",
          "## 留一年交叉驗證（out-of-fold 合併）\n", pooled_all.to_markdown() + "\n",
          "## 各月晴比例：觀測 vs 各模型（out-of-fold）\n", mb.to_markdown() + "\n",
          "## 分層（T<0 / T>=0，乾季 / 濕季）kappa\n",
          pooled[pooled.group != "all"].pivot(index="model", columns="group", values="kappa").round(3).to_markdown() + "\n",
          "## 各折門檻\n",
          pd.DataFrame({y: {m: v.get("threshold") for m, v in t.items() if "threshold" in v} for y, t in ths.items()}).T.round(2).to_markdown() + "\n",
          f"全年份擬合門檻：R_dpd >= {th_all['R_dpd']['threshold']:.2f} degC, R_rh <= {th_all['R_rh']['threshold']:.0f} %, "
          f"E_tcc <= {th_all['E_tcc']['threshold']:.2f}, E_mh <= {th_all['E_mh']['threshold']:.2f}\n"]
    if "LR" in th_all:
        md.append(f"LR 係數（標準化後）：{th_all['LR']['coef']}\n")
    (C.RESULTS / f"validation_{stn_id}.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md[:3]))
    print(pooled[pooled.group != "all"].pivot(index="model", columns="group", values="kappa").round(3).to_string())


if __name__ == "__main__":
    stn = sys.argv[1] if len(sys.argv) > 1 else "467550"
    hrs = tuple(int(h) for h in sys.argv[2].split(",")) if len(sys.argv) > 2 else (20, 21)
    mon = [int(m) for m in sys.argv[3].split(",")] if len(sys.argv) > 3 else None
    tag = sys.argv[4] if len(sys.argv) > 4 else ""
    main(stn, hrs, mon, tag)
