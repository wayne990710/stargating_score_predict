# 研究筆記（Claude 自用，每次工作結束更新）

最後更新：2026-09-12 晚。讀者是下一個接手的 Claude。目的：不要重做已做過的事、不要再踩同樣的坑、知道下一步從哪裡開始。

## 0. 現況一頁

- repo 與 GitHub 同步（remote 名稱 astronomical_observation_predict，本機資料夾 stargating_score_predict，使用者自己改的，不用動）。
- 資料全部抓完：9 站 CODiS 2008-01～2026-08（1,777 站月，14 個 partial 是測站停測期），ERA5 六格點，天文表，日曆。
- 主結果：合歡山傍晚 20–21 時皆晴機率（已驗證）；整夜版兩個暫定版本。
- 鹿林天文台原始檔已下載到 %LOCALAPPDATA%\hehuan_cache\lulin\（cloudsensor 13 檔、weather 17 檔，共 1.2 GB），**尚未解析**。
- 使用者已同意的事：下載鹿林檔案、push 資料到 GitHub、git 同步。
- 使用者還沒做的事：10/8 實況紀錄、決定主定義、CDS 帳號（選做）。

## 1. 不要重做的事（已確認的事實）

| 事實 | 證據位置 |
|---|---|
| 衛星反演雲量夜間 2025-06 前全報陰，不可當真值 | results/truth_audit.md |
| 人工雲量夜間只有 20/21（冬季 05）時，2022 起停止 | truth_audit_manual_coverage_*.csv |
| -99.7 = 霧遮蔽 → 雲量 10；null 且 vis<1 km 也視為遮蔽 | clean.py standardize() |
| 合歡山 RH 2011-11 前全是 -9997 | qc/sentinel_codes.csv |
| CODiS report_date 上限 32 天，45 天以上 code 400；成功 body code 是 200 | scripts/fetch_codis.py |
| Open-Meteo 必須 models=era5；阿里山要 cell_selection=nearest | era5_openmeteo/meta.json |
| 高山站日射起始比日出晚 1 小時是地形/門檻，不是時間戳錯（平地站為 0） | qc/timestamp_check_by_month.csv |
| 邏輯迴歸不比露點差規則好；R_rh 與 R_dpd 幾乎相同 | validation_467550.md |
| 只用地面規則的整夜 def_A 夏季假晴（7 月 0.57）；ERA5 中高雲整夜不散 | c0h9c0_month_hour_clear.csv、REPORT §4.2 |
| 露點差＋ERA5 中高雲組合在 20/21 時 recall 只有 0.59（Youden 在子集上太嚴） | validation_467550_pooled.csv |
| 海拔梯度 kappa：臺北 0.23 → 鞍部 0.28 → 阿里山 0.38 → 玉山 0.60 | transfer_altitude_gradient.csv |
| 鄰站一致性：昆陽/小奇萊 kappa >0.7，大禹嶺/奇萊稜線 0.43–0.46 | transfer_hehuan_vs_neighbours.csv |
| 推薦回測 lift 1.2（0.7–1.65）；只用月相也有 1.13，因黑暗時數與季節相關 | c0h9c0_recommend_lift_summary.csv |

## 2. 踩過的坑

- pandas 讀 stations.csv 空欄位變 NaN → keep_default_na=False。
- 夜標籤表若含 05 時，label_from_clear 要先過濾 NIGHT_HOURS，否則 def_A 會多算一小時。
- evening_clear 欄是 bool 含 NaN → object dtype，nlargest 會炸，先 astype(float)。
- git 在 Windows 會噴一堆 CRLF warning，無害；.gitattributes 已設 LF。
- bash 裡 $LOCALAPPDATA 是反斜線路徑，ls 會失敗；用 Python 的 config.CODIS_CACHE。
- 背景 Bash 的 sleep 可以用，前景 sleep 被擋；等條件用 until grep 迴圈。
- 玉山 2023 年 RH 中位數 100%，感測器異常；不在主要驗證年份，但做任何 2023 的分析要先排除。
- Youden J 選門檻會讓夏季高估 0.11–0.15；若要月偏差最小，門檻要改用校準準則（還沒做）。

## 3. 目前最弱的環節（審查會問的）

1. 後半夜、尤其夏季，沒有真值。鹿林雲感測器是解法（見 §5）。
2. 玉山（有人站）與合歡山（自動站）RH 感測器不同；合歡山飽和時數比例是玉山兩倍。門檻直接沿用是假設。
3. 傍晚版定義嚴格（兩小時都晴），數值偏低；要跟使用者確認他們要的是哪種定義。
4. 推薦工具的假日權重 0.6 是拍腦袋的；lift 回測沒含假日。

## 4. 想過但沒做的事

- 門檻改用「月偏差最小」校準（而非 Youden），可能修掉夏季高估。
- 用玉山 2015–2021 的能見度當「站上霧」獨立指標，檢查 RH≥98 的規則。
- 決策樹 max_depth=3 對照、LR reliability diagram、Brier skill score。
- 天文夜遮罩敏感度（夏季 20 時仍在暮光內）。
- 舊合歡山站 C0F950 1990–2008、昆陽 1992–2007 延長序列（各約 200 次請求）。
- 推薦結果靜態 HTML 頁。
- 臺北站的傍晚氣候（466920 有人工雲量 2008–2017），10/8 校內小觀可用；truth_audit 已產出 truth_audit_evening_clear_share_466920.csv，但沒整理進報告。

## 5. 下一步（建議順序）

1. **鹿林雲感測器解析器**：格式見檔頭（Boltwood Cloud Sensor II 原始行；欄位 SkyRl=天空溫度、Ambnt=環境溫度、Cvr 或雲況代碼 1=晴 2=多雲 3=陰）。先用 2013–2016 完整年份。做法：10 分鐘 → 逐小時 → 與鹿林氣象站（Davis，逐分鐘，Dew Pt. 欄）的露點差對照 → 整夜（20–04）各小時 kappa，特別看 6–8 月 00–04 時。若後半夜 kappa 也 >0.5，整夜版可升級為已驗證。
   - 注意：氣象站 2009–2015 是 12 小時制時間，2018 起 24 小時制；Bar 欄單位年年不同；雲感測器 2017、2018、2020 檔很小。
2. 跟使用者確認主定義（傍晚兩小時皆晴 vs 至少一小時），與假日權重。
3. 10/8 後補抓 --plan C，做第一筆實況對照。
4. 報告裡補一段臺北站傍晚氣候（給校內小觀用）。

## 6. 指令備忘

```
set PYTHONIOENCODING=utf-8
python scripts/fetch_codis.py --plan C            # 學期中補抓 2026
python scripts/build_hourly.py && python scripts/build_nights.py
python scripts/validate_proxy.py 467550           # 主驗證；加參數 "5 11,12,1,2 _h05_winter" 做冬季 05 時
python scripts/apply_hehuan.py C0H9C0 467550 R_dpd tentative
python scripts/apply_hehuan.py C0H9C0 467550 R_dpd+E_mh tentative
python scripts/transfer_check.py && python scripts/sensitivity_and_backtest.py
python scripts/recommend.py --start 2026-10-01 --end 2026-12-31 --top 12
pytest -q
```

## 7. 與使用者互動的觀察

- 使用者是高中生、天文社社長，會問「這樣有錯嗎」、「主要風險是什麼」；回答要先給結論、再給理由，表格比長段落好。
- 使用者在意「像不像研究」，願意砍功能換嚴謹。
- 使用者說「先這樣」表示暫停，不是結束；下次可能從任何一點接續。
