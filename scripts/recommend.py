# -*- coding: utf-8 -*-
"""Date recommendation for a stargazing trip.

    python scripts/recommend.py --start 2026-10-01 --end 2026-12-31 [--site hehuan] [--top 15] [--min-dark 3]

score = P_clear(half-month climatology, def_A)  x  dark_frac(moonless astronomical-night share)  x  holiday weight
holiday weight: 1.0 if the NEXT day is a holiday/weekend (Fri, Sat, day before a public holiday), else --weekday-weight.
Output: a ranked table (markdown + CSV under results/recommend/), one row per night with every component.
"""
import sys
import argparse
import pathlib

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hehuan import config as C   # noqa: E402

SITES = {"hehuan": ("c0h9c0", "hehuan"), "taipei": ("466920", "taipei")}


def load_components(site: str):
    tag, astro_name = SITES[site]
    prob = pd.read_csv(C.RESULTS / "tables" / f"{tag}_halfmonth_prob_def_A.csv", index_col=0)
    astro = pd.read_csv(C.PROCESSED / "astro" / f"{astro_name}_nights_astro_2008_2027.csv", parse_dates=["night"]).set_index("night")
    cal = pd.read_csv(C.PROCESSED / "calendar" / "tw_calendar.csv", parse_dates=["date"]).set_index("date")
    return prob, astro, cal


def recommend(start, end, site="hehuan", min_dark=3.0, weekday_weight=0.6, top=15):
    prob, astro, cal = load_components(site)
    nights = pd.date_range(start, end, freq="D")
    rows = []
    for d in nights:
        half = f"{d.month:02d}{'a' if d.day <= 15 else 'b'}"
        p = prob.loc[half]
        a = astro.loc[d]
        c = cal.loc[d] if d in cal.index else None
        next_holiday = bool(c["next_is_holiday"]) if c is not None else d.weekday() in (4, 5)
        w = 1.0 if next_holiday else weekday_weight
        score = float(p["p"]) * float(a["dark_frac"]) * w
        rows.append(dict(night=d.date(), weekday="一二三四五六日"[d.weekday()], next_day_off=next_holiday,
                         p_clear=round(float(p["p"]), 3), p_ci=f"{p['ci_lo']:.2f}-{p['ci_hi']:.2f}",
                         moon_illum=round(float(a["moon_illum"]), 2), dark_hours=float(a["dark_hours"]),
                         dark_frac=round(float(a["dark_frac"]), 2), astro_dusk=str(a["astro_dusk"])[11:16],
                         moonrise=str(a["moonrise"])[11:16] if pd.notna(a["moonrise"]) else "-",
                         moonset=str(a["moonset"])[11:16] if pd.notna(a["moonset"]) else "-",
                         holiday_w=w, score=round(score, 3), note=(c["remark"] if c is not None and isinstance(c["remark"], str) else "")))
    df = pd.DataFrame(rows)
    df["eligible"] = df["dark_hours"] >= min_dark
    df = df.sort_values(["eligible", "score"], ascending=[False, False]).reset_index(drop=True)
    df.insert(0, "rank", range(1, len(df) + 1))
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True); ap.add_argument("--end", required=True)
    ap.add_argument("--site", default="hehuan", choices=sorted(SITES))
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--min-dark", type=float, default=3.0)
    ap.add_argument("--weekday-weight", type=float, default=0.6)
    a = ap.parse_args()
    df = recommend(a.start, a.end, a.site, a.min_dark, a.weekday_weight, a.top)
    out = C.RESULTS / "recommend"; out.mkdir(exist_ok=True)
    df.to_csv(out / f"recommend_{a.site}_{a.start}_{a.end}.csv", index=False, encoding="utf-8-sig")
    show = df.head(a.top)[["rank", "night", "weekday", "next_day_off", "p_clear", "p_ci", "moon_illum", "dark_hours", "moonrise", "moonset", "score", "note"]]
    md = [f"# 上山日期推薦：{a.site} {a.start} ~ {a.end}\n",
          f"分數 = 半月可觀星機率 × 無月黑暗時數比例 × 假日權重（隔天放假 1.0，否則 {a.weekday_weight}）；黑暗時數 < {a.min_dark} h 的夜排在最後。\n",
          "機率來自代理指標重建的 2008–2025 氣候統計（狀態見 results/tables/c0h9c0_rule_used.json）。\n",
          show.to_markdown(index=False)]
    (out / f"recommend_{a.site}_{a.start}_{a.end}.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
