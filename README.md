# 合歡山觀星氣候分析與上山日期推薦

高二自主學習專題。用中央氣象署測站觀測資料與 ERA5 再分析，回答「合歡山哪個月、哪幾天最容易看到星星」，並做出給天文社排活動日期用的推薦工具。

## 研究四步

1. **驗證代理指標**：在有人工夜間雲量觀測的玉山站（3845 m，2008–2021）驗證「露點差大且近三小時無雨」能否判斷當晚天空晴朗；阿里山、鞍部、臺北做海拔梯度對照。
2. **套用到合歡山**：合歡山自動站 C0H9C0 沒有雲量，用驗證過的代理指標重建 2011–2025 每晚是否可觀星。
3. **觀星氣候統計**：各月、半月可觀星機率（年區塊 bootstrap 信賴區間）、夜間各時段差異、連續晴夜機率、年際變化。
4. **上山日期推薦**：輸入日期範圍，結合氣候機率、月相、無月黑暗時數、假日，排出候選日期。

主要結果與限制見 [results/REPORT_night1.md](results/REPORT_night1.md)；每一個方法決定見 [docs/DECISIONS.md](docs/DECISIONS.md)。

## 快速使用

```bash
pip install -r requirements.txt
python scripts/recommend.py --start 2026-12-01 --end 2026-12-31 --top 10
```

## 重建全部結果

```bash
python scripts/fetch_codis.py --plan A     # 玉山、合歡山（可續跑；A→B→C→E→D）
python scripts/build_hourly.py             # cache JSON → raw CSV → processed hourly + QC
python scripts/build_astro.py              # 天文表（ephem，skyfield 抽驗）
python scripts/fetch_holidays.py           # 人事總處辦公日曆
python scripts/build_nights.py             # 夜間小時表與逐夜表
python scripts/truth_audit.py 467550       # 真值來源審核
python scripts/validate_proxy.py 467550    # 留一年交叉驗證
python scripts/apply_hehuan.py             # 合歡山氣候統計
python scripts/transfer_check.py           # 遷移證據
python scripts/sensitivity_and_backtest.py # 敏感度與推薦回測
python scripts/make_data_dictionary.py
pytest -q
```

## 目錄

```
config/stations.csv        測站主表（站號、角色、沿革）
src/hehuan/                套件：codis_client, clean, nights, era5, astro, holidays, validate, climatology
scripts/                   可執行腳本（上面的順序）
data/raw/                  原始資料 CSV（CODiS 逐時、ERA5、日曆、站清單）
data/processed/            hourly / night_hours / nights / astro / calendar / qc
results/                   tables, figures, recommend, *.md 報告
docs/                      PLAN、DECISIONS、data_dictionary、DATA_SOURCES、USER_TODO、計畫書修改稿、實況紀錄表
tests/                     pytest
```

原始 CODiS JSON 快取在 `%LOCALAPPDATA%\hehuan_cache`（不在 repo 內，可由 fetch 腳本重建）。

## 資料來源與授權

見 [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md)。ERA5 資料 © Copernicus / ECMWF（CC-BY 4.0），經 Open-Meteo 取得，僅供非商業用途。程式碼 MIT 授權。
