"""Week-8 recommendation tool. Expected values come from sources independent of the code under test:
moon times from the USNO API (queried 2026-11-18), day-off flags from the raw DGPA calendar CSV."""
import sys
import pathlib

import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import recommend as R   # noqa: E402


def minutes(hhmm):
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m


def row(df, date):
    return df[df["日期"] == date].iloc[0]


@pytest.mark.parametrize("site", ["hehuan", "taipei"])
def test_both_sites_rank_every_night(site):
    df, meta = R.recommend("2027-01-01", "2027-01-31", site)
    assert len(df) == 31
    assert list(df["排名"]) == list(range(1, 32))
    assert df["日期"].is_unique


# USNO: Taipei 2026-10-09 moonrise 04:16; Hehuan 2027-04-03 moonrise 03:20; Hehuan 2027-04-09 moonset 20:38
@pytest.mark.parametrize("site,night,col,usno", [
    ("taipei", "2026-10-08", "月出", "04:16"),
    ("hehuan", "2027-04-02", "月出", "03:20"),
    ("hehuan", "2027-04-09", "月沒", "20:38"),
])
def test_moon_times_match_usno(site, night, col, usno):
    df, _ = R.recommend(night, night, site)
    assert abs(minutes(row(df, night)[col]) - minutes(usno)) <= 3


def _raw_dgpa(year_roc, year):
    p = ROOT / "data" / "raw" / "holidays" / f"cal_{year_roc}_{year}.csv"
    for enc in ("utf-8-sig", "cp950"):
        try:
            d = pd.read_csv(p, encoding=enc, dtype=str)
            break
        except UnicodeDecodeError:
            continue
    d.columns = [c.strip() for c in d.columns]
    return dict(zip(d["西元日期"].str.strip(), d["是否放假"].str.strip() == "2"))


def test_day_off_flags_match_raw_dgpa_october_2026():
    raw = _raw_dgpa(115, 2026)
    df, _ = R.recommend("2026-10-01", "2026-10-30", "taipei")
    for _, r in df.iterrows():
        nxt = (pd.Timestamp(r["日期"]) + pd.Timedelta(days=1)).strftime("%Y%m%d")
        assert (r["隔天放假"] == "是") == raw[nxt], r["日期"]


def test_beyond_calendar_falls_back_to_weekends():
    df, _ = R.recommend("2028-01-01", "2028-01-03", "hehuan")
    assert row(df, "2028-01-01")["隔天放假"] == "是"     # next day Sunday
    assert row(df, "2028-01-03")["隔天放假"] == "否"     # next day Tuesday
    assert row(df, "2028-01-01")["日曆來源"] == "僅週末"


def test_only_days_off_filter():
    df, _ = R.recommend("2027-03-01", "2027-03-31", "hehuan", only_days_off=True)
    assert len(df) > 0 and (df["隔天放假"] == "是").all()


def test_evening_window_counts_dark_after_moonset():
    df, _ = R.recommend("2027-04-09", "2027-04-09", "hehuan", window="evening")
    r = row(df, "2027-04-09")
    expected = (24 * 60 - minutes("20:38")) / 60          # moon sets 20:38 (USNO), dark until midnight
    assert abs(r["無月黑暗h"] - expected) < 0.1


def test_score_is_probability_times_dark_fraction_and_sorted():
    df, _ = R.recommend("2027-04-01", "2027-04-30", "hehuan")
    assert ((df["分數"] - df["晴天機率"] * df["無月比例"]).abs() < 0.006).all()
    ok = df[df["黑暗足夠"]]
    assert ok["分數"].is_monotonic_decreasing


def test_half_month_boundary_and_leap_day():
    df, _ = R.recommend("2028-02-14", "2028-02-29", "hehuan")
    prob = pd.read_csv(ROOT / "results" / "tables" / "c0h9c0_halfmonth_prob_evening_clear.csv", index_col=0)
    assert row(df, "2028-02-15")["晴天機率"] == round(prob.loc["02a", "p"], 3)
    assert row(df, "2028-02-16")["晴天機率"] == round(prob.loc["02b", "p"], 3)
    assert "2028-02-29" in set(df["日期"])


def test_reversed_range_is_an_error():
    with pytest.raises(ValueError):
        R.recommend("2027-02-01", "2027-01-01", "hehuan")


def test_taipei_table_uses_only_2008_2017_manual_obs():
    t = pd.read_csv(ROOT / "results" / "tables" / "466920_halfmonth_prob_evening_clear.csv", index_col=0)
    assert len(t) == 24 and t["n_years"].max() <= 10
    lab = pd.read_csv(ROOT / "data" / "processed" / "labels" / "466920_night_labels.csv", parse_dates=["night"])
    lab = lab[lab["evening_clear"].notna() & (lab["night"].dt.month == 1) & (lab["night"].dt.day <= 15)]
    clear = lab["evening_clear"].astype(str).str.lower().eq("true")
    assert abs(t.loc["01a", "p"] - clear.mean()) < 0.001


# ---- consecutive nights (--nights N) -------------------------------------------------------------
def _brute_any(stn, month, first_half, n):
    """Count n-night runs by plain loops over the label file (independent of climatology.consecutive_any)."""
    lab = pd.read_csv(ROOT / "data" / "processed" / "labels" / f"{stn}_night_labels.csv", parse_dates=["night"])
    val = {}
    for night, v in zip(lab["night"], lab["evening_clear"].astype(str).str.lower()):
        if v in ("true", "false") and night.year < 2026:
            val[night] = v == "true"
    runs = any_ = all_ = 0
    for night in val:
        if night.month != month or (night.day <= 15) != first_half:
            continue
        w = [val.get(night + pd.Timedelta(days=k)) for k in range(n)]
        if None in w:
            continue
        runs += 1; any_ += any(w); all_ += all(w)
    return any_ / runs, all_ / runs, runs


@pytest.mark.parametrize("site,stn,start,month,first_half,n", [
    ("hehuan", "C0H9C0", "2027-04-02", 4, True, 2),
    ("hehuan", "C0H9C0", "2027-01-20", 1, False, 3),
    ("taipei", "466920", "2027-04-29", 4, False, 2),
])
def test_any_clear_of_n_nights_matches_brute_force_count(site, stn, start, month, first_half, n):
    df, _ = R.recommend(start, start, site, nights=n)
    p_any, p_all, runs = _brute_any(stn, month, first_half, n)
    r = row(df, start)
    assert abs(r["至少一晚晴"] - p_any) < 0.001
    assert abs(r["每晚都晴"] - p_all) < 0.001
    assert r["歷史樣本數"] == runs


def test_stay_rows_cover_n_nights_and_score():
    df, _ = R.recommend("2027-04-01", "2027-04-10", "hehuan", nights=2)
    one, _ = R.recommend("2027-04-01", "2027-04-11", "hehuan")
    assert len(df) == 10                                   # one stay per start date, last one ends 04-11
    r = row(df, "2027-04-02")
    assert r["最後一晚"] == "2027-04-03"
    assert r["隔天放假"] == "是"                            # Sat 04-03 and Sun 04-04 both off
    assert row(df, "2027-04-01")["隔天放假"] == "否"        # Fri 04-02 is a school day
    frac = (row(one, "2027-04-02")["無月比例"] + row(one, "2027-04-03")["無月比例"]) / 2
    assert abs(r["分數"] - r["至少一晚晴"] * frac) < 0.006
    assert r["最少無月黑暗h"] == min(row(one, "2027-04-02")["無月黑暗h"], row(one, "2027-04-03")["無月黑暗h"])
    assert r["每晚都晴"] <= r["單晚晴機率"] <= r["至少一晚晴"]
    lo, hi = map(float, r["至少一晚晴95%區間"].split("–"))
    assert lo <= r["至少一晚晴"] <= hi


def test_single_night_output_unchanged_by_nights_option():
    a, _ = R.recommend("2027-04-01", "2027-04-10", "hehuan")
    b, _ = R.recommend("2027-04-01", "2027-04-10", "hehuan", nights=1)
    assert a.equals(b) and "至少一晚晴" not in a.columns


def test_nights_out_of_range_is_an_error():
    with pytest.raises(ValueError):
        R.recommend("2027-04-01", "2027-04-10", "hehuan", nights=0)
