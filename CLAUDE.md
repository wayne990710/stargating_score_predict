# CLAUDE.md — 給接手這個 repo 的 Claude

先讀 docs/RESEARCH_NOTES.md（研究筆記：目前狀態、踩過的坑、不要重做的事、下一步）。
再讀 docs/DECISIONS.md（每個方法決定與理由）。結果在 results/REPORT_night1.md。

## 專案一句話
高二自主學習：用氣象署測站與 ERA5 分析合歡山觀星氣候，做上山日期推薦。不做短期預報（使用者決定）。

## 硬規則
- CODiS 是非官方 API：一站一曆月一請求、間隔 ≥1.2 秒、不平行、不排程每天跑。
- 原始 JSON 快取在 %LOCALAPPDATA%\hehuan_cache（OneDrive 之外），repo 只放 CSV。
- 計畫書 PDF 含使用者姓名，已 gitignore，不要加進 repo。
- 2026 年資料不用於門檻選擇與氣候統計（留作活動對照）。
- 圖要中文字型：plt.rcParams["font.family"] = ["Microsoft JhengHei", "DejaVu Sans"]。
- 重跑順序：build_hourly → build_nights → validate_proxy 467550 → apply_hehuan → transfer_check → sensitivity_and_backtest。
- 用 PYTHONIOENCODING=utf-8 執行 Python，否則中文輸出會亂碼。

## 使用者偏好
- 中文（繁體）溝通；喜歡先看結論與風險；要誠實標示「已驗證 / 暫定」。
- 研究筆記是給 Claude 自己看的，寫在 docs/RESEARCH_NOTES.md，每次工作結束更新。
