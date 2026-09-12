# 資料來源與授權

| 來源 | 內容 | 取得方式 | 授權 / 注意事項 |
|---|---|---|---|
| 中央氣象署 CODiS 氣候觀測資料查詢服務 | 測站逐時觀測（氣溫、濕度、風、雨量、日射、有人站另有露點、能見度、人工雲量、衛星反演雲量） | 網頁背後的非官方 API `POST https://codis.cwa.gov.tw/api/station`，一站一曆月一次請求，間隔 ≥1.2 秒 | 氣象署開放資料採政府資料開放授權條款 1.0。此 API 未公開文件，可能隨時改版；原始 JSON 存於本機快取，衍生 CSV 進 repo。 |
| ERA5 再分析（ECMWF / Copernicus C3S） | 逐時總雲量、低/中/高雲量、2 m 濕度、氣溫、露點、降水、地面氣壓，0.25° 格點，1940 起 | 經 Open-Meteo Historical Weather API（免帳號，`models=era5`）；官方 CDS 路線腳本見 scripts/fetch_era5_cds*.py | ERA5：Copernicus 授權（CC-BY 4.0，需註明 Hersbach et al. 2020）。Open-Meteo：CC-BY 4.0，免費方案限非商業用途。 |
| 行政院人事行政總處 政府行政機關辦公日曆表 | 每日是否放假、備註 | data.gov.tw 資料集 14718，每民國年一個 CSV | 政府資料開放授權條款 1.0。114 年檔為 Big5，其餘 UTF-8 BOM。 |
| JPL DE421 星曆 | 太陽、月亮位置（skyfield 用） | 首次執行自動下載，存於快取 | 公有領域。 |

## 引用

- Hersbach, H. et al. (2020). The ERA5 global reanalysis. *Q. J. R. Meteorol. Soc.*, 146, 1999–2049.
- 中央氣象署（2026）。氣候觀測資料查詢服務 CODiS。https://codis.cwa.gov.tw/
- Open-Meteo (2026). Historical Weather API. https://open-meteo.com/en/docs/historical-weather-api

## 測站

見 config/stations.csv。角色：`truth` = 有衛星反演雲量的有人站（真值）；`target` = 合歡山；`neighbor` = 合歡山周邊自動站；`archive` = 舊站，僅記錄。
