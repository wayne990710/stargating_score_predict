# -*- coding: utf-8 -*-
"""Apply a validated hourly proxy rule to a station's night hours and summarise the stargazing climatology."""
import numpy as np
import pandas as pd

from . import config as C
from .nights import label_from_clear, night_date


def apply_rule(nh: pd.DataFrame, rule: dict) -> pd.Series:
    """rule = {'kind': 'R_dpd'|'R_rh', 'threshold': x}. Returns bool Series 'predicted clear' per hour
    (False when the feature is missing or rain in the last 3 h is unknown/non-zero)."""
    no_rain = nh["rain_3h_known"].astype(bool) & (nh["rain_3h"] == 0)
    if rule["kind"] == "R_dpd":
        x = nh["dpd"]; p = x >= rule["threshold"]
    elif rule["kind"] == "R_rh":
        x = nh["rh"]; p = x <= rule["threshold"]
    else:
        raise ValueError(rule)
    return (p & no_rain & x.notna()).astype(bool)


def hourly_valid(nh: pd.DataFrame, rule: dict) -> pd.Series:
    x = nh["dpd"] if rule["kind"] == "R_dpd" else nh["rh"]
    return x.notna() & nh["rain_3h_known"].astype(bool)


def proxy_nights(nh: pd.DataFrame, rule: dict) -> pd.DataFrame:
    """One row per night with n_valid, n_clear, longest run, def_A/B (proxy) and evening_clear_proxy (20&21)."""
    clear = apply_rule(nh, rule)
    valid = hourly_valid(nh, rule)
    cloud_dummy = pd.Series(np.where(clear, 0.0, 10.0), index=nh.index).where(valid)
    out = label_from_clear(clear, valid, cloud_dummy)
    ev = nh[nh.index.hour.isin([20, 21])]
    evc = clear[ev.index].groupby(night_date(ev.index)).agg(["sum", "count"])
    evv = valid[ev.index].groupby(night_date(ev.index)).sum()
    out["evening_clear"] = ((evc["sum"] == 2) & (evv == 2)).where(evv == 2)
    out["evening_any_clear"] = ((evc["sum"] >= 1) & (evv == 2)).where(evv == 2)
    return out


def month_prob(nights: pd.DataFrame, col: str, by="month") -> pd.DataFrame:
    d = nights.dropna(subset=[col]).copy()
    d["month"] = d.index.month
    d["half"] = np.where(d.index.day <= 15, "a", "b")
    d["halfmonth"] = d["month"].astype(str).str.zfill(2) + d["half"]
    key = "halfmonth" if by == "halfmonth" else "month"
    g = d.groupby(key)[col]
    return pd.DataFrame({"p": g.mean(), "n": g.count(), "n_years": d.groupby(key).apply(lambda x: x.index.year.nunique())})


def year_block_bootstrap(nights: pd.DataFrame, col: str, by="month", n_boot=1000, seed=0) -> pd.DataFrame:
    """95 % CI of the monthly (or half-monthly) probability by resampling whole years with replacement."""
    rng = np.random.default_rng(seed)
    d = nights.dropna(subset=[col]).copy()
    d["year"] = d.index.year
    d["month"] = d.index.month
    d["half"] = np.where(d.index.day <= 15, "a", "b")
    d["halfmonth"] = d["month"].astype(str).str.zfill(2) + d["half"]
    key = "halfmonth" if by == "halfmonth" else "month"
    years = np.array(sorted(d.year.unique()))
    # pre-aggregate per (year, key): sum and count
    agg = d.groupby(["year", key])[col].agg(["sum", "count"]).unstack(key)
    keys = agg["sum"].columns
    boots = np.empty((n_boot, len(keys)))
    for i in range(n_boot):
        ys = rng.choice(years, size=len(years), replace=True)
        s = agg["sum"].loc[ys].sum(axis=0); c = agg["count"].loc[ys].sum(axis=0)
        boots[i] = (s / c.replace(0, np.nan)).to_numpy()
    lo, hi = np.nanpercentile(boots, [2.5, 97.5], axis=0)
    base = month_prob(nights, col, by)
    base["ci_lo"] = pd.Series(lo, index=keys); base["ci_hi"] = pd.Series(hi, index=keys)
    return base.round(3)


def month_hour_heatmap(nh: pd.DataFrame, rule: dict) -> pd.DataFrame:
    clear = apply_rule(nh, rule); valid = hourly_valid(nh, rule)
    d = pd.DataFrame({"clear": clear[valid], "month": nh.index.month[valid], "hour": nh.index.hour[valid]})
    tab = d.groupby(["month", "hour"]).clear.mean().unstack("hour")
    return tab[[h for h in C.NIGHT_HOURS if h in tab.columns]].round(3)


def persistence(nights: pd.DataFrame, col: str) -> pd.DataFrame:
    """P(clear tonight | clear last night) by month, and P(at least one clear night in 2 / 3 consecutive nights)."""
    d = nights[[col]].copy()
    d["prev"] = d[col].shift(1)
    d["next1"] = d[col].shift(-1); d["next2"] = d[col].shift(-2)
    d["month"] = d.index.month
    g = d.groupby("month")
    out = pd.DataFrame({
        "p_clear": g[col].mean(),
        "p_clear_given_prev_clear": d[d.prev == 1].groupby("month")[col].mean(),
        "p_clear_given_prev_cloudy": d[d.prev == 0].groupby("month")[col].mean(),
        "p_any_of_2": g.apply(lambda x: ((x[col] == 1) | (x["next1"] == 1)).mean()),
        "p_any_of_3": g.apply(lambda x: ((x[col] == 1) | (x["next1"] == 1) | (x["next2"] == 1)).mean()),
    })
    return out.round(3)
