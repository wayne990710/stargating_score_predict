# -*- coding: utf-8 -*-
"""Batch downloader for CODiS hourly observations: one station x one calendar month per request.

    python scripts/fetch_codis.py --stations 467550 C0H9C0 --from 2023-01 --to 2025-12
    python scripts/fetch_codis.py --plan A          # predefined batches (see PLANS below)
    python scripts/fetch_codis.py --plan A --dry-run

Rules (verified 2026-09-11/12 against the live API, see docs/PLAN_night1.md):
  * report_date accepts up to ~32 days; 45+ days -> body code 400. So: one calendar month per call.
  * success  == HTTP 200 and body["code"] == 200 and metadata.count >= expected_rows * 0.9
  * body code 400 (invalid time range)  -> record, do NOT retry
  * 5xx / timeout / bad JSON            -> exponential back-off, up to 3 retries
  * min 1.2 s between requests, never parallel
  * raw JSON gzip-written to CACHE_DIR/codis_json/<stn>/<stn>_<YYYY-MM>.json.gz (outside OneDrive)
  * manifest (data/raw/codis_manifest.csv) has one row per (stn, month): status, rows, expected, elapsed
  * a month already 'ok' in the cache is skipped -> the script is resumable
"""
import argparse
import calendar
import datetime as dt
import gzip
import json
import sys
import time
import pathlib

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hehuan import config as C                      # noqa: E402
from hehuan.codis_client import CodisClient         # noqa: E402

MANIFEST = C.RAW / "codis_manifest.csv"
LOG = C.LOGS / "fetch_codis.log"

# predefined batches: (stn_id, from_month, to_month); None = station fetch_start / config FETCH_END
PLANS = {
    "A": [("467550", "2023-01", "2025-12"), ("467550", "2015-01", "2022-12"), ("C0H9C0", None, "2025-12")],
    "B": [("467550", "2008-01", "2014-12"), ("466920", "2023-01", "2025-12"), ("466910", "2023-01", "2025-12"),
          ("467530", "2023-01", "2025-12"), ("C0H990", None, "2025-12")],
    "C": [(s, "2026-01", None) for s in ("467550", "C0H9C0", "466920", "466910", "467530", "C0H990")],
    "D": [("C0T790", None, None), ("C0I530", None, None), ("C0I540", None, None)],
    # manned stations' manual night cloud (05/20/21 LST) is the usable truth -> extend Alishan/Anbu/Taipei backwards
    "E": [("467530", "2008-01", "2022-12"), ("466920", "2008-01", "2022-12"), ("466910", "2008-01", "2022-12")],
}


def month_range(a: str, b: str):
    y, m = map(int, a.split("-"))
    y2, m2 = map(int, b.split("-"))
    while (y, m) <= (y2, m2):
        yield f"{y:04d}-{m:02d}"
        m += 1
        if m == 13:
            y, m = y + 1, 1


def expected_rows(stn: pd.Series, month: str) -> int:
    y, m = map(int, month.split("-"))
    first = dt.date(y, m, 1)
    last = dt.date(y, m, calendar.monthrange(y, m)[1])
    start = dt.date.fromisoformat(stn.station_start) if stn.station_start else first
    if stn.station_end:
        last = min(last, dt.date.fromisoformat(stn.station_end))
    first = max(first, start)
    ndays = (last - first).days + 1
    return max(ndays, 0) * 24


def log(msg: str):
    line = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_manifest() -> pd.DataFrame:
    if MANIFEST.exists():
        return pd.read_csv(MANIFEST, dtype={"stn_id": str, "month": str})
    return pd.DataFrame(columns=["stn_id", "month", "status", "http", "code", "rows", "expected",
                                 "elapsed_s", "bytes", "fetched_at", "note"])


def save_manifest(df: pd.DataFrame):
    df = df.drop_duplicates(["stn_id", "month"], keep="last").sort_values(["stn_id", "month"])
    df.to_csv(MANIFEST, index=False)


def cache_path(stn_id: str, month: str) -> pathlib.Path:
    d = C.CODIS_CACHE / stn_id
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{stn_id}_{month}.json.gz"


def already_ok(stn_id: str, month: str, exp: int) -> bool:
    p = cache_path(stn_id, month)
    if not p.exists():
        return False
    try:
        with gzip.open(p, "rt", encoding="utf-8") as f:
            js = json.load(f)
        return js.get("code") == 200 and js.get("metadata", {}).get("count", 0) >= exp * 0.9
    except Exception:
        return False


def fetch_month(client: CodisClient, stn: pd.Series, month: str) -> dict:
    y, m = map(int, month.split("-"))
    first = dt.date(y, m, 1)
    last = dt.date(y, m, calendar.monthrange(y, m)[1])
    exp = expected_rows(stn, month)
    rec = dict(stn_id=stn.stn_id, month=month, expected=exp, note="")
    if exp == 0:
        rec.update(status="skip_before_start", http=None, code=None, rows=0, elapsed_s=0, bytes=0,
                   fetched_at=dt.datetime.now().isoformat(timespec="seconds"))
        return rec
    delay = 5
    for attempt in range(4):
        try:
            js = client.fetch_hourly(stn.stn_id, first.isoformat(), last.isoformat(), stn_type=stn.stn_type)
        except Exception as e:                      # network / timeout
            rec["note"] = f"{type(e).__name__}: {e}"[:200]
            log(f"  {stn.stn_id} {month} attempt {attempt+1} error {rec['note']}")
            time.sleep(delay); delay *= 3
            continue
        req = js.get("_request", {})
        http, code = req.get("http_status"), js.get("code")
        count = js.get("metadata", {}).get("count", 0) or 0
        rec.update(http=http, code=code, rows=count, elapsed_s=req.get("elapsed_s"),
                   bytes=req.get("bytes"), fetched_at=req.get("fetched_at"))
        if http == 200 and code == 200 and count >= exp * 0.9:
            rec["status"] = "ok"
        elif http == 200 and code == 200:
            rec["status"] = "partial"                  # keep it, but flag
        elif code == 400:
            rec["status"] = "bad_range"; rec["note"] = str(js.get("message", ""))[:200]
        elif http and 500 <= http < 600 or "_text" in js:
            rec["status"] = "server_error"
            time.sleep(delay); delay *= 3
            continue
        else:
            rec["status"] = f"code_{code}"; rec["note"] = str(js.get("message", ""))[:200]
        with gzip.open(cache_path(stn.stn_id, month), "wt", encoding="utf-8") as f:
            json.dump(js, f, ensure_ascii=False)
        return rec
    rec.setdefault("status", "failed")
    return rec


def build_queue(args) -> list:
    st = C.stations().set_index("stn_id", drop=False)
    items = []
    if args.plan:
        for stn_id, a, b in PLANS[args.plan]:
            s = st.loc[stn_id]
            a = a or s.fetch_start
            b = b or C.FETCH_END
            items += [(stn_id, mo) for mo in month_range(a, b)]
    else:
        for stn_id in args.stations:
            s = st.loc[stn_id]
            a = getattr(args, "from") or s.fetch_start
            b = args.to or C.FETCH_END
            items += [(stn_id, mo) for mo in month_range(a, b)]
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", choices=sorted(PLANS))
    ap.add_argument("--stations", nargs="*", default=[])
    ap.add_argument("--from", dest="from", default=None, help="YYYY-MM")
    ap.add_argument("--to", default=None, help="YYYY-MM")
    ap.add_argument("--min-interval", type=float, default=1.2)
    ap.add_argument("--max-requests", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.min_interval < 1.0:
        sys.exit("min-interval must be >= 1.0 s (be polite to the unofficial API)")

    st = C.stations().set_index("stn_id", drop=False)
    queue = build_queue(args)
    todo = [(s, mo) for s, mo in queue if not already_ok(s, mo, expected_rows(st.loc[s], mo))]
    log(f"plan={args.plan} stations={sorted({s for s,_ in queue})} queued={len(queue)} todo={len(todo)}")
    if args.dry_run:
        for s, mo in todo[:10]:
            print(" ", s, mo, expected_rows(st.loc[s], mo))
        print("  ..." if len(todo) > 10 else "")
        return

    client = CodisClient(min_interval=args.min_interval, raw_dir=None, max_requests=args.max_requests)
    manifest = load_manifest()
    t0 = time.monotonic()
    n_ok = 0
    for i, (s, mo) in enumerate(todo, 1):
        rec = fetch_month(client, st.loc[s], mo)
        manifest = pd.DataFrame([rec]) if manifest.empty else pd.concat([manifest, pd.DataFrame([rec])], ignore_index=True)
        n_ok += rec["status"] == "ok"
        if i % 10 == 0 or rec["status"] != "ok":
            log(f"[{i}/{len(todo)}] {s} {mo} {rec['status']} rows={rec.get('rows')}/{rec['expected']} "
                f"{rec.get('elapsed_s')}s  ok={n_ok}  elapsed={time.monotonic()-t0:.0f}s")
        if i % 10 == 0:
            save_manifest(manifest)
    save_manifest(manifest)
    log(f"done: {n_ok}/{len(todo)} ok, {client.n_requests} requests, {time.monotonic()-t0:.0f}s")


if __name__ == "__main__":
    main()
