# -*- coding: utf-8 -*-
"""Week 9: Lulin Observatory raw files -> hourly table with night cloud state and dew-point depression.

Outputs
  data/processed/lulin/lulin_hourly.csv.gz        every hour 2009-2025 (weather) joined with cloud sensor 2012-2024
  data/processed/lulin/lulin_night_hours.csv.gz   20-04 LST hours that have BOTH a cloud reading and a dew-point depression
  results/tables/week09_lulin_coverage.csv        per year: hours available, clock check, clear share
  results/tables/week09_lulin_sky_hist.csv        night distribution of sky-minus-ambient per year (threshold evidence)
  results/figures/fig_week09_lulin.png
"""
import sys
import gzip
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
from hehuan import config as C, lulin as L   # noqa: E402

NIGHT = C.NIGHT_HOURS
BINS = list(range(-60, 25, 5))


def best_lag(cs_amb: pd.Series, w_t: pd.Series) -> tuple:
    """Clock check: hourly lag (cloud-sensor clock minus weather clock) maximising corr of the two thermometers."""
    j = pd.concat([cs_amb, w_t], axis=1, keys=["a", "b"]).dropna()
    if len(j) < 500:
        return np.nan, np.nan, np.nan
    best = max(range(-9, 10), key=lambda k: j["a"].corr(j["b"].shift(k)))
    return best, round(j["a"].corr(j["b"].shift(best)), 3), round(j["a"].corr(j["b"]), 3)


def main():
    out_dir = C.PROCESSED / "lulin"; out_dir.mkdir(parents=True, exist_ok=True)
    frames, cov, hist = [], [], []
    for y in range(2009, 2026):
        w = L.read_weather(y)
        wh = L.weather_hourly(w)
        try:
            c = L.read_cloudsensor(y)
            ch = L.cloud_hourly(c)
        except FileNotFoundError:
            c, ch = None, pd.DataFrame(columns=["sky_med", "sky_min", "sky_max", "n_sky", "wet_any", "amb_cs", "clear"])
        h = wh.join(ch, how="outer")
        h = h[(h.index >= f"{y}-01-01 01:00") & (h.index <= f"{y + 1}-01-01 00:00")]
        frames.append(h)
        night = h[h.index.hour.isin(NIGHT)]
        both = night.dropna(subset=["sky_med", "t_air", "rh"])
        lag, r_best, r0 = best_lag(h["amb_cs"], h["t_air"]) if c is not None else (np.nan, np.nan, np.nan)
        tmax_hour = h["t_air"].groupby(h.index.hour).mean().idxmax() if h["t_air"].notna().any() else np.nan
        cov.append(dict(year=y, weather_hours=int(h["t_air"].notna().sum()), cloud_hours=int(h["sky_med"].notna().sum()),
                        night_hours_cloud=int(night["sky_med"].notna().sum()), night_hours_both=len(both),
                        nights_with_6h=int((both.groupby((both.index - pd.Timedelta(hours=12)).normalize()).size() >= 6).sum()),
                        clear_share_night=round(night["clear"].dropna().astype(bool).mean(), 3) if night["sky_med"].notna().any() else np.nan,
                        clock_lag_h=lag, corr_at_best_lag=r_best, corr_at_lag0=r0, warmest_hour=tmax_hour,
                        bar_median=round(w["bar"].median(), 1), rain_total=round(w["rain"].sum(), 1),
                        cs_bad_lines=(c.attrs.get("bad_lines") if c is not None else np.nan)))
        if night["sky_med"].notna().any():
            cnt, _ = np.histogram(night["sky_med"].dropna(), bins=BINS)
            hist.append(pd.Series(cnt, index=[f"{a}~{a + 5}" for a in BINS[:-1]], name=y))
        print(cov[-1], flush=True)
    allh = L.add_derived(pd.concat(frames).sort_index())
    allh = allh[~allh.index.duplicated()]
    allh.index.name = "time"
    cols = ["t_air", "rh", "td_davis", "td_magnus", "dpd", "wind", "precip", "rain_3h", "rain_3h_known",
            "sky_med", "sky_min", "sky_max", "n_sky", "wet_any", "amb_cs", "clear", "n_min"]
    with gzip.open(out_dir / "lulin_hourly.csv.gz", "wt", encoding="utf-8", newline="") as f:
        allh[cols].to_csv(f, float_format="%.2f")
    nh = allh[allh.index.hour.isin(NIGHT)].dropna(subset=["sky_med", "dpd"])[cols].copy()
    nh.insert(0, "night", (nh.index - pd.Timedelta(hours=12)).normalize())
    with gzip.open(out_dir / "lulin_night_hours.csv.gz", "wt", encoding="utf-8", newline="") as f:
        nh.to_csv(f, float_format="%.2f")
    T, F = C.RESULTS / "tables", C.RESULTS / "figures"
    cov = pd.DataFrame(cov); cov.to_csv(T / "week09_lulin_coverage.csv", index=False)
    hist = pd.DataFrame(hist); hist.index.name = "year"; hist.to_csv(T / "week09_lulin_sky_hist.csv")
    print("night hours with cloud + dpd:", len(nh), "| nights:", nh.night.nunique(), "| clear share:", round(nh.clear.astype(bool).mean(), 3))
    print("Davis dew point vs Magnus MAE:", round((allh.td_davis - allh.td_magnus).abs().mean(), 3))
    m = nh.groupby([nh.index.month, nh.index.hour]).clear.apply(lambda s: s.astype(bool).mean()).unstack()[NIGHT].round(2)
    m.to_csv(T / "week09_lulin_clear_month_hour.csv"); print(m.to_string())

    fig, ax = plt.subplots(1, 3, figsize=(15, 4))
    tot = hist.sum()
    ax[0].bar(range(len(tot)), tot.values, color=["tab:blue" if int(k.split("~")[0]) < L.CLEAR_MAX_SKY else "tab:gray" for k in tot.index])
    ax[0].set_xticks(range(len(tot))[::2]); ax[0].set_xticklabels([k.split("~")[0] for k in tot.index][::2])
    ax[0].set_xlabel("天空溫度 − 環境溫度 (°C)"); ax[0].set_title(f"鹿林夜間雲感測器讀值分布（藍 = 判為晴，≤ {L.CLEAR_MAX_SKY:.0f}）", fontsize=10)
    ax[1].bar(cov.year, cov.night_hours_both, color="tab:green"); ax[1].set_title("每年可用的夜間小時數（雲況與露點差皆有）", fontsize=10)
    mm = nh.groupby(nh.index.month).clear.apply(lambda s: s.astype(bool).mean())
    ax[2].bar(mm.index, mm.values, color="tab:blue"); ax[2].set_xticks(range(1, 13)); ax[2].set_ylim(0, 1)
    ax[2].set_title("鹿林各月夜間小時為晴的比例（雲感測器）", fontsize=10)
    fig.tight_layout(); fig.savefig(F / "fig_week09_lulin.png", dpi=130); plt.close(fig)


if __name__ == "__main__":
    main()
