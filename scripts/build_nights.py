# -*- coding: utf-8 -*-
"""Build, for every station with a processed hourly table:
  data/processed/night_hours/<stn>_night_hours.csv.gz  (the 9 night hours per night, station + ERA5 joined)
  data/processed/nights/<stn>_nights.csv                (one row per night: truth labels if cloud_sat exists,
                                                          station aggregates, ERA5 aggregates, astro if available)
"""
import sys
import gzip
import pathlib

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hehuan import config as C, era5, nights   # noqa: E402

ASTRO = {"C0H9C0": "hehuan", "C0H990": "hehuan", "C0T790": "hehuan", "C0I530": "hehuan", "C0I540": "hehuan",
         "466920": "taipei"}


def load_hourly(stn_id: str) -> pd.DataFrame:
    p = C.PROCESSED / "hourly" / f"{stn_id}_hourly.csv.gz"
    return pd.read_csv(p, index_col="time", parse_dates=["time"])


def main(stn_ids):
    (C.PROCESSED / "night_hours").mkdir(exist_ok=True)
    (C.PROCESSED / "nights").mkdir(exist_ok=True)
    if not stn_ids:
        stn_ids = [p.name.split("_")[0] for p in sorted((C.PROCESSED / "hourly").glob("*_hourly.csv.gz"))]
    for stn_id in stn_ids:
        h = load_hourly(stn_id)
        e = era5.load(stn_id)
        # --- night hours (long table) ---
        nh = nights.night_hours_frame(h)
        cols = [c for c in ("cloud_sat", "cloud_manual", "cloud_manual_eff", "sky_obscured", "vis_manual", "rh", "t_air", "td_obs", "td_magnus", "dpd",
                            "precip", "rain_3h", "rain_3h_known", "rain_6h", "rain_6h_known", "wind", "gust",
                            "pres", "rh_stuck") if c in nh]
        nh = nh[["night", "second_half"] + cols].join(e[["e_tcc", "e_lcc", "e_mcc", "e_hcc", "e_mh", "e_rh", "e_t2m", "e_precip"]])
        with gzip.open(C.PROCESSED / "night_hours" / f"{stn_id}_night_hours.csv.gz", "wt", encoding="utf-8", newline="") as f:
            nh.to_csv(f, float_format="%.3f")
        # --- nights ---
        parts = [nights.station_night_aggregates(h), nights.era5_night_aggregates(e)]
        if "cloud_sat" in h:
            t = nights.truth_nights(h, "cloud_sat")
            t.columns = [f"sat_{c}" for c in t.columns]
            parts.insert(0, t)
        if "cloud_manual" in h:   # evening manual cloud (20/21 LST) where available
            d = h[h.index.hour.isin([20, 21])]
            m = d.groupby(nights.night_date(d.index))["cloud_manual_eff"].agg(["mean", "max", "count"])
            m.columns = ["manual_cloud_2021_mean", "manual_cloud_2021_max", "manual_cloud_2021_n"]
            m["evening_clear"] = (m["manual_cloud_2021_max"] <= 2).where(m["manual_cloud_2021_n"] == 2)
            parts.append(m)
        n = pd.concat(parts, axis=1)
        n.index.name = "night"
        n = n[n.index >= h.index.min().normalize()]
        if stn_id in ASTRO:
            a = pd.read_csv(C.PROCESSED / "astro" / f"{ASTRO[stn_id]}_nights_astro_2008_2027.csv", parse_dates=["night"])
            n = n.join(a.set_index("night")[["moon_illum", "dark_hours", "night_hours", "dark_frac"]])
        n.to_csv(C.PROCESSED / "nights" / f"{stn_id}_nights.csv", float_format="%.3f")
        msg = f"{stn_id}: {len(n)} nights"
        if "sat_def_A" in n:
            v = n["sat_def_A"].dropna()
            msg += f"; satellite-labelled nights={len(v)}, def_A clear share={v.mean():.3f}"
        print(msg)


if __name__ == "__main__":
    main(sys.argv[1:])
