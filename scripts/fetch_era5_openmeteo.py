"""Fetch ERA5 hourly cloud/humidity series from Open-Meteo Historical Weather API (no account needed).

Verified 2026-09-11:
  * one request can cover 2008-01-01..2025-12-31 (157,800 hourly rows, ~5-8 MB, ~10 s);
  * BUT rate limiting counts weight, not HTTP calls: >2 weeks per location counts fractionally
    (18 years ~ 470 call-units per request). Two 18-year requests back-to-back triggered HTTP 429
    (free tier: 600 calls/min, 5,000/h, 10,000/day). So: sleep ~60 s between 18-year requests,
    or split per year. Total budget for 5 sites x 18 years x <=10 vars ~ 2,350 call-units -> fits one day.
  * Always pass models=era5 -- the default best_match switches from ERA5 to ECMWF IFS 9 km
    on 2016-12-31, making the series inhomogeneous.

Usage:  python fetch_era5_openmeteo.py [out_dir]
Output: one CSV per site: era5_openmeteo_<site>.csv  (time = Asia/Taipei local, ISO8601)
Licence: Open-Meteo data CC-BY 4.0; ERA5 (C) Copernicus/ECMWF. Free tier: non-commercial use only.
"""
import sys, time, json, pathlib
import requests
import pandas as pd

API = "https://archive-api.open-meteo.com/v1/archive"
HOURLY = ["cloud_cover", "cloud_cover_low", "cloud_cover_mid", "cloud_cover_high",
          "relative_humidity_2m", "temperature_2m", "dew_point_2m", "precipitation", "surface_pressure"]
START, END = "2008-01-01", "2025-12-31"

# Station coordinates: C0H9C0 given by project; others approximate -- verify against CODiS station metadata.
# NOTE: C0H9C0, C0H990, C0I530, C0I540, C0T790 all fall in the same ERA5 0.25deg cell (24.25N, 121.25E),
# so ERA5 gives ONE cloud series for the whole Hehuanshan cluster.
SITES = {
    "C0H9C0_hehuanshan": (24.1434, 121.2725),
    "467550_yushan":     (23.4875, 120.9594),
    "466920_taipei":     (25.0377, 121.5148),
    "466910_anbu":       (25.1826, 121.5297),
    "C0H990_kunyang":    (24.1264, 121.2837),
}


def fetch(lat, lon, start=START, end=END, models="era5", retries=5):
    p = dict(latitude=lat, longitude=lon, start_date=start, end_date=end,
             hourly=",".join(HOURLY), timezone="Asia/Taipei", models=models)
    for attempt in range(retries):
        r = requests.get(API, params=p, timeout=300)
        if r.status_code == 429:
            wait = 65
            print(f"  429 rate-limited ({r.text[:120]!r}); sleeping {wait}s")
            time.sleep(wait)
            continue
        r.raise_for_status()
        j = r.json()
        if j.get("error"):
            raise RuntimeError(j)
        df = pd.DataFrame(j["hourly"])
        meta = {k: j[k] for k in ("latitude", "longitude", "elevation", "utc_offset_seconds")}
        return df, meta
    raise RuntimeError("gave up after repeated 429")


if __name__ == "__main__":
    out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out.mkdir(parents=True, exist_ok=True)
    meta_path = out / "era5_openmeteo_meta.json"
    metas = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    for name, (lat, lon) in SITES.items():
        target = out / f"era5_openmeteo_{name}.csv"
        if target.exists():
            print("skip existing", target.name); continue
        df, meta = fetch(lat, lon)
        df.to_csv(target, index=False)
        metas[name] = dict(requested=[lat, lon], **meta, rows=len(df))
        meta_path.write_text(json.dumps(metas, indent=1))
        print(name, meta, len(df), "rows")
        time.sleep(60)  # one 18-year request ~ 470 call-units; stay under 600/min
