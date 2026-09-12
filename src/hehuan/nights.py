# -*- coding: utf-8 -*-
"""Night-window aggregation.

Conventions (docs/DECISIONS.md)
- Night window = 20:00..04:00 LST (9 hourly points). night_date = date of the evening (ts - 12 h).
- Hourly 'clear' = satellite cloud amount (0-10) <= CLEAR_MAX (default 2).
- Definition A (primary): observable if >= 3 consecutive clear hours AND >= 6 valid hours.
- Definition B (strict):  observable if >= 2/3 of valid hours are clear (and >= 6 valid hours).
- Definition C (sensitivity): mean cloud over the window <= 3.
A missing hour counts as NOT clear (it breaks a run) but does not count as valid.
"""
import numpy as np
import pandas as pd

from . import config as C

NIGHT_HOURS = C.NIGHT_HOURS
CLEAR_MAX = C.CLEAR_MAX_CLOUD
MIN_VALID = C.MIN_VALID_HOURS


def night_date(ts) -> pd.Series:
    ts = pd.DatetimeIndex(ts) if not isinstance(ts, pd.Series) else ts
    return (ts - pd.Timedelta(hours=12)).normalize()


def longest_run(bools) -> int:
    best = cur = 0
    for b in bools:
        cur = cur + 1 if b else 0
        best = max(best, cur)
    return best


TRUTH_EXTRA_HOURS = [5]   # 05 LST kept in the night-hours table for winter pre-dawn validation only


def night_hours_frame(hourly: pd.DataFrame) -> pd.DataFrame:
    """Keep the 9 night hours (+05 LST for validation) and add night / second_half columns."""
    d = hourly[hourly.index.hour.isin(NIGHT_HOURS + TRUTH_EXTRA_HOURS)].copy()
    d["night"] = night_date(d.index)
    d["second_half"] = d.index.hour <= 4
    return d


def label_from_clear(clear: pd.Series, valid: pd.Series, mean_cloud: pd.Series,
                     min_valid=MIN_VALID, min_run=C.MIN_CLEAR_RUN, frac_b=2 / 3, mean_c=3.0) -> pd.DataFrame:
    """Vectorised night labels from per-hour 'clear' (bool, False when missing) and 'valid' (bool) series
    that are indexed by hour-ending time; returns one row per night."""
    df = pd.DataFrame({"clear": clear.astype(bool), "valid": valid.astype(bool), "cloud": mean_cloud})
    df = df[df.index.hour.isin(NIGHT_HOURS)]
    df["night"] = night_date(df.index)
    g = df.groupby("night")
    out = pd.DataFrame({
        "n_valid": g["valid"].sum(),
        "n_clear": g["clear"].sum(),
        "longest_clear_run": g["clear"].apply(lambda s: longest_run(s.to_numpy())),
        "mean_cloud": g["cloud"].mean(),
    })
    ok = out["n_valid"] >= min_valid
    out["def_A"] = np.where(ok, (out["longest_clear_run"] >= min_run).astype(float), np.nan)
    out["def_B"] = np.where(ok, (out["n_clear"] / out["n_valid"].replace(0, np.nan) >= frac_b).astype(float), np.nan)
    out["def_C"] = np.where(ok, (out["mean_cloud"] <= mean_c).astype(float), np.nan)
    return out


def label_nights(df: pd.DataFrame, time_col="time", cloud_col="cloud", clear_max=CLEAR_MAX, **kw) -> pd.DataFrame:
    """Convenience wrapper used by tests: df with a time column and a 0-10 cloud column."""
    d = df[[time_col, cloud_col]].copy()
    d[time_col] = pd.to_datetime(d[time_col])
    d = d.set_index(time_col).sort_index()
    d = d[d.index.hour.isin(NIGHT_HOURS)]
    valid = d[cloud_col].notna()
    clear = (d[cloud_col] <= clear_max) & valid
    out = label_from_clear(clear, valid, d[cloud_col], **kw)
    return out.reset_index()


def truth_nights(hourly: pd.DataFrame, cloud_col="cloud_sat", clear_max=CLEAR_MAX) -> pd.DataFrame:
    """Night truth table from a satellite/observed cloud column (0-10)."""
    d = hourly[hourly.index.hour.isin(NIGHT_HOURS)]
    valid = d[cloud_col].notna()
    clear = (d[cloud_col] <= clear_max) & valid
    return label_from_clear(clear, valid, d[cloud_col])


def station_night_aggregates(hourly: pd.DataFrame) -> pd.DataFrame:
    """Per-night summaries of station variables (for climatology plots and transfer checks)."""
    d = night_hours_frame(hourly)
    d = d[d.index.hour.isin(NIGHT_HOURS)]
    g = d.groupby("night")
    agg = {}
    for c in ("rh", "dpd", "t_air", "wind", "pres"):
        if c in d:
            agg[f"{c}_mean"] = g[c].mean()
            agg[f"{c}_min"] = g[c].min()
            agg[f"{c}_max"] = g[c].max()
    if "precip" in d:
        agg["precip_night"] = g["precip"].sum(min_count=1)
        agg["precip_known_hours"] = g["precip"].count()
    if "solar" in d:   # daytime solar of the evening day (proxy for afternoon convection) is added elsewhere
        pass
    out = pd.DataFrame(agg)
    out["n_hours_rh"] = g["rh"].count() if "rh" in d else 0
    return out


def era5_night_aggregates(era5: pd.DataFrame) -> pd.DataFrame:
    d = era5[era5.index.hour.isin(NIGHT_HOURS)].copy()
    d["night"] = night_date(d.index)
    g = d.groupby("night")
    out = pd.DataFrame({
        "e_tcc_mean": g["e_tcc"].mean(), "e_tcc_min": g["e_tcc"].min(), "e_tcc_max": g["e_tcc"].max(),
        "e_lcc_mean": g["e_lcc"].mean(), "e_mcc_mean": g["e_mcc"].mean(), "e_hcc_mean": g["e_hcc"].mean(),
        "e_mh_mean": g["e_mh"].mean(), "e_mh_min": g["e_mh"].min(),
        "e_rh_mean": g["e_rh"].mean(), "e_t2m_mean": g["e_t2m"].mean(),
        "e_precip_night": g["e_precip"].sum(),
    })
    return out
