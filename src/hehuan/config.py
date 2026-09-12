# -*- coding: utf-8 -*-
"""Project paths, station table and analysis defaults.

CACHE_DIR (raw CODiS JSON, ephemeris) deliberately lives OUTSIDE the repo / OneDrive folder:
    %LOCALAPPDATA%\\hehuan_cache   (override with env HEHUAN_CACHE_DIR)
Everything derived from it is written as CSV under data/ and is reproducible from the cache.
"""
import os
import pathlib

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config"
DATA = ROOT / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
RESULTS = ROOT / "results"
LOGS = ROOT / "logs"

CACHE_DIR = pathlib.Path(os.environ.get("HEHUAN_CACHE_DIR")
                         or pathlib.Path(os.environ.get("LOCALAPPDATA", ROOT)) / "hehuan_cache")
CODIS_CACHE = CACHE_DIR / "codis_json"
EPHEM_DIR = CACHE_DIR / "ephem"

for _p in (LOGS, CODIS_CACHE, EPHEM_DIR, PROCESSED, RESULTS / "tables", RESULTS / "figures"):
    _p.mkdir(parents=True, exist_ok=True)

# --- analysis defaults (see docs/DECISIONS.md) ---------------------------------------
NIGHT_HOURS = [20, 21, 22, 23, 0, 1, 2, 3, 4]   # local standard time (UTC+8), 9 hourly points
CLEAR_MAX_CLOUD = 2        # satellite cloud amount (0-10) <= 2  -> hour is "clear"
MIN_VALID_HOURS = 6        # a night needs >= 6 valid hours to be labelled
MIN_CLEAR_RUN = 3          # definition A: >= 3 consecutive clear hours
SENTINEL_MAX = -90.0       # any numeric value <= -90 is a CODiS missing-value code -> NaN
FETCH_END = "2026-08"      # last calendar month to fetch (inclusive)


def stations() -> pd.DataFrame:
    df = pd.read_csv(CONFIG / "stations.csv", dtype=str, encoding="utf-8-sig")
    for c in ("lat", "lon", "alt_m"):
        df[c] = df[c].astype(float)
    df["priority"] = df["priority"].astype(int)
    return df


def station(stn_id: str) -> pd.Series:
    df = stations()
    row = df[df.stn_id == stn_id]
    if row.empty:
        raise KeyError(stn_id)
    return row.iloc[0]
