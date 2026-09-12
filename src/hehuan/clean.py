# -*- coding: utf-8 -*-
"""CODiS cache (JSON per station-month) -> raw CSV (per station-year) -> standardized hourly table.

Conventions
-----------
* time      : local standard time (UTC+8), HOUR-ENDING label. CODiS labels the 24th record of a day
              "23:59:00"; we shift it by +1 minute so it becomes next day 00:00 (the 24:00 observation).
* sentinels : CODiS uses numeric missing codes with decimal suffixes (-9997, -9999.7, -99.5, -999.6, ...).
              Every numeric value <= SENTINEL_MAX (-90) becomes NaN. The distinct codes are counted into
              qc/sentinel_codes.csv BEFORE they are removed, so nothing is silently lost.
* precip    : hourly accumulation (mm). rain_3h = sum over the current and previous 2 hours; NaN if ANY of
              the 3 hours is missing ("unknown" is never treated as "no rain").
* dew point : td_obs is the station's own dew point (manned stations only). td_magnus is computed from
              t_air and rh with the Magnus formula (over water; over ice when t_air < 0) so that manned and
              automatic stations share one definition. dpd = t_air - td_magnus.
"""
import gzip
import json
import pathlib

import numpy as np
import pandas as pd

from . import config as C
from .codis_client import CodisClient

COLUMN_MAP = {
    "StationPressure.Instantaneous": "pres",
    "SeaLevelPressure.Instantaneous": "slp",
    "AirTemperature.Instantaneous": "t_air",
    "DewPointTemperature.Instantaneous": "td_obs",
    "RelativeHumidity.Instantaneous": "rh",
    "WindSpeed.Mean": "wind",
    "WindDirection.Mean": "wind_dir",
    "PeakGust.Maximum": "gust",
    "PeakGust.Direction": "gust_dir",
    "Precipitation.Accumulation": "precip",
    "PrecipitationDuration.Total": "precip_dur",
    "SunshineDuration.Total": "sunshine",
    "GlobalSolarRadiation.Accumulation": "solar",
    "Visibility.Instantaneous": "vis_manual",
    "Visibility.AutoMean": "vis_auto",
    "UVIndex.Accumulation": "uv",
    "TotalCloudAmount.Instantaneous": "cloud_manual",
    "TotalCloudAmount.SatRetrieved": "cloud_sat",
}
UNITS = {
    "pres": "hPa", "slp": "hPa", "t_air": "degC", "td_obs": "degC", "rh": "%", "wind": "m/s",
    "wind_dir": "deg", "gust": "m/s", "gust_dir": "deg", "precip": "mm/h", "precip_dur": "h",
    "sunshine": "h", "solar": "MJ/m2", "vis_manual": "km", "vis_auto": "km", "uv": "index",
    "cloud_manual": "0-10", "cloud_sat": "0-10", "sky_obscured": "bool", "cloud_manual_eff": "0-10", "td_magnus": "degC", "dpd": "degC",
    "rain_3h": "mm", "rain_3h_known": "bool", "rain_6h": "mm", "rain_6h_known": "bool",
}


# ----------------------------------------------------------------------------- cache -> raw csv
def load_month(path: pathlib.Path) -> pd.DataFrame:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        js = json.load(f)
    rows = [CodisClient.flatten(r) for r in CodisClient.rows(js)]
    df = pd.DataFrame(rows)
    return df[[c for c in df.columns if not c.endswith("f")]] if len(df) else df


def cache_to_raw_csv(stn_id: str) -> list:
    """Concatenate cached months into data/raw/codis/<stn>/<stn>_<yyyy>.csv.gz (original column names).
    Returns the list of written files."""
    src = C.CODIS_CACHE / stn_id
    files = sorted(src.glob(f"{stn_id}_*.json.gz"))
    if not files:
        return []
    frames = []
    for p in files:
        df = load_month(p)
        if len(df):
            frames.append(df)
    allm = pd.concat(frames, ignore_index=True)
    allm["year"] = allm["DataTime"].str[:4]
    out_dir = C.RAW / "codis" / stn_id
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for y, g in allm.groupby("year"):
        p = out_dir / f"{stn_id}_{y}.csv.gz"
        with gzip.open(p, "wt", encoding="utf-8", newline="") as f:
            g.drop(columns="year").to_csv(f, index=False)
        written.append(p)
    return written


def read_raw(stn_id: str) -> pd.DataFrame:
    files = sorted((C.RAW / "codis" / stn_id).glob(f"{stn_id}_*.csv.gz"))
    return pd.concat([pd.read_csv(p) for p in files], ignore_index=True) if files else pd.DataFrame()


# ----------------------------------------------------------------------------- physics helpers
def magnus_dewpoint(t: pd.Series, rh: pd.Series) -> pd.Series:
    """Dew point (degC) from temperature and RH. Magnus/Sonntag over water (a=17.62, b=243.12),
    over ice when t<0 (a=22.46, b=272.62). rh clipped to [1, 100]."""
    rh = rh.clip(lower=1, upper=100)
    a = np.where(t < 0, 22.46, 17.62)
    b = np.where(t < 0, 272.62, 243.12)
    gamma = np.log(rh / 100.0) + a * t / (b + t)
    return pd.Series(b * gamma / (a - gamma), index=t.index)


# ----------------------------------------------------------------------------- raw -> hourly
def standardize(raw: pd.DataFrame, stn_id: str):
    """Return (hourly DataFrame indexed by hour-ending local time, sentinel-count DataFrame)."""
    df = raw.copy()
    t = pd.to_datetime(df["DataTime"])
    t = t + pd.to_timedelta((t.dt.minute == 59).astype(int), unit="min")   # 23:59 -> next day 00:00
    df["time"] = t
    keep = [c for c in COLUMN_MAP if c in df.columns]
    df = df[["time"] + keep].rename(columns=COLUMN_MAP)
    num_cols = [COLUMN_MAP[c] for c in keep]
    for c in num_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    # manual cloud amount code -99.7 == "sky obscured" (fog at the station: visibility < 1 km in 100 % of
    # cases at Yushan 2015-2021). It is an observation of NOT-clear sky, not a missing value.
    if "cloud_manual" in df.columns:
        df["sky_obscured"] = df["cloud_manual"].between(-99.75, -99.65)
    # sentinel inventory (before removal)
    recs = []
    for c in num_cols:
        v = df[c]
        bad = v[v <= C.SENTINEL_MAX]
        for val, n in bad.value_counts().items():
            recs.append(dict(stn_id=stn_id, column=c, value=val, count=int(n)))
        df.loc[v <= C.SENTINEL_MAX, c] = np.nan
    sentinels = pd.DataFrame(recs, columns=["stn_id", "column", "value", "count"])
    # effective manual cloud for truth labels: obscured -> 10; missing cloud but visibility < 1 km -> 10
    if "cloud_manual" in df.columns:
        eff = df["cloud_manual"].copy()
        eff[df["sky_obscured"]] = 10.0
        if "vis_manual" in df.columns:
            eff[eff.isna() & (df["vis_manual"] < 1.0)] = 10.0
        df["cloud_manual_eff"] = eff
    # de-duplicate timestamps (keep last) and reindex to a complete hourly axis
    df = df.drop_duplicates("time", keep="last").set_index("time").sort_index()
    full = pd.date_range(df.index.min(), df.index.max(), freq="h")
    df = df.reindex(full)
    df.index.name = "time"
    # derived
    if {"t_air", "rh"} <= set(df.columns):
        df["td_magnus"] = magnus_dewpoint(df["t_air"], df["rh"]).round(2)
        df["dpd"] = (df["t_air"] - df["td_magnus"]).round(2)
    if "precip" in df.columns:
        for w in (3, 6):
            s = df["precip"].rolling(w, min_periods=w).sum()
            df[f"rain_{w}h"] = s
            df[f"rain_{w}h_known"] = s.notna()
    return df, sentinels


# ----------------------------------------------------------------------------- QC
def coverage_by_month(df: pd.DataFrame, stn_id: str) -> pd.DataFrame:
    cols = [c for c in df.columns if not c.endswith("_known")]
    g = df[cols].notna().groupby(df.index.to_period("M")).sum()
    n = df.groupby(df.index.to_period("M")).size()
    out = g.div(n, axis=0).round(3)
    out.insert(0, "n_hours", n)
    out.insert(0, "stn_id", stn_id)
    out.index.name = "month"
    return out.reset_index()


def rh_sensor_summary(df: pd.DataFrame, stn_id: str) -> pd.DataFrame:
    """Per year: RH max, share of hours at max, share >= 98, number of distinct values, resolution."""
    out = []
    for y, g in df["rh"].dropna().groupby(df["rh"].dropna().index.year):
        vals = np.sort(g.unique())
        res = float(np.min(np.diff(vals))) if len(vals) > 1 else np.nan
        out.append(dict(stn_id=stn_id, year=y, n=len(g), rh_max=float(g.max()), frac_at_max=round((g == g.max()).mean(), 3),
                        frac_ge_98=round((g >= 98).mean(), 3), frac_ge_95=round((g >= 95).mean(), 3),
                        n_distinct=len(vals), resolution=res, rh_median=float(g.median())))
    return pd.DataFrame(out)


def stuck_hours(df: pd.DataFrame, stn_id: str, min_run: int = 12) -> pd.DataFrame:
    """Flag runs of >= min_run identical non-saturated RH values (sensor stuck). Saturation (rh >= rh_max
    of that year) is excluded because a 3,400 m station really can sit in cloud for a day."""
    rh = df["rh"]
    flag = pd.Series(False, index=df.index)
    for y, g in rh.groupby(rh.index.year):
        sat = g.max()
        same = (g == g.shift()) & (g < sat) & g.notna()
        run_id = (~same).cumsum()
        run_len = same.groupby(run_id).transform("sum") + 1
        flag.loc[g.index] = (run_len >= min_run) & g.notna() & (g < sat)
    df["rh_stuck"] = flag
    s = flag.groupby(flag.index.year).sum()
    return pd.DataFrame(dict(stn_id=stn_id, year=s.index, stuck_hours=s.values))


def timestamp_check(df: pd.DataFrame, stn: pd.Series) -> pd.DataFrame:
    """Hour-ending convention check: the first hour of the day with solar > 0 should be the hour label
    that ENDS after sunrise, i.e. floor(sunrise)+1. Reports the median offset per month; expect 0 or +1
    (+1 also acceptable: the sensor threshold). Large or negative offsets mean a timestamp problem."""
    import ephem
    if "solar" not in df.columns:
        return pd.DataFrame()
    solar = df["solar"]
    day = solar.index.normalize()
    first = solar[solar > 0].groupby(day[solar > 0]).apply(lambda s: s.index.min().hour)
    if first.empty:
        return pd.DataFrame()
    obs = ephem.Observer(); obs.lat, obs.lon, obs.elevation = str(stn.lat), str(stn.lon), float(stn.alt_m)
    obs.pressure = 0; obs.horizon = "-0:50"
    sun = ephem.Sun()
    rec = []
    for d, h in first.items():
        obs.date = (pd.Timestamp(d) - pd.Timedelta(hours=8)).to_pydatetime()   # local midnight -> UTC
        sr = ephem.to_timezone(obs.next_rising(sun), None) if False else obs.next_rising(sun)
        sr_local = pd.Timestamp(sr.datetime()) + pd.Timedelta(hours=8)
        rec.append(dict(date=d, first_solar_hour=h, sunrise_hour=sr_local.hour + sr_local.minute / 60,
                        offset=h - (int(sr_local.hour) + 1)))
    r = pd.DataFrame(rec)
    out = r.groupby(r.date.dt.to_period("M")).offset.agg(["median", "mean", "count"]).round(2)
    out.insert(0, "stn_id", stn.stn_id)
    out.index.name = "month"
    return out.reset_index()
