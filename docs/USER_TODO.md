# 需要你做的事（Claude 做不到或不該替你做的）

## 需要決定
1. **要不要 push 資料檔到 GitHub**：程式與文件已推。`data/raw/codis`（約 40 MB）與 `data/processed`（約 60 MB）目前只在本機 commit。若要推，直接 `git push`；若嫌大，可在 .gitignore 加 `data/processed/night_hours/` 後再推。
2. **計畫書 PDF**：含你的姓名，已被 .gitignore 排除，不會進 GitHub。
3. **主定義與門檻**：目前主定義 A（≥3 連續晴小時且 ≥6 有效小時）、露點差門檻由玉山訓練年決定（見 results/tables/validation_467550_thresholds.json）。要改就改 `src/hehuan/config.py` 或 thresholds 檔後重跑 `scripts/apply_hehuan.py`，不需重抓資料。
4. **推薦工具的主指標**：預設用「傍晚 20–21 時皆晴」機率（直接驗證過），可改用 def_A（整夜，未直接驗證後半夜）。

## 選做：官方 ERA5（Copernicus CDS）交叉驗證
1. 到 https://cds.climate.copernicus.eu 註冊 ECMWF 帳號並登入。
2. 到 https://cds.climate.copernicus.eu/how-to-api 複製 `url:` 與 `key:` 兩行，存成 `C:\Users\<你>\.cdsapirc`。
3. 到資料集頁面 reanalysis-era5-single-levels 與 reanalysis-era5-single-levels-timeseries 的 Download 分頁最下方接受 CC-BY 授權。
4. `pip install "cdsapi>=0.7.7"`，然後執行 `python scripts/fetch_era5_cds_timeseries.py`。
目前所有結果用 Open-Meteo 的 ERA5（models=era5），不依賴此步。

## 選做：鹿林天文台雲感測器與氣象站原始檔（台灣高山獨立地面真值）
- 雲感測器（Boltwood，10 分鐘 sky−ambient 溫差，2012–2024，每年 0.5–7 MB）與氣象站（逐分鐘，2009–2025，每年 60–70 MB）公開於 https://www.lulin.ncu.edu.tw/download/weather/WeatherFiles/
- 屬於檔案下載，需要你同意；同意後告訴 Claude，或自行下載到 `data/raw/lulin/`。
- 用途：用鹿林（2862 m，距玉山站 8 km）驗證露點差規則在整夜（含後半夜）的表現，這是目前真值只到 21 時的最大缺口。

## 活動實況紀錄
- 10/8 校內小觀、12/11–13 合歡山大觀：用 `docs/observation_log_template.csv` 每小時記錄目視雲量（0–10）、有無起霧、肉眼極限星等、月亮是否在天上。
- 事後執行 `python scripts/fetch_codis.py --plan C` 補抓當月測站資料，就能把實況與代理指標對照。

## 學期中資料更新
- 每月執行一次 `python scripts/fetch_codis.py --plan C`（只抓 2026 年、跳過已完成月份），間隔 ≥1.2 秒，不要平行、不要排程每天跑。
- 之後重跑 `scripts/build_hourly.py`、`scripts/build_nights.py`。

## 未完成／延伸（依優先序）
- 鄰站大禹嶺、小奇萊、奇萊稜線全期（`--plan D`）：合歡山群站間一致性。
- 邏輯迴歸與決策樹的校準圖（reliability diagram）。
- 推薦結果單檔靜態網頁。
