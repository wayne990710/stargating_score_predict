# -*- coding: utf-8 -*-
"""上山／觀星日期推薦（第 8 週）。

    python scripts/recommend.py --site hehuan --start 2027-03-01 --end 2027-05-31 --only-days-off
    python scripts/recommend.py --site taipei --start 2026-10-01 --end 2026-10-31

分數 = P（該日所在半月的「傍晚 20、21 時皆晴」機率） × 活動時段中無月黑暗的比例
  - P：合歡山 = 露點差代理標籤 2011–2025（暫定）；臺北 = 人工雲量 2008–2017（直接觀測）。2026 年不用。
  - 活動時段：night = 天文暮光結束到天文曙光開始（整夜，合歡山預設）；
              evening = 天文暮光結束到午夜 24:00（傍晚，學校預設）。
  - 月亮在地平線上的時間不算黑暗（不考慮月亮亮度與高度）。
假日不乘權重：輸出「隔天放假」欄位；加 --only-days-off 只排隔天放假的晚上。
天文數值依查詢區間即時用 ephem 計算，不受天文表年份限制。
輸出：results/recommend/recommend_<site>_<start>_<end>.csv（UTF-8 BOM，Excel 可開）與 .md
"""
import sys
import argparse
import datetime as dt
import pathlib

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hehuan import config as C          # noqa: E402
from hehuan.astro import night_ephem    # noqa: E402

SITES = {
    "hehuan": dict(name="合歡山觀星園", stn="C0H9C0", table="c0h9c0_halfmonth_prob_evening_clear.csv",
                   source="合歡山測站露點差代理判斷 2011–2025（方法在玉山驗證，未在合歡山實地驗證，暫定）",
                   window="night"),
    "taipei": dict(name="學校（臺北）", stn="466920", table="466920_halfmonth_prob_evening_clear.csv",
                   source="臺北測站人工雲量觀測 2008–2017（直接觀測）", window="evening"),
}
WEEKDAY = "一二三四五六日"


def half_key(d: pd.Timestamp) -> str:
    return f"{d.month:02d}{'a' if d.day <= 15 else 'b'}"


def load_calendar():
    cal = pd.read_csv(C.PROCESSED / "calendar" / "tw_calendar.csv", parse_dates=["date"]).set_index("date")
    cal["is_holiday"] = cal["is_holiday"].astype(str).str.lower().eq("true")
    return cal


def day_off(cal, d: pd.Timestamp):
    """(is the day off?, source). Outside the official calendar fall back to Saturday/Sunday."""
    if d in cal.index and cal.loc[d, "source"] == "dgpa":
        return bool(cal.loc[d, "is_holiday"]), "人事總處"
    return d.weekday() >= 5, "僅週末"


def remark(cal, d):
    if d in cal.index and isinstance(cal.loc[d, "remark"], str):
        return cal.loc[d, "remark"]
    return ""


def recommend(start, end, site="hehuan", window=None, min_dark=2.0, only_days_off=False):
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    if e < s:
        raise ValueError(f"結束日期 {end} 早於開始日期 {start}")
    if (e - s).days > 731:
        raise ValueError("查詢區間請不要超過兩年")
    cfg = SITES[site]
    window = window or cfg["window"]
    prob = pd.read_csv(C.RESULTS / "tables" / cfg["table"], index_col=0)
    st = C.station(cfg["stn"])
    cal = load_calendar()
    rows = []
    for d in pd.date_range(s, e, freq="D"):
        a = night_ephem(d.date(), st.lat, st.lon, st.alt_m)
        p = prob.loc[half_key(d)]
        off_next, cal_src = day_off(cal, d + pd.Timedelta(days=1))
        if window == "night":
            dark_h, win_h = a["dark_hours"], a["night_hours"]
        else:
            dark_h, win_h = a["dark_hours_evening"], a["evening_hours"]
        frac = dark_h / win_h if win_h else 0.0
        rows.append({
            "日期": d.date().isoformat(), "星期": WEEKDAY[d.weekday()], "隔天放假": "是" if off_next else "否",
            "晴天機率": round(float(p["p"]), 3), "機率95%區間": f"{p['ci_lo']:.2f}–{p['ci_hi']:.2f}",
            "天文暮光結束": a["astro_dusk"].strftime("%H:%M"),
            "月出": a["moonrise"].strftime("%H:%M") if pd.notna(a["moonrise"]) else "-",
            "月沒": a["moonset"].strftime("%H:%M") if pd.notna(a["moonset"]) else "-",
            "月亮照亮%": round(100 * a["moon_illum"]),
            "時段長度h": round(win_h, 2), "無月黑暗h": round(dark_h, 2), "無月比例": round(frac, 2),
            "分數": round(float(p["p"]) * frac, 3),
            "隔天是": remark(cal, d + pd.Timedelta(days=1)), "日曆來源": cal_src,
        })
    df = pd.DataFrame(rows)
    if only_days_off:
        df = df[df["隔天放假"] == "是"]
    df["黑暗足夠"] = df["無月黑暗h"] >= min_dark
    df = df.sort_values(["黑暗足夠", "分數", "無月黑暗h", "日期"], ascending=[False, False, False, True]).reset_index(drop=True)
    df.insert(0, "排名", range(1, len(df) + 1))
    return df, {**cfg, "site": site, "window": window, "min_dark": min_dark, "only_days_off": only_days_off}


def to_markdown(df, meta, start, end, top):
    win = "整夜（天文暮光結束到曙光開始）" if meta["window"] == "night" else "傍晚（天文暮光結束到 24:00）"
    cols = ["排名", "日期", "星期", "隔天放假", "晴天機率", "機率95%區間", "月出", "月沒", "月亮照亮%", "無月黑暗h", "分數", "隔天是"]
    lines = [f"# 觀星日期推薦：{meta['name']} {start} ～ {end}\n",
             f"- 分數 = 晴天機率 × 活動時段中無月黑暗的比例。活動時段：{win}。",
             f"- 晴天機率 = 該半月「傍晚 20、21 時雲量皆 ≤ 2 成」的歷史比例；資料：{meta['source']}。",
             "- 同一個月內各晚的晴天機率幾乎一樣，排名主要由月亮決定；機率差 0.1 以內通常分不出高下（看 95% 區間）。",
             f"- 無月黑暗少於 {meta['min_dark']} 小時的晚上排在最後。" + ("只列隔天放假的晚上。" if meta["only_days_off"] else ""),
             "", df.head(top)[cols].to_markdown(index=False)]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="觀星日期推薦")
    ap.add_argument("--site", default="hehuan", choices=sorted(SITES))
    ap.add_argument("--start", required=True, help="YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD")
    ap.add_argument("--window", choices=["night", "evening"], default=None, help="預設：合歡山 night、學校 evening")
    ap.add_argument("--min-dark", type=float, default=2.0, help="活動時段中至少要有幾小時無月黑暗")
    ap.add_argument("--only-days-off", action="store_true", help="只列隔天放假的晚上")
    ap.add_argument("--top", type=int, default=15)
    a = ap.parse_args()
    try:
        df, meta = recommend(a.start, a.end, a.site, a.window, a.min_dark, a.only_days_off)
    except (ValueError, KeyError) as err:
        sys.exit(f"錯誤：{err}")
    out = C.RESULTS / "recommend"; out.mkdir(exist_ok=True)
    stem = f"recommend_{a.site}_{a.start}_{a.end}" + ("_daysoff" if a.only_days_off else "")
    df.to_csv(out / f"{stem}.csv", index=False, encoding="utf-8-sig")
    md = to_markdown(df, meta, a.start, a.end, a.top)
    (out / f"{stem}.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
