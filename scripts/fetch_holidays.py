# -*- coding: utf-8 -*-
"""Download the DGPA government office calendar CSVs (data.gov.tw dataset 14718) for every year offered,
then build data/processed/calendar/tw_calendar.csv (one row per day: date, weekday, is_holiday, remark).

Years before 2017 are not published as CSV; for 2008-2016 only weekends are marked (is_holiday from weekday).
"""
import re
import sys
import pathlib

import pandas as pd
import requests

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hehuan import config as C          # noqa: E402
from hehuan.holidays import load_calendar   # noqa: E402

RAW = C.RAW / "holidays"
OUT = C.PROCESSED / "calendar" / "tw_calendar.csv"
API = "https://data.gov.tw/api/v2/rest/dataset/14718"


def download_all():
    js = requests.get(API, timeout=60, headers={"User-Agent": "Mozilla/5.0"}).json()
    dist = js["result"]["distribution"]
    for d in dist:
        url = d.get("resourceDownloadUrl", "")
        desc = d.get("resourceDescription", "") + d.get("resourceName", "")
        if "Google" in desc or "google" in url.lower():
            continue
        m = re.search(r"(\d{3})年", desc) or re.search(r"/(\d{3})\D", url)
        if not m:
            print("skip (no year):", desc[:60], url[:80]); continue
        roc = int(m.group(1)); year = roc + 1911
        target = RAW / f"cal_{roc}_{year}.csv"
        if target.exists():
            continue
        r = requests.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200 or len(r.content) < 1000:
            print("failed", roc, r.status_code, url[:80]); continue
        target.write_bytes(r.content)
        print("downloaded", target.name, len(r.content), "bytes")


def build():
    frames = [load_calendar(p) for p in sorted(RAW.glob("cal_*.csv")) if "google" not in p.name]
    cal = pd.concat(frames, ignore_index=True).drop_duplicates("date").sort_values("date")
    cal["source"] = "dgpa"
    first = cal.date.min()
    back = pd.DataFrame({"date": pd.date_range("2008-01-01", first - pd.Timedelta(days=1))})
    back["星期"] = back.date.dt.dayofweek.map(dict(enumerate("一二三四五六日")))
    back["is_holiday"] = back.date.dt.dayofweek >= 5
    back["remark"] = ""
    back["source"] = "weekend_only"
    cal = pd.concat([back, cal], ignore_index=True).sort_values("date")
    cal["weekday"] = cal.date.dt.dayofweek
    cal["next_is_holiday"] = cal.is_holiday.shift(-1).fillna(False).astype(bool)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    cal[["date", "weekday", "星期", "is_holiday", "next_is_holiday", "remark", "source"]].to_csv(
        OUT, index=False, encoding="utf-8-sig")
    print(OUT, len(cal), "days;", cal.groupby(cal.date.dt.year).is_holiday.sum().to_dict())


if __name__ == "__main__":
    download_all()
    build()
