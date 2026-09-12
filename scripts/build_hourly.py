# -*- coding: utf-8 -*-
"""cache JSON -> data/raw/codis/<stn>/*.csv.gz -> data/processed/hourly/<stn>_hourly.csv.gz + QC tables.

    python scripts/build_hourly.py                # every station with cached months
    python scripts/build_hourly.py 467550 C0H9C0  # subset
"""
import sys
import gzip
import pathlib

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hehuan import config as C          # noqa: E402
from hehuan import clean                # noqa: E402


def main(stn_ids):
    qc = C.PROCESSED / "qc"
    qc.mkdir(parents=True, exist_ok=True)
    st = C.stations().set_index("stn_id", drop=False)
    if not stn_ids:
        stn_ids = [p.name for p in sorted(C.CODIS_CACHE.iterdir()) if p.is_dir() and any(p.glob("*.json.gz"))]
    sent, cov, rhs, stuck, tcheck = [], [], [], [], []
    for stn_id in stn_ids:
        files = clean.cache_to_raw_csv(stn_id)
        raw = clean.read_raw(stn_id)
        if raw.empty:
            print(stn_id, "no data"); continue
        df, s = clean.standardize(raw, stn_id)
        stuck.append(clean.stuck_hours(df, stn_id))
        sent.append(s); cov.append(clean.coverage_by_month(df, stn_id))
        rhs.append(clean.rh_sensor_summary(df, stn_id))
        tcheck.append(clean.timestamp_check(df, st.loc[stn_id]))
        out = C.PROCESSED / "hourly" / f"{stn_id}_hourly.csv.gz"
        with gzip.open(out, "wt", encoding="utf-8", newline="") as f:
            df.to_csv(f, float_format="%.3f")
        print(f"{stn_id}: {len(files)} raw files, {len(df)} hours {df.index.min()} .. {df.index.max()}, "
              f"{s['count'].sum() if len(s) else 0} sentinel values -> {out.name}")
    for name, frames in [("sentinel_codes", sent), ("coverage_by_month", cov), ("rh_sensor_by_year", rhs),
                         ("rh_stuck_by_year", stuck), ("timestamp_check_by_month", tcheck)]:
        frames = [f for f in frames if f is not None and len(f)]
        if frames:
            new = pd.concat(frames, ignore_index=True)
            p = qc / f"{name}.csv"
            if p.exists():   # merge with stations processed earlier
                old = pd.read_csv(p)
                old = old[~old.stn_id.isin(new.stn_id.unique())]
                new = pd.concat([old, new], ignore_index=True)
            new.to_csv(p, index=False)


if __name__ == "__main__":
    main(sys.argv[1:])
