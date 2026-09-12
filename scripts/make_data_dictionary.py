# -*- coding: utf-8 -*-
"""Generate docs/data_dictionary.md from the column maps in src/hehuan/clean.py and the actual processed files."""
import sys
import pathlib

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hehuan import config as C, clean   # noqa: E402

DESC = {
    "time": "小時終標籤，臺灣標準時間 UTC+8；CODiS 的 23:59 已轉成次日 00:00",
    "pres": "測站氣壓", "slp": "海平面氣壓（有人站）", "t_air": "氣溫", "td_obs": "測站觀測露點（有人站）",
    "rh": "相對濕度", "wind": "平均風速", "wind_dir": "平均風向", "gust": "最大陣風", "gust_dir": "陣風風向",
    "precip": "該小時累積雨量（小時終）", "precip_dur": "降水時數（有人站）", "sunshine": "日照時數", "solar": "全天空日射量",
    "vis_manual": "人工觀測能見度（有人站，僅特定時刻）", "vis_auto": "自動能見度", "uv": "紫外線指數",
    "cloud_manual": "人工觀測總雲量 0–10（有人站，僅特定時刻；夜間 20/21 時只到 2021 年）",
    "cloud_sat": "衛星反演總雲量 0–10（2023 起；夜間不可信，見 results/truth_audit.md）",
    "sky_obscured": "人工雲量代碼 -99.7：天空被霧遮蔽", "cloud_manual_eff": "真值用雲量：遮蔽或能見度 <1 km 時為 10",
    "td_magnus": "由 t_air 與 rh 以 Magnus 公式算的露點（冰面/水面自動切換）", "dpd": "露點差 t_air − td_magnus",
    "rain_3h": "本小時與前 2 小時雨量合計；任一小時缺值則為缺值", "rain_3h_known": "rain_3h 是否有值",
    "rain_6h": "6 小時雨量合計", "rain_6h_known": "rain_6h 是否有值", "rh_stuck": "RH 連續 ≥12 小時同一非飽和值（疑似感測器卡住）",
    "e_tcc": "ERA5 總雲量 0–1", "e_lcc": "ERA5 低雲", "e_mcc": "ERA5 中雲", "e_hcc": "ERA5 高雲",
    "e_mh": "ERA5 中＋高雲（隨機重疊）1−(1−mcc)(1−hcc)", "e_rh": "ERA5 2 m 相對濕度", "e_t2m": "ERA5 2 m 氣溫",
    "e_precip": "ERA5 該小時降水", "night": "夜的日期（傍晚那天）", "second_half": "是否為 00–04 時",
    "n_valid": "夜視窗內有效小時數", "n_clear": "晴小時數", "longest_clear_run": "最長連續晴小時",
    "mean_cloud": "視窗平均雲量（代理版為 0/10 虛擬值）", "def_A": "可觀星夜定義 A", "def_B": "定義 B", "def_C": "定義 C",
    "evening_clear": "20 與 21 時皆晴", "evening_any_clear": "20 或 21 時至少一小時晴",
    "moon_illum": "天文暮光末的月照亮比例", "dark_hours": "天文夜中無月的小時數", "night_hours": "天文夜長度（小時）", "dark_frac": "dark_hours / night_hours",
}


def describe(path: pathlib.Path, index_col=None):
    df = pd.read_csv(path, nrows=2000, index_col=index_col)
    cols = ([df.index.name] if df.index.name else []) + list(df.columns)
    rows = []
    for c in cols:
        base = c.replace("sat_", "") if c.startswith("sat_") else c
        for pre in ("rh_", "dpd_", "t_air_", "wind_", "pres_", "e_tcc_", "e_mh_"):
            if c.startswith(pre) and c.split("_")[-1] in ("mean", "min", "max"):
                base = "AGG"
        d = DESC.get(c) or DESC.get(base) or ("夜間視窗統計：" + c if base == "AGG" else "")
        if c.startswith("sat_"):
            d = "（衛星雲量版）" + d
        rows.append(f"| `{c}` | {clean.UNITS.get(c, '')} | {d} |")
    return "\n".join(["| 欄位 | 單位 | 說明 |", "|---|---|---|"] + rows)


def main():
    md = ["# 資料字典\n", "所有時間為臺灣標準時間（UTC+8），小時終標籤。缺值為空白。\n"]
    md.append("## data/raw/codis/<stn>/<stn>_<yyyy>.csv.gz\n原始欄位名稱（CODiS JSON 攤平，如 `AirTemperature.Instantaneous`），值未修改，含哨兵碼。對應表：\n")
    md.append("| 原始欄位 | 標準欄位 |\n|---|---|\n" + "\n".join(f"| `{k}` | `{v}` |" for k, v in clean.COLUMN_MAP.items()) + "\n")
    for title, glob, idx in (("data/processed/hourly/<stn>_hourly.csv.gz", "hourly/*_hourly.csv.gz", "time"),
                             ("data/processed/night_hours/<stn>_night_hours.csv.gz", "night_hours/*_night_hours.csv.gz", "time"),
                             ("data/processed/nights/<stn>_nights.csv", "nights/467550_nights.csv", "night"),
                             ("data/processed/nights/<stn>_nights_proxy.csv", "nights/*_nights_proxy.csv", "night"),
                             ("data/processed/astro/<site>_nights_astro_2008_2027.csv", "astro/*.csv", None),
                             ("data/processed/calendar/tw_calendar.csv", "calendar/tw_calendar.csv", None)):
        files = sorted((C.PROCESSED).glob(glob))
        if files:
            md.append(f"## {title}\n"); md.append(describe(files[0], idx) + "\n")
    md.append("## data/processed/qc/\n- `sentinel_codes.csv`：各站各欄的缺值哨兵碼與次數（清理前盤點）\n- `coverage_by_month.csv`：各站各月各欄有效比例\n"
              "- `rh_sensor_by_year.csv`：RH 上限、飽和比例、解析度（儀器異質性）\n- `rh_stuck_by_year.csv`：疑似卡住小時數\n- `timestamp_check_by_month.csv`：日射起始小時相對日出的偏移（0 或 +1 為正常）\n")
    (ROOT / "docs" / "data_dictionary.md").write_text("\n".join(md), encoding="utf-8")
    print("docs/data_dictionary.md written")


if __name__ == "__main__":
    main()
