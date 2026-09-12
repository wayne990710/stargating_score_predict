"""Official CDS route B: point time-series dataset (fast, tiny requests), needs the same account setup as
fetch_era5_cds.py (ECMWF account -> %USERPROFILE%\\.cdsapirc -> accept CC-BY licence on the dataset page).

Dataset: reanalysis-era5-single-levels-timeseries ("ERA5 hourly time-series data on single levels from 1940 to present")
  https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels-timeseries?tab=download
  * point request -> nearest 0.25deg grid point; formats csv / netcdf; 1940-01-01 .. (today - ~5 days)
  * verified via public costing endpoint 2026-09-11: 4 variables x 2008-2025 csv = cost 144 of limit 760
  * ONLY 23 variables: has total_cloud_cover, cloud_base_height, 2m_temperature, 2m_dewpoint_temperature,
    surface_pressure, total_precipitation ... but NO low/medium/high cloud cover.
    For low/mid/high use fetch_era5_cds.py (full dataset, area subset, GRIB, one request per year).
"""
import pathlib
import cdsapi

DATASET = "reanalysis-era5-single-levels-timeseries"
VARS = ["total_cloud_cover", "cloud_base_height", "2m_temperature", "2m_dewpoint_temperature",
        "surface_pressure", "total_precipitation"]
SITES = {  # verify coordinates against CODiS metadata before running
    "C0H9C0_hehuanshan": (24.1434, 121.2725),
    "467550_yushan":     (23.4875, 120.9594),
    "466920_taipei":     (25.0377, 121.5148),
    "466910_anbu":       (25.1826, 121.5297),
}
OUT = pathlib.Path("data/era5_cds_timeseries"); OUT.mkdir(parents=True, exist_ok=True)

client = cdsapi.Client()
for name, (lat, lon) in SITES.items():
    target = OUT / f"era5_ts_{name}.zip"   # CDS delivers csv/netcdf inside a zip (even with .nc/.csv names)
    if target.exists():
        print("skip", target); continue
    req = {
        "variable": VARS,
        "location": {"longitude": lon, "latitude": lat},
        "date": ["2008-01-01/2025-12-31"],
        "data_format": "csv",
    }
    client.retrieve(DATASET, req, str(target))
    print("done", name)
