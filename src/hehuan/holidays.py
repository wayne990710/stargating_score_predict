"""
load_holidays.py -- 讀取行政院人事行政總處「政府行政機關辦公日曆表」CSV
來源 (data.gov.tw 資料集 14718)：https://data.gov.tw/dataset/14718
   程式化取得各年 CSV 連結：GET https://data.gov.tw/api/v2/rest/dataset/14718  -> result.distribution[].resourceDownloadUrl
格式：欄位 西元日期(YYYYMMDD), 星期(一~日), 是否放假(0=上班日, 2=放假日), 備註(節日名稱/補假/補行上班)
編碼：115/116 年 (2026/2027) 與 108/113 年為 UTF-8 with BOM；114 年 (2025, 1141020更新版) 為 Big5(cp950)。
      → 一律先試 utf-8-sig 再退回 cp950。
另有 *_Google行事曆專用.csv (Subject/Start Date/... 只列節日) 不適合當每日表。
"""
import pandas as pd, glob, os

def load_calendar(path):
    for enc in ("utf-8-sig", "cp950"):
        try:
            df = pd.read_csv(path, encoding=enc, dtype=str)
            break
        except UnicodeDecodeError:
            continue
    df.columns = [c.strip() for c in df.columns]
    df["date"] = pd.to_datetime(df["西元日期"], format="%Y%m%d")
    df["is_holiday"] = df["是否放假"].str.strip() == "2"
    df["remark"] = df["備註"].fillna("")
    return df[["date", "星期", "is_holiday", "remark"]]

def load_all(folder=os.path.dirname(os.path.abspath(__file__))):
    files = [f for f in sorted(glob.glob(os.path.join(folder, "cal_*.csv"))) if "google" not in f]
    return pd.concat([load_calendar(f) for f in files], ignore_index=True).drop_duplicates("date").sort_values("date")

if __name__ == "__main__":
    import sys; sys.stdout.reconfigure(encoding="utf-8")
    df = load_all()
    print(df.groupby(df.date.dt.year)["is_holiday"].agg(["count", "sum"]))
    # 「觀星適合的假日前夜」= 隔天放假的日子（週五、連假前一天）
    df["next_is_holiday"] = df["is_holiday"].shift(-1)
    print(df[(df.date >= "2026-01-01") & (df.date <= "2026-02-28") & df.next_is_holiday].to_string(index=False))
