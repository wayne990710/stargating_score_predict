# -*- coding: utf-8 -*-
"""Half-month and monthly evening-clear probability for Taipei (466920) from MANUAL cloud observations,
20 and 21 LST both <= 2/10, 2008-2017 (night observations stopped afterwards). Same year-block bootstrap
as Hehuanshan (src/hehuan/climatology.year_block_bootstrap).

Outputs results/tables/466920_halfmonth_prob_evening_clear.csv and 466920_monthly_prob_evening_clear.csv
"""
import sys
import pathlib

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hehuan import config as C, climatology as K   # noqa: E402


def main():
    lab = pd.read_csv(C.PROCESSED / "labels" / "466920_night_labels.csv", index_col="night", parse_dates=["night"])
    lab["evening_clear"] = lab["evening_clear"].map({True: 1.0, False: 0.0, "True": 1.0, "False": 0.0}).astype(float)
    lab = lab[lab.index < "2026-01-01"]
    T = C.RESULTS / "tables"
    for by in ("halfmonth", "month"):
        t = K.year_block_bootstrap(lab, "evening_clear", by)
        name = "halfmonth" if by == "halfmonth" else "monthly"
        t.to_csv(T / f"466920_{name}_prob_evening_clear.csv")
        print(name, len(lab.dropna(subset=["evening_clear"])), "nights,", lab.index.year.min(), "-", lab.index.year.max())
        print(t.to_string())


if __name__ == "__main__":
    main()
