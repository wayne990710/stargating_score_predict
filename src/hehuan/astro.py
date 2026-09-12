# -*- coding: utf-8 -*-
"""Per-night astronomy table: sunset, astronomical dusk/dawn, sunrise, moonrise/moonset, illumination,
astronomical-night length and moonless dark hours.

Batch engine: ephem (fast, ~2 ms/night, matches skyfield/USNO within 1 minute; verified 2026-09-11).
Spot-check engine: skyfield (needs de421.bsp in config.EPHEM_DIR).

"Night N" = from sunset on local date N to sunrise on N+1 (Asia/Taipei, UTC+8).
"""
import datetime as dt
from zoneinfo import ZoneInfo

import ephem
import pandas as pd

TZ = ZoneInfo("Asia/Taipei")
UTC = dt.timezone.utc


def _merge(iv):
    iv = sorted(iv)
    out = []
    for a, b in iv:
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def dark_moonless_hours(dusk, dawn, moon_up):
    total = dawn - dusk
    covered = dt.timedelta(0)
    for a, b in _merge(moon_up):
        lo, hi = max(a, dusk), min(b, dawn)
        if hi > lo:
            covered += hi - lo
    return (total - covered).total_seconds() / 3600, total.total_seconds() / 3600


def night_ephem(date: dt.date, lat: float, lon: float, elev: float) -> dict:
    obs = ephem.Observer()
    obs.lat, obs.lon, obs.elevation = str(lat), str(lon), elev
    obs.pressure = 0
    sun, moon = ephem.Sun(), ephem.Moon()
    noon = dt.datetime.combine(date, dt.time(12, 0), TZ).astimezone(UTC).replace(tzinfo=None)
    obs.date = noon

    def to_dt(d):
        return ephem.to_timezone(d, UTC)

    obs.horizon = "-0:50"
    sunset = to_dt(obs.next_setting(sun))
    obs.horizon = "-18"
    dusk = to_dt(obs.next_setting(sun, use_center=True))
    dawn = to_dt(obs.next_rising(sun, use_center=True, start=dusk))
    obs.horizon = "-0:50"
    sunrise = to_dt(obs.next_rising(sun, start=dawn))

    obs.horizon = "-0:34"
    lo = ephem.Date(sunset - dt.timedelta(hours=12))
    end = ephem.Date(sunrise)
    rises, sets = [], []
    d = lo
    while True:
        r = obs.next_rising(moon, start=d)
        if r >= end:
            break
        rises.append(to_dt(r)); d = r + ephem.minute
    d = lo
    while True:
        s = obs.next_setting(moon, start=d)
        if s >= end:
            break
        sets.append(to_dt(s)); d = s + ephem.minute
    events = sorted([(t, "r") for t in rises] + [(t, "s") for t in sets])
    obs.date = lo; moon.compute(obs)
    cur = to_dt(lo) if moon.alt > 0 else None
    intervals = []
    for t, k in events:
        if k == "r" and cur is None:
            cur = t
        elif k == "s" and cur is not None:
            intervals.append((cur, t)); cur = None
    if cur is not None:
        intervals.append((cur, sunrise + dt.timedelta(hours=1)))

    obs.date = ephem.Date(dusk); moon.compute(obs)
    illum = moon.phase / 100.0
    # moon altitude at local midnight (useful: is the moon up in the middle of the night?)
    mid = dt.datetime.combine(date + dt.timedelta(days=1), dt.time(0, 0), TZ).astimezone(UTC).replace(tzinfo=None)
    obs.date = mid; moon.compute(obs)
    moon_alt_midnight = float(moon.alt) * 180 / 3.141592653589793
    dark_h, night_h = dark_moonless_hours(dusk, dawn, intervals)

    def loc(t):
        return t.astimezone(TZ).replace(tzinfo=None)

    night_moonrise = [loc(t) for t in rises if sunset <= t <= sunrise]
    night_moonset = [loc(t) for t in sets if sunset <= t <= sunrise]
    return dict(night=pd.Timestamp(date), sunset=loc(sunset), astro_dusk=loc(dusk), astro_dawn=loc(dawn),
                sunrise=loc(sunrise), moonrise=night_moonrise[0] if night_moonrise else pd.NaT,
                moonset=night_moonset[0] if night_moonset else pd.NaT,
                moon_illum=round(illum, 3), moon_alt_midnight=round(moon_alt_midnight, 1),
                night_hours=round(night_h, 2), dark_hours=round(dark_h, 2),
                dark_frac=round(dark_h / night_h, 3) if night_h else float("nan"))


def astro_table(lat, lon, elev, start="2008-01-01", end="2027-12-31") -> pd.DataFrame:
    days = pd.date_range(start, end, freq="D")
    rows = [night_ephem(d.date(), lat, lon, elev) for d in days]
    return pd.DataFrame(rows)


def night_skyfield(date: dt.date, lat, lon, elev, ephem_dir) -> dict:
    """Independent check with skyfield (JPL DE421). Returns the same keys as night_ephem (subset)."""
    from skyfield import almanac
    from skyfield.api import Loader, wgs84
    load = Loader(str(ephem_dir))
    ts = load.timescale()
    eph = load("de421.bsp")
    earth, moon = eph["earth"], eph["moon"]
    site = wgs84.latlon(lat, lon, elevation_m=elev)
    observer = earth + site
    t0 = ts.from_datetime(dt.datetime.combine(date, dt.time(0, 0), TZ))
    t1 = ts.from_datetime(dt.datetime.combine(date + dt.timedelta(days=2), dt.time(0, 0), TZ))
    f = almanac.dark_twilight_day(eph, site)
    times, events = almanac.find_discrete(t0, t1, f)
    ev = list(zip(times.utc_datetime(), events))
    noon = dt.datetime.combine(date, dt.time(12, 0), TZ)
    sunset = dusk = dawn = sunrise = None
    prev = None
    for t, e in ev:
        if prev is not None:
            if t > noon and sunset is None and prev == 4 and e == 3:
                sunset = t
            if sunset is not None and dusk is None and prev == 1 and e == 0:
                dusk = t
            if dusk is not None and dawn is None and prev == 0 and e == 1:
                dawn = t
            if dawn is not None and sunrise is None and prev == 3 and e == 4:
                sunrise = t
        prev = e

    def moon_up(t):
        alt, _, _ = observer.at(t).observe(moon).apparent().altaz()
        return alt.degrees > -0.8333
    moon_up.step_days = 0.02
    mt, me = almanac.find_discrete(t0, t1, moon_up)
    mt = list(mt.utc_datetime()); me = list(me)
    intervals, cur = [], (t0.utc_datetime() if moon_up(t0) else None)
    for t, e in zip(mt, me):
        if e and cur is None:
            cur = t
        elif not e and cur is not None:
            intervals.append((cur, t)); cur = None
    if cur is not None:
        intervals.append((cur, t1.utc_datetime()))
    illum = almanac.fraction_illuminated(eph, "moon", ts.from_datetime(dusk))
    dark_h, night_h = dark_moonless_hours(dusk, dawn, intervals)

    def loc(t):
        return t.astimezone(TZ).replace(tzinfo=None)
    return dict(sunset=loc(sunset), astro_dusk=loc(dusk), astro_dawn=loc(dawn), sunrise=loc(sunrise),
                moon_illum=round(float(illum), 3), night_hours=round(night_h, 2), dark_hours=round(dark_h, 2))
