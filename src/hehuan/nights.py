"""Scout D helper: night-window aggregation + Open-Meteo ERA5 fetch (no account needed).

Conventions (decided in the methodology checklist):
- Night window = 20:00..04:00 LST (9 hourly points). night_date = date of the evening.
- Hourly 'clear' = cloud (0-10 scale) <= CLEAR_MAX (default 2).
- Definition A (primary): night observable if >=3 consecutive clear hours AND >=6 valid hours.
- Definition B (strict):  night observable if >=2/3 of valid hours clear (and >=6 valid hours).
- Definition C (sensitivity): mean cloud over window <= 3.
"""
import numpy as np
import pandas as pd

NIGHT_HOURS = [20, 21, 22, 23, 0, 1, 2, 3, 4]
CLEAR_MAX = 2
MIN_VALID = 6

def night_date(ts: pd.Series) -> pd.Series:
    """Assign each timestamp to the evening date of its night (20-23 -> same day, 00-04 -> previous day)."""
    return (ts - pd.Timedelta(hours=12)).dt.normalize()

def longest_run(bools: np.ndarray) -> int:
    best = cur = 0
    for b in bools:
        cur = cur + 1 if b else 0
        best = max(best, cur)
    return best

def label_nights(df: pd.DataFrame, time_col="time", cloud_col="cloud",
                 clear_max=CLEAR_MAX, min_valid=MIN_VALID, min_run=3, frac_b=2/3, mean_c=3.0) -> pd.DataFrame:
    """df: hourly rows with a local-time timestamp and a 0-10 cloud value (NaN allowed).
    Returns one row per night with n_valid, n_clear, longest_clear_run, def_A, def_B, def_C (NaN if too few valid hours)."""
    d = df[[time_col, cloud_col]].copy()
    d[time_col] = pd.to_datetime(d[time_col])
    d = d[d[time_col].dt.hour.isin(NIGHT_HOURS)]
    d["night"] = night_date(d[time_col])
    d = d.sort_values(time_col)
    out = []
    for night, g in d.groupby("night"):
        c = g[cloud_col].to_numpy(dtype=float)
        valid = ~np.isnan(c)
        n_valid = int(valid.sum())
        clear = (c <= clear_max) & valid          # missing hour counts as NOT clear (breaks a run)
        row = dict(night=night, n_valid=n_valid, n_clear=int(clear.sum()),
                   longest_clear_run=longest_run(clear), mean_cloud=np.nanmean(c) if n_valid else np.nan)
        if n_valid < min_valid:
            row.update(def_A=np.nan, def_B=np.nan, def_C=np.nan)
        else:
            row.update(def_A=float(row["longest_clear_run"] >= min_run),
                       def_B=float(row["n_clear"] / n_valid >= frac_b),
                       def_C=float(row["mean_cloud"] <= mean_c))
        out.append(row)
    return pd.DataFrame(out)

def fetch_open_meteo_era5(lat, lon, start, end, model="era5", timezone="Asia/Taipei"):
    """Hourly ERA5 cloud cover (%, 0-100) via Open-Meteo archive API. No API key for non-commercial use.
    Returns DataFrame with local-time 'time' and cloud_cover, cloud_cover_low/mid/high, plus grid-point metadata.
    Fetch one calendar year per call and sleep >=1 s between calls."""
    import requests
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = dict(latitude=lat, longitude=lon, start_date=start, end_date=end,
                  hourly="cloud_cover,cloud_cover_low,cloud_cover_mid,cloud_cover_high",
                  models=model, timezone=timezone)
    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()
    j = r.json()
    df = pd.DataFrame(j["hourly"])
    df["time"] = pd.to_datetime(df["time"])
    df.attrs.update(grid_lat=j["latitude"], grid_lon=j["longitude"], grid_elev_dem=j.get("elevation"))
    return df

if __name__ == "__main__":
    # self-test with synthetic data
    t = pd.date_range("2024-01-01 00:00", "2024-01-05 23:00", freq="h")
    rng = np.random.default_rng(0)
    cloud = rng.integers(0, 11, size=len(t)).astype(float)
    cloud[(t.hour >= 20) & (t.day == 2)] = 0          # night of Jan 2 evening: clear 20-23
    cloud[(t.hour <= 4) & (t.day == 3)] = 0           # ... and 00-04 of Jan 3 -> whole night clear
    cloud[(t.hour <= 4) & (t.day == 4)] = np.nan      # night of Jan 3: 5 missing -> only 4 valid -> NaN label
    res = label_nights(pd.DataFrame({"time": t, "cloud": cloud}))
    print(res.to_string())
    assert res.loc[res.night == "2024-01-02", "def_A"].item() == 1.0
    assert res.loc[res.night == "2024-01-02", "def_B"].item() == 1.0
    assert np.isnan(res.loc[res.night == "2024-01-03", "def_A"].item())
    print("self-test OK")
