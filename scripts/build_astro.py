# -*- coding: utf-8 -*-
"""Build per-night astronomy tables (2008-2027) for Hehuanshan and Taipei with ephem,
then spot-check 30 random nights against skyfield and write the max differences to results/tables."""
import sys
import pathlib
import random

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hehuan import config as C                       # noqa: E402
from hehuan.astro import astro_table, night_skyfield  # noqa: E402

SITES = {"hehuan": "C0H9C0", "taipei": "466920"}


def main():
    out = C.PROCESSED / "astro"
    out.mkdir(parents=True, exist_ok=True)
    checks = []
    for name, stn_id in SITES.items():
        s = C.station(stn_id)
        df = astro_table(s.lat, s.lon, s.alt_m)
        df.to_csv(out / f"{name}_nights_astro_2008_2027.csv", index=False)
        print(name, len(df), "nights;", df[["night_hours", "dark_hours"]].describe().loc[["min", "mean", "max"]].round(2).to_dict())
        rng = random.Random(42)
        for i in rng.sample(range(len(df)), 30):
            r = df.iloc[i]
            k = night_skyfield(r.night.date(), s.lat, s.lon, s.alt_m, C.EPHEM_DIR)
            checks.append(dict(site=name, night=r.night.date(),
                               d_sunset_min=(r.sunset - k["sunset"]).total_seconds() / 60,
                               d_dusk_min=(r.astro_dusk - k["astro_dusk"]).total_seconds() / 60,
                               d_dawn_min=(r.astro_dawn - k["astro_dawn"]).total_seconds() / 60,
                               d_dark_h=r.dark_hours - k["dark_hours"],
                               d_illum=r.moon_illum - k["moon_illum"]))
    ck = pd.DataFrame(checks)
    ck.to_csv(C.RESULTS / "tables" / "astro_ephem_vs_skyfield.csv", index=False)
    print("ephem vs skyfield, max |diff|:", ck.drop(columns=["site", "night"]).abs().max().round(3).to_dict())


if __name__ == "__main__":
    main()
