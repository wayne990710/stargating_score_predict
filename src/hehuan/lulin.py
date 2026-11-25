# -*- coding: utf-8 -*-
"""Parsers for the Lulin Observatory (NCU, 23.469N 120.874E, 2862 m) raw files.

cloud sensor (Boltwood Cloud Sensor II log, one row every ~10 min, local time):
    Date Time U SkyRl Ambnt Sensr Block Hea <flags1> <flags2> <raw> <ver>
    SkyRl = sky temperature minus ambient temperature (degC): strongly negative = clear sky.
    flags2 last digit = wet/rain flag of the sensor.
weather station (Davis WeatherLink export, one row per minute, local time, tab separated, 2 header lines):
    Date(yy/mm/dd) Time("12:01 a" before 2018, "0:01" later) TempOut Hi Low OutHum DewPt WindSpeed ... Bar Rain ...

Hourly convention matches the CWA tables: hour-ending labels, local standard time (UTC+8).
"""
import pathlib

import numpy as np
import pandas as pd

from . import config as C
from .clean import magnus_dewpoint

LULIN_DIR = C.CACHE_DIR / "lulin"
LAT, LON, ALT = 23.469, 120.874, 2862.0
CLEAR_MAX_SKY = -20.0      # sky-minus-ambient <= -20 degC -> clear (valley between the two modes, see week-9 doc)


def read_cloudsensor(year: int) -> pd.DataFrame:
    p = LULIN_DIR / "cloudsensor" / f"{year}_Lulin_cloudsensor.txt"
    rows, bad = [], 0
    with open(p, encoding="latin-1") as f:
        for ln in f:
            a = ln.split()
            if len(a) < 10 or not a[0].startswith("20"):
                continue
            try:
                rows.append((a[0] + " " + a[1], float(a[3]), float(a[4]), float(a[5]), a[8], a[9]))
            except ValueError:
                bad += 1
    d = pd.DataFrame(rows, columns=["time", "sky", "amb", "sensor", "f1", "f2"])
    d["time"] = pd.to_datetime(d["time"], errors="coerce")
    d = d.dropna(subset=["time"]).drop_duplicates("time").set_index("time").sort_index()
    ok = d["f1"].str.fullmatch(r"[01]{4}") & d["f2"].str.fullmatch(r"[01]{4}")
    d = d[ok & d["sky"].between(-80, 40) & d["amb"].between(-30, 40)].copy()
    d["wet"] = d["f2"].str[3] == "1"
    d.attrs["bad_lines"] = bad
    return d[["sky", "amb", "sensor", "wet", "f1", "f2"]]


def _parse_time(date: pd.Series, time: pd.Series) -> pd.Series:
    t = time.str.strip()
    ampm = t.str[-1].isin(["a", "p"])
    out = pd.Series(pd.NaT, index=t.index, dtype="datetime64[ns]")
    if (~ampm).any():
        out[~ampm] = pd.to_datetime(date[~ampm] + " " + t[~ampm], format="%y/%m/%d %H:%M", errors="coerce")
    if ampm.any():
        s = date[ampm] + " " + t[ampm].str[:-1].str.strip() + t[ampm].str[-1].map({"a": " AM", "p": " PM"})
        out[ampm] = pd.to_datetime(s, format="%y/%m/%d %I:%M %p", errors="coerce")
    return out


def weather_file(year: int) -> pathlib.Path:
    hits = sorted((LULIN_DIR / "weather").glob(f"{year}*.txt"))
    if not hits:
        raise FileNotFoundError(year)
    return hits[0]


def read_weather(year: int) -> pd.DataFrame:
    d = pd.read_csv(weather_file(year), sep="\t", skiprows=2, header=None, usecols=[0, 1, 2, 5, 6, 7, 15, 16],
                    names=["date", "time", "t_air", "rh", "td_davis", "wind", "bar", "rain"], dtype=str,
                    encoding="latin-1", na_values=["---", "------"], on_bad_lines="skip")
    d["ts"] = _parse_time(d["date"], d["time"])
    d = d.dropna(subset=["ts"])
    for c in ("t_air", "rh", "td_davis", "wind", "bar", "rain"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.drop_duplicates("ts").set_index("ts").sort_index()
    d.loc[~d["t_air"].between(-30, 40), "t_air"] = np.nan
    d.loc[~d["rh"].between(1, 100), "rh"] = np.nan
    return d[["t_air", "rh", "td_davis", "wind", "bar", "rain"]]


def weather_hourly(w: pd.DataFrame) -> pd.DataFrame:
    """Hour-ending: T/RH = mean of the last 10 minutes before the hour; rain = sum over the hour."""
    label = w.index.ceil("h")
    last10 = (w.index.minute == 0) | (w.index.minute >= 51)
    inst = w[last10].groupby(label[last10])[["t_air", "rh", "td_davis", "wind"]].mean()
    inst["n_min_inst"] = w[last10].groupby(label[last10])["t_air"].count()
    hour = pd.DataFrame({"precip": w["rain"].groupby(label).sum(min_count=45),
                         "n_min": w["t_air"].groupby(label).count()})
    out = inst.join(hour, how="outer")
    out.loc[out["n_min_inst"] < 5, ["t_air", "rh", "td_davis", "wind"]] = np.nan
    return out


def cloud_hourly(c: pd.DataFrame, clear_max=CLEAR_MAX_SKY) -> pd.DataFrame:
    """Samples within +-25 min of the hour (normally 5). sky_med = median sky-minus-ambient."""
    label = (c.index + pd.Timedelta(minutes=30)).floor("h")
    near = (c.index - label).total_seconds().__abs__() <= 25 * 60
    g = c[near].groupby(label[near])
    out = pd.DataFrame({"sky_med": g["sky"].median(), "sky_min": g["sky"].min(), "sky_max": g["sky"].max(),
                        "n_sky": g["sky"].count(), "wet_any": g["wet"].any(), "amb_cs": g["amb"].mean()})
    out = out[out["n_sky"] >= 3]
    out["clear"] = (out["sky_med"] <= clear_max) & ~out["wet_any"]
    return out


def add_derived(h: pd.DataFrame) -> pd.DataFrame:
    h = h.copy()
    h["td_magnus"] = magnus_dewpoint(h["t_air"], h["rh"]).round(2)
    h["dpd"] = (h["t_air"] - h["td_magnus"]).round(2)
    s = h["precip"].rolling(3, min_periods=3).sum()
    h["rain_3h"] = s
    h["rain_3h_known"] = s.notna()
    return h
