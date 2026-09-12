"""Official route: ERA5 hourly single-level cloud cover over Taiwan from the Copernicus Climate Data Store.

USER MUST DO FIRST (Claude cannot do these):
  1. Create an ECMWF account (Login/Register on https://cds.climate.copernicus.eu ; accounts are ECMWF accounts).
  2. Log in, open https://cds.climate.copernicus.eu/how-to-api , copy the two-line block shown there
     (url: https://cds.climate.copernicus.eu/api / key: <personal access token>) into
     C:\\Users\\<you>\\.cdsapirc   (Windows: %USERPROFILE%\\.cdsapirc ; create with Notepad, "Save as" name ".cdsapirc",
     file type "All files", or in PowerShell:  Set-Content -Path "$env:USERPROFILE\\.cdsapirc" -Value "url: ...","key: ...").
  3. Open https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels?tab=download , scroll to
     "Terms of use" at the bottom and accept the licence (once per dataset; required before any API download).
  4. pip install "cdsapi>=0.7.7"
Then:  python fetch_era5_cds.py  (one request per year -> data/era5_cds/era5_tw_<year>.grib)

Request cost: 4 variables x 8760 h = 35,040 fields per year (area subset does NOT reduce the field count).
CDS ERA5 hourly limit has been 120,000 fields per request (GRIB); NetCDF has a stricter limit since 2025-04.
Queue: reports in 2026 show hours per request during busy periods -- run this unattended.
Reading: pip install cfgrib xarray  ->  xr.open_dataset("era5_tw_2024.grib", engine="cfgrib")
"""
import pathlib, time
import cdsapi

DATASET = "reanalysis-era5-single-levels"
VARS = ["total_cloud_cover", "low_cloud_cover", "medium_cloud_cover", "high_cloud_cover"]
# North, West, South, East -- covers Taiwan main island (Hehuanshan 24.14N 121.27E, Yushan, Taipei, Anbu)
AREA = [25.5, 120.0, 21.5, 122.5]
YEARS = range(2008, 2026)
OUT = pathlib.Path("data/era5_cds"); OUT.mkdir(parents=True, exist_ok=True)

client = cdsapi.Client()
for y in YEARS:
    target = OUT / f"era5_tw_{y}.grib"
    if target.exists():
        print("skip", target); continue
    req = {
        "product_type": ["reanalysis"],
        "variable": VARS,
        "year": [str(y)],
        "month": [f"{m:02d}" for m in range(1, 13)],
        "day": [f"{d:02d}" for d in range(1, 32)],
        "time": [f"{h:02d}:00" for h in range(24)],
        "area": AREA,
        "data_format": "grib",
        "download_format": "unarchived",
    }
    t0 = time.time()
    client.retrieve(DATASET, req, str(target))
    print(y, "done in %.0f s" % (time.time() - t0))
