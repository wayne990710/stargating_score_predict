# -*- coding: utf-8 -*-
"""ERA5 (via Open-Meteo, models=era5) loader. Timestamps are local (Asia/Taipei) instantaneous hourly values,
so they align directly with CODiS hour-ending labels (both are 'the state at HH:00')."""
import json

import pandas as pd

from . import config as C

FILES = {
    "C0H9C0": "C0H9C0_hehuanshan", "C0H990": "C0H990_kunyang", "467550": "467550_yushan",
    "466920": "466920_taipei", "466910": "466910_anbu", "467530": "467530_alishan",
    # neighbours share the Hehuanshan cell
    "C0T790": "C0H9C0_hehuanshan", "C0I530": "C0H9C0_hehuanshan", "C0I540": "C0H9C0_hehuanshan",
}
RENAME = {"cloud_cover": "e_tcc", "cloud_cover_low": "e_lcc", "cloud_cover_mid": "e_mcc",
          "cloud_cover_high": "e_hcc", "relative_humidity_2m": "e_rh", "temperature_2m": "e_t2m",
          "dew_point_2m": "e_td2m", "precipitation": "e_precip", "surface_pressure": "e_sp"}


def load(stn_id: str) -> pd.DataFrame:
    name = FILES[stn_id]
    df = pd.read_csv(C.RAW / "era5_openmeteo" / f"era5_openmeteo_{name}.csv.gz")
    df["time"] = pd.to_datetime(df["time"])
    df = df.rename(columns=RENAME).set_index("time").sort_index()
    for c in ("e_tcc", "e_lcc", "e_mcc", "e_hcc"):
        df[c] = df[c] / 100.0          # % -> fraction 0-1
    # 'cloud above the station' candidates for a high-altitude site
    df["e_mh"] = 1 - (1 - df["e_mcc"]) * (1 - df["e_hcc"])      # random-overlap mid+high
    df["e_maxmh"] = df[["e_mcc", "e_hcc"]].max(axis=1)
    return df


def meta(stn_id: str) -> dict:
    m = json.loads((C.RAW / "era5_openmeteo" / "meta.json").read_text(encoding="utf-8"))
    return m.get(FILES[stn_id], {})
