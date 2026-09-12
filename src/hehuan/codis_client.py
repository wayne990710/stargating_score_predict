# -*- coding: utf-8 -*-
"""
codis_client.py - minimal, polite client for the (unofficial) CODiS station API.

    POST https://codis.cwa.gov.tw/api/station

Usage:
    from codis_client import CodisClient
    c = CodisClient(min_interval=1.2, raw_dir="raw")     # raw_dir: where to dump JSON (optional)
    js = c.fetch_hourly("466920", "2024-01-15")           # one day of hourly data (24 rows)
    js = c.fetch_hourly("466920", "2024-01-01", "2024-01-31")   # multi-day (if the server allows it)
    js = c.fetch_daily("C0H9C0", "2024-01")               # report_month -> daily stats for one month
    df = CodisClient.dts_to_frame(js)                     # flatten to a pandas DataFrame

Notes (verified 2026-09-11):
  * stn_type: 46xxxx manned stations -> "cwb"; C0xxxx automatic -> "auto_C0"; C1xxxx -> "auto_C1" (assumed)
  * the 24th hourly record of a day is labelled "YYYY-MM-DDT23:59:00" (it is the 24:00 observation)
  * every value field X has a sibling quality flag "Xf" (e.g. Instantaneous / Instantaneousf)
"""
import json
import os
import time
import datetime as _dt

import requests

API_URL = "https://codis.cwa.gov.tw/api/station"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36",
    "Referer": "https://codis.cwa.gov.tw/StationData",
    "Origin": "https://codis.cwa.gov.tw",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}


def stn_type_for(stn_id: str) -> str:
    """Infer the stn_type form value from a station ID."""
    s = stn_id.upper()
    if s[:2].isdigit():          # 46xxxx / 47xxxx manned stations
        return "cwb"
    if s.startswith("C0"):
        return "auto_C0"
    if s.startswith("C1"):
        return "auto_C1"
    raise ValueError(f"unknown station id pattern: {stn_id}")


class CodisClient:
    def __init__(self, min_interval: float = 1.2, raw_dir: str | None = None,
                 timeout: float = 60.0, max_requests: int | None = None):
        self.min_interval = min_interval
        self.raw_dir = raw_dir
        self.timeout = timeout
        self.max_requests = max_requests
        self.n_requests = 0
        self._last_t = 0.0
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        if raw_dir:
            os.makedirs(raw_dir, exist_ok=True)

    # ------------------------------------------------------------------ core
    def _throttle(self):
        wait = self.min_interval - (time.monotonic() - self._last_t)
        if wait > 0:
            time.sleep(wait)

    def post(self, stn_id: str, start: str, end: str, type_: str = "report_date",
             stn_type: str | None = None, date: str | None = None,
             tag: str | None = None, extra: dict | None = None) -> dict:
        """Raw POST. start/end are 'YYYY-MM-DDTHH:MM:SS'. Returns parsed JSON (dict)."""
        if self.max_requests is not None and self.n_requests >= self.max_requests:
            raise RuntimeError(f"request budget exhausted ({self.max_requests})")
        stn_type = stn_type or stn_type_for(stn_id)
        form = {
            "date": date if date is not None else start,
            "type": type_,
            "stn_ID": stn_id,
            "stn_type": stn_type,
            "more": "",
            "start": start,
            "end": end,
            "item": "",
        }
        if extra:
            form.update(extra)
        self._throttle()
        t0 = time.monotonic()
        r = self.session.post(API_URL, data=form, timeout=self.timeout)
        self._last_t = time.monotonic()
        self.n_requests += 1
        elapsed = self._last_t - t0
        try:
            js = r.json()
        except ValueError:
            js = {"_http_status": r.status_code, "_text": r.text[:2000]}
        js["_request"] = {"form": form, "http_status": r.status_code,
                          "elapsed_s": round(elapsed, 2), "bytes": len(r.content),
                          "fetched_at": _dt.datetime.now().isoformat(timespec="seconds")}
        if self.raw_dir:
            name = tag or f"{stn_id}_{type_}_{start[:10]}_{end[:10]}"
            with open(os.path.join(self.raw_dir, name + ".json"), "w", encoding="utf-8") as f:
                json.dump(js, f, ensure_ascii=False, indent=1)
        return js

    # ------------------------------------------------------------- wrappers
    def fetch_hourly(self, stn_id: str, day: str, end_day: str | None = None, **kw) -> dict:
        """report_date: hourly rows. day / end_day = 'YYYY-MM-DD' (inclusive)."""
        end_day = end_day or day
        return self.post(stn_id, f"{day}T00:00:00", f"{end_day}T23:59:59",
                         type_="report_date", **kw)

    def fetch_daily(self, stn_id: str, month: str, **kw) -> dict:
        """report_month: daily rows for one month. month = 'YYYY-MM'."""
        y, m = (int(x) for x in month.split("-"))
        first = _dt.date(y, m, 1)
        last = (first.replace(day=28) + _dt.timedelta(days=4)).replace(day=1) - _dt.timedelta(days=1)
        return self.post(stn_id, f"{first:%Y-%m-%d}T00:00:00", f"{last:%Y-%m-%d}T23:59:59",
                         type_="report_month", **kw)

    # -------------------------------------------------------------- helpers
    @staticmethod
    def rows(js: dict) -> list:
        """Return the list of dts records (empty list on error)."""
        try:
            return js["data"][0]["dts"]
        except (KeyError, IndexError, TypeError):
            return []

    @staticmethod
    def flatten(rec: dict) -> dict:
        """{'DataTime':..., 'AirTemperature': {'Instantaneous': 1, 'Instantaneousf': None}} ->
           {'DataTime':..., 'AirTemperature.Instantaneous': 1, 'AirTemperature.Instantaneousf': None}"""
        out = {}
        for k, v in rec.items():
            if isinstance(v, dict):
                for k2, v2 in v.items():
                    out[f"{k}.{k2}"] = v2
            else:
                out[k] = v
        return out

    @classmethod
    def dts_to_frame(cls, js: dict):
        import pandas as pd
        recs = [cls.flatten(r) for r in cls.rows(js)]
        df = pd.DataFrame(recs)
        if "DataTime" in df:
            df["DataTime"] = pd.to_datetime(df["DataTime"])
        return df
