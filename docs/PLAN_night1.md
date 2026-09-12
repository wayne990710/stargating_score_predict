# 第一夜工作計畫（Claude 自主執行）

日期：2026-09-12 起的一個晚上（約 7 小時）
研究定位：合歡山觀星氣候分析與上山日期推薦（已放棄短期預報）

## 0. 探勘後的新事實（會改變做法）

| 發現 | 影響 |
|---|---|
| 衛星反演雲量（SatRetrieved）只從 2023-01 開始有值，不是十年 | 衛星真值只有 2023–2025 三年；2015–2021 玉山有 20/21 時的人工雲量可當「傍晚補充真值」 |
| 玉山白天人工雲量 ≤2 時，衛星仍常報 ≥8；衛星幾乎不給 0 | 「雲海（雲在站下）」與「寒冷地表誤判」可能讓真值系統性偏陰，必須先做真值可用性審核，才能選門檻 |
| CODiS 一次請求可跨一個曆月（31–32 天），45 天以上回 code 400 | 一站一月一請求；今晚約 800 次請求，約 40 分鐘 |
| 成功回應的 body code 是 200（不是 0） | 抓取器的成功判定要寫對，否則整晚抓不到任何東西 |
| 缺值不只 null，還有 -9997、-9999.7、-99.5、-999.6 等小數哨兵碼 | 一律 ≤ -90 → NaN，先產出哨兵碼盤點表；雨量視窗有缺值時視為「未知」，不可當「無雨」 |
| 高山站 RH 日週期最低點不一定在午後 | 時間戳對齊改用日射起始小時 vs 日出時刻檢查 |
| 冬季負溫下 RH 感測器在雲霧中只讀 93–97% | 主特徵改用露點差（Magnus 公式），門檻按 T<0 / T≥0 分層 |
| Open-Meteo 免帳號可取 ERA5 逐時總/低/中/高雲量，已抓好 5 站 2008–2025 | 不用等 CDS 帳號；但必須指定 models=era5，否則 2017 起會混入 IFS |
| 合歡山、昆陽、小奇萊、奇萊稜線、大禹嶺同一個 ERA5 格點 | ERA5 對合歡山群只有一條序列 |
| 阿里山 467530（2413 m）有 24 小時 SatRetrieved | 海拔梯度的中間站，只需 36 次請求 |
| 鹿林天文台公開 2009–2025 氣象站與 2012–2024 雲感測器原始檔 | 台灣高山獨立地面真值，但屬檔案下載，需使用者同意 |
| 專案目錄在 OneDrive 同步範圍 | 原始 JSON 快取放 OneDrive 外，寫檔即 gzip |

## 1. 主線（MVP，必做）

### 區塊 0（0:00–0:30）骨架
- 目錄：src/hehuan/、scripts/、config/、data/{raw,processed}/、results/{tables,figures}/、docs/、tests/、logs/
- .gitignore：cache、*.bsp、logs、計畫書 PDF（含個人姓名）
- requirements.txt、LICENSE（MIT）、config/stations.csv（含沿革註記：466920 2014 遷站、C0H990 2015 儀器汰換、C0I5x0 2017-12-28 起）
- CACHE_DIR 預設 %LOCALAPPDATA%\hehuan_cache
- 搬入探勘成果：codis_client、night_labels、astro、holidays、ERA5 CSV（gzip）
- commit #1 並 push（使用者先前已同意推第一版骨架）

### 區塊 1（0:30–1:15）抓取
- scripts/fetch_codis.py：一站一月；成功 = HTTP 200 且 body code==200 且 count ≥ 該月預期列數×0.9；400 不重試；5xx/逾時退避重試；manifest 記 expected_rows；限速 1.2 s；gzip；可續跑
- 先實測 2 個月（起始月 2008-02 應 120 列、閏年 2 月 696 列）
- 背景批次 A（347 次）：玉山 2023–25 → 玉山 2015–22 → 合歡山 2008–25
- 背景批次 B（408 次）：玉山 2008–14、臺北/鞍部 2023–25、昆陽 2008–25、阿里山 2023–25
- 背景批次 C（約 56 次）：各站 2026-01～08（活動對照與留出測試期）
- ERA5 補阿里山格點（1 次，與前次間隔 60 s），補齊 meta.json

### 區塊 2（1:15–2:30）清理與品質
- qc/sentinel_codes.csv（站×欄×值×次數）→ ≤ -90 → NaN
- 23:59 → 次日 00:00；完整逐時索引 reindex
- 時間戳硬檢查：日射首個非零小時 vs skyfield 日出；夜間日射必為 0
- RH 儀器異質性：每站每年直方圖、上限（100 vs 98）、解析度；合歡山 vs 昆陽同時刻差
- stuck 規則排除飽和值；被標記小時在夜聚合中視為缺值
- Magnus 露點差；cwb 站與官方露點 MAE
- 雨量視窗 rolling(min_periods=window)，未知 ≠ 無雨
- tests/test_data_integrity.py
- commit #2

### 區塊 3（2:30–3:30）真值可用性審核（新增，評審列為 blocker）
- 玉山白天 08/09/11/14/17 時人工雲量 vs 同時刻衛星：混淆矩陣按月、按時刻；「人工 ≤2 但衛星 ≥8」比例
- 衛星值分布、0 的出現率、日夜切換是否不連續
- 缺值非隨機性：缺值小時 vs 非缺值小時的 RH/露點差/ERA5 tcc 分布；缺值率按月×整點
- ERA5 雲海旗標（lcc 高且 mcc+hcc 低）與寒夜旗標（tcc 低且 T<0），與站 RH 無關
- 玉山各月 def_A 比例 vs 鹿林年報（距 8 km）10–12 月最佳、6–7 月最差的月分布
- results/truth_audit.md
- 檢查點 1：若落後，砍區塊 5 的回測與區塊 6 的計畫書修改稿改為延伸
- commit #3

### 區塊 4（3:30–5:00）核心驗證與合歡山第一版
- build_nights：夜 = 前一日 20:00–當日 04:00 共 9 整點；晴 = 衛星 ≤2；def_A（≥3 連續晴小時且有效 ≥6）主、B 嚴格、C 敏感度；真值表：玉山、臺北、鞍部、阿里山
- validate_proxy MVP：規則 R1「露點差 ≤ X 且過去 3 小時無雨（已知）」，X 只在訓練折用 Youden J 選，T<0/T≥0 分層；氣候基準線只用訓練折；leave-one-year-out；逐時與逐夜兩層 precision/recall/F1/kappa；月比例偏差表（全部 / 剔除雲海旗標兩版）；3 年真值用夜移動區塊 bootstrap；三聯圖
- 海拔對照：臺北、鞍部、阿里山各一列逐時 kappa
- ERA5 vs 衛星：tcc / max(mcc,hcc) / 1−(1−mcc)(1−hcc)，Spearman、kappa、月偏差；決定 ERA5 角色
- apply_hehuan：各月/半月可觀星機率、年區塊 bootstrap 95% CI、月×整點熱圖、逐年折線；chosen_thresholds.json 帶 status（validated/tentative）；tentative 不進 README
- 玉山月偏差表拆「雲海/寒夜旗標貢獻」與「其餘」，今晚不校正合歡山
- 檢查點 2
- commit #4、#5

### 區塊 5（5:00–6:00）天文表、假日、推薦 v0
- astro：ephem 批次算 2008–2027 合歡山與臺北每夜日落、暮光末、曙光始、月出月沒、照亮比、天文夜時數、無月黑暗時數；抽 30 夜與 skyfield 對照
- holidays：人事總處辦公日曆 2017–2027（utf-8-sig 退 cp950）
- recommend CLI：score = P_climate(半月) × (無月黑暗時數/天文夜) × 假日權重；示範 2026-10-01～12-31
- 回測 lift 用 leave-one-year-out；並列「只用月相」對照
- commit #6

### 區塊 6（6:00–7:00）文件與交接
- data/README.md 資料字典（由欄位對映 dict 自動生成）
- docs/DECISIONS.md（ADR 式）
- docs/USER_TODO.md：CDS 帳號步驟、鹿林下載 curl 指令、push 與 PDF 決定、門檻決定、2026 資料每月補抓方式
- docs/計畫書修改稿_v2.md（原版 vs 修改版對照表）
- docs/observation_log_template.csv（10/8、12/11–13 實況紀錄）
- results/REPORT_night1.md、README.md、reports/NIGHT_LOG.md
- commit #7；push 程式與文件（資料檔另議）

## 2. 延伸（時間允許才做，依序）
1. 邏輯迴歸（≤6 特徵）與 max_depth=3 決策樹對照；reliability diagram 與 Brier skill score
2. 2015–2021 玉山 20/21 時人工雲量獨立測試（只報逐時，註明傍晚視角）
3. 定義敏感度表：A/B/C × 晴門檻 ≤1/≤2/≤3 × 露點差門檻 ±0.5 °C 的月排名 Spearman
4. 連續晴夜機率、前/後半夜差異、逐年變化
5. 天文夜遮罩敏感度（夏季剔除暮光小時）
6. 大禹嶺 C0T790 全期（216 次）、小奇萊/奇萊稜線 2017-12 起
7. Open-Meteo 四鄰格點 ERA5（海拔匹配敏感度）
8. 推薦結果單檔靜態 HTML
9. 舊合歡山站 C0F950 1990–2008、昆陽 1992–2007 延長序列

## 3. 需要使用者做的事（不做也不影響今晚主線）
- 【決定】是否 push 資料檔到 GitHub；計畫書 PDF 含個人姓名，預設不進 repo
- 【決定】主定義與門檻預設值（夜窗 20–04、晴 ≤2、def_A、露點差門檻由訓練折決定），可改 config 重跑
- 【決定】是否納入阿里山當海拔對照（預設納入）
- 【操作，選做】Copernicus CDS 帳號：註冊 → .cdsapirc → 接受 CC-BY → pip install cdsapi → 跑 scripts/fetch_era5_cds_timeseries.py
- 【同意，選做】下載鹿林天文台原始檔（每年 60–70 MB）到 data/raw/lulin/
- 【操作】10/8 校內小觀當晚用實況紀錄表記錄

## 4. 請求量與檔案大小
- CODiS 今晚約 810 次請求（延伸最多再 +430），間隔 1.2 s，不平行
- 原始 JSON gzip 後約 110 MB（OneDrive 外）；processed CSV gz 約 40 MB；ERA5 約 10 MB
