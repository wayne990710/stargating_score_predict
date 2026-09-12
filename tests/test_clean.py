import sys
import pathlib

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from hehuan import clean            # noqa: E402
from hehuan.nights import label_nights   # noqa: E402


def _raw(n_days=2):
    rows = []
    for d in range(1, n_days + 1):
        for h in range(1, 25):
            label = f"2024-01-{d:02d}T{h:02d}:00:00" if h < 24 else f"2024-01-{d:02d}T23:59:00"
            rows.append({"DataTime": label, "AirTemperature.Instantaneous": 10.0, "RelativeHumidity.Instantaneous": 80,
                         "Precipitation.Accumulation": 0.0, "TotalCloudAmount.SatRetrieved": 1})
    return pd.DataFrame(rows)


def test_2359_becomes_next_day_midnight():
    df, _ = clean.standardize(_raw(), "X")
    assert df.index[23] == pd.Timestamp("2024-01-02 00:00")
    assert len(df) == 48 and df.index.is_monotonic_increasing


def test_sentinels_become_nan_and_are_counted():
    raw = _raw()
    raw.loc[3, "RelativeHumidity.Instantaneous"] = -9997
    raw.loc[4, "AirTemperature.Instantaneous"] = -9999.7
    raw.loc[5, "Precipitation.Accumulation"] = -999.6
    df, s = clean.standardize(raw, "X")
    assert df["rh"].isna().sum() == 1 and df["t_air"].isna().sum() == 1
    assert set(s.value) == {-9997, -9999.7, -999.6}


def test_rain_window_unknown_is_not_zero():
    raw = _raw()
    raw.loc[5, "Precipitation.Accumulation"] = -999.6      # missing hour 6
    df, _ = clean.standardize(raw, "X")
    assert np.isnan(df["rain_3h"].iloc[5]) and np.isnan(df["rain_3h"].iloc[7])
    assert df["rain_3h"].iloc[8] == 0.0 and bool(df["rain_3h_known"].iloc[8])


def test_magnus_dewpoint():
    td = clean.magnus_dewpoint(pd.Series([20.0, -5.0]), pd.Series([50.0, 100.0]))
    assert abs(td.iloc[0] - 9.3) < 0.3
    assert abs(td.iloc[1] - (-5.0)) < 0.05


def test_night_labels_definition_a():
    t = pd.date_range("2024-01-01 00:00", "2024-01-05 23:00", freq="h")
    cloud = pd.Series(10.0, index=t)
    cloud[(t >= "2024-01-02 20:00") & (t <= "2024-01-02 23:00")] = 0      # 4 consecutive clear hours
    res = label_nights(pd.DataFrame({"time": t, "cloud": cloud.values}))
    row = res.set_index("night").loc["2024-01-02"]
    assert row.def_A == 1.0 and row.def_B == 0.0 and row.longest_clear_run == 4
