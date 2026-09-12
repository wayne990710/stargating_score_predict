# 合歡山觀星氣候分析與上山日期推薦

高二自主學習專題。用中央氣象署測站觀測資料與 ERA5 再分析，回答「合歡山哪個月、哪幾天最容易看到星星」，並做出給天文社排活動日期用的推薦工具。

## 研究四步

1. **驗證代理指標**：在有衛星反演雲量的有人站（玉山 467550 為主，阿里山、鞍部、臺北做海拔對照），驗證用相對濕度、露點差、降雨能不能判斷「當晚可不可以觀星」。
2. **套用到合歡山**：合歡山自動站 C0H9C0 沒有雲量，用驗證過的代理指標重建 2008–2025 每晚的可觀星標籤。
3. **觀星氣候統計**：各月、半月可觀星夜機率、夜間時段差異、連續晴夜機率、年際變化。
4. **上山日期推薦**：輸入日期範圍，結合氣候機率、月相、無月黑暗時數、假日，排出候選日期。

## 目錄

```
config/stations.csv        測站主表
src/hehuan/                套件（抓取、清理、夜標籤、天文、假日、驗證、氣候統計、推薦）
scripts/                   可執行腳本
data/raw/                  原始資料（CSV，可重現）
data/processed/            清理後的逐時表、逐夜表、QC 報告
results/                   表格與圖
docs/                      計畫、決策紀錄、資料字典、資料來源
tests/                     pytest
```

原始 CODiS JSON 快取在 `%LOCALAPPDATA%\hehuan_cache`（不在 repo 內）。

## 安裝

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 資料來源與授權

見 [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md)。ERA5 資料 © Copernicus / ECMWF（CC-BY 4.0），經 Open-Meteo 取得，僅供非商業用途。
