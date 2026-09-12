# 資料字典

所有時間為臺灣標準時間（UTC+8），小時終標籤。缺值為空白。

## data/raw/codis/<stn>/<stn>_<yyyy>.csv.gz
原始欄位名稱（CODiS JSON 攤平，如 `AirTemperature.Instantaneous`），值未修改，含哨兵碼。對應表：

| 原始欄位 | 標準欄位 |
|---|---|
| `StationPressure.Instantaneous` | `pres` |
| `SeaLevelPressure.Instantaneous` | `slp` |
| `AirTemperature.Instantaneous` | `t_air` |
| `DewPointTemperature.Instantaneous` | `td_obs` |
| `RelativeHumidity.Instantaneous` | `rh` |
| `WindSpeed.Mean` | `wind` |
| `WindDirection.Mean` | `wind_dir` |
| `PeakGust.Maximum` | `gust` |
| `PeakGust.Direction` | `gust_dir` |
| `Precipitation.Accumulation` | `precip` |
| `PrecipitationDuration.Total` | `precip_dur` |
| `SunshineDuration.Total` | `sunshine` |
| `GlobalSolarRadiation.Accumulation` | `solar` |
| `Visibility.Instantaneous` | `vis_manual` |
| `Visibility.AutoMean` | `vis_auto` |
| `UVIndex.Accumulation` | `uv` |
| `TotalCloudAmount.Instantaneous` | `cloud_manual` |
| `TotalCloudAmount.SatRetrieved` | `cloud_sat` |

## data/processed/hourly/<stn>_hourly.csv.gz

| 欄位 | 單位 | 說明 |
|---|---|---|
| `time` |  | 小時終標籤，臺灣標準時間 UTC+8；CODiS 的 23:59 已轉成次日 00:00 |
| `pres` | hPa | 測站氣壓 |
| `slp` | hPa | 海平面氣壓（有人站） |
| `t_air` | degC | 氣溫 |
| `td_obs` | degC | 測站觀測露點（有人站） |
| `rh` | % | 相對濕度 |
| `wind` | m/s | 平均風速 |
| `wind_dir` | deg | 平均風向 |
| `gust` | m/s | 最大陣風 |
| `gust_dir` | deg | 陣風風向 |
| `precip` | mm/h | 該小時累積雨量（小時終） |
| `precip_dur` | h | 降水時數（有人站） |
| `sunshine` | h | 日照時數 |
| `solar` | MJ/m2 | 全天空日射量 |
| `vis_manual` | km | 人工觀測能見度（有人站，僅特定時刻） |
| `vis_auto` | km | 自動能見度 |
| `uv` | index | 紫外線指數 |
| `cloud_manual` | 0-10 | 人工觀測總雲量 0–10（有人站，僅特定時刻；夜間 20/21 時只到 2021 年） |
| `cloud_sat` | 0-10 | 衛星反演總雲量 0–10（2023 起；夜間不可信，見 results/truth_audit.md） |
| `sky_obscured` | bool | 人工雲量代碼 -99.7：天空被霧遮蔽 |
| `cloud_manual_eff` | 0-10 | 真值用雲量：遮蔽或能見度 <1 km 時為 10 |
| `td_magnus` | degC | 由 t_air 與 rh 以 Magnus 公式算的露點（冰面/水面自動切換） |
| `dpd` | degC | 露點差 t_air − td_magnus |
| `rain_3h` | mm | 本小時與前 2 小時雨量合計；任一小時缺值則為缺值 |
| `rain_3h_known` | bool | rain_3h 是否有值 |
| `rain_6h` | mm | 6 小時雨量合計 |
| `rain_6h_known` | bool | rain_6h 是否有值 |
| `rh_stuck` |  | RH 連續 ≥12 小時同一非飽和值（疑似感測器卡住） |

## data/processed/night_hours/<stn>_night_hours.csv.gz

| 欄位 | 單位 | 說明 |
|---|---|---|
| `time` |  | 小時終標籤，臺灣標準時間 UTC+8；CODiS 的 23:59 已轉成次日 00:00 |
| `night` |  | 夜的日期（傍晚那天） |
| `second_half` |  | 是否為 00–04 時 |
| `cloud_sat` | 0-10 | 衛星反演總雲量 0–10（2023 起；夜間不可信，見 results/truth_audit.md） |
| `cloud_manual` | 0-10 | 人工觀測總雲量 0–10（有人站，僅特定時刻；夜間 20/21 時只到 2021 年） |
| `cloud_manual_eff` | 0-10 | 真值用雲量：遮蔽或能見度 <1 km 時為 10 |
| `sky_obscured` | bool | 人工雲量代碼 -99.7：天空被霧遮蔽 |
| `vis_manual` | km | 人工觀測能見度（有人站，僅特定時刻） |
| `rh` | % | 相對濕度 |
| `t_air` | degC | 氣溫 |
| `td_obs` | degC | 測站觀測露點（有人站） |
| `td_magnus` | degC | 由 t_air 與 rh 以 Magnus 公式算的露點（冰面/水面自動切換） |
| `dpd` | degC | 露點差 t_air − td_magnus |
| `precip` | mm/h | 該小時累積雨量（小時終） |
| `rain_3h` | mm | 本小時與前 2 小時雨量合計；任一小時缺值則為缺值 |
| `rain_3h_known` | bool | rain_3h 是否有值 |
| `rain_6h` | mm | 6 小時雨量合計 |
| `rain_6h_known` | bool | rain_6h 是否有值 |
| `wind` | m/s | 平均風速 |
| `gust` | m/s | 最大陣風 |
| `pres` | hPa | 測站氣壓 |
| `rh_stuck` |  | RH 連續 ≥12 小時同一非飽和值（疑似感測器卡住） |
| `e_tcc` |  | ERA5 總雲量 0–1 |
| `e_lcc` |  | ERA5 低雲 |
| `e_mcc` |  | ERA5 中雲 |
| `e_hcc` |  | ERA5 高雲 |
| `e_mh` |  | ERA5 中＋高雲（隨機重疊）1−(1−mcc)(1−hcc) |
| `e_rh` |  | ERA5 2 m 相對濕度 |
| `e_t2m` |  | ERA5 2 m 氣溫 |
| `e_precip` |  | ERA5 該小時降水 |

## data/processed/nights/<stn>_nights.csv

| 欄位 | 單位 | 說明 |
|---|---|---|
| `night` |  | 夜的日期（傍晚那天） |
| `sat_n_valid` |  | （衛星雲量版）夜視窗內有效小時數 |
| `sat_n_clear` |  | （衛星雲量版）晴小時數 |
| `sat_longest_clear_run` |  | （衛星雲量版）最長連續晴小時 |
| `sat_mean_cloud` |  | （衛星雲量版）視窗平均雲量（代理版為 0/10 虛擬值） |
| `sat_def_A` |  | （衛星雲量版）可觀星夜定義 A |
| `sat_def_B` |  | （衛星雲量版）定義 B |
| `sat_def_C` |  | （衛星雲量版）定義 C |
| `rh_mean` |  | 夜間視窗統計：rh_mean |
| `rh_min` |  | 夜間視窗統計：rh_min |
| `rh_max` |  | 夜間視窗統計：rh_max |
| `dpd_mean` |  | 夜間視窗統計：dpd_mean |
| `dpd_min` |  | 夜間視窗統計：dpd_min |
| `dpd_max` |  | 夜間視窗統計：dpd_max |
| `t_air_mean` |  | 夜間視窗統計：t_air_mean |
| `t_air_min` |  | 夜間視窗統計：t_air_min |
| `t_air_max` |  | 夜間視窗統計：t_air_max |
| `wind_mean` |  | 夜間視窗統計：wind_mean |
| `wind_min` |  | 夜間視窗統計：wind_min |
| `wind_max` |  | 夜間視窗統計：wind_max |
| `pres_mean` |  | 夜間視窗統計：pres_mean |
| `pres_min` |  | 夜間視窗統計：pres_min |
| `pres_max` |  | 夜間視窗統計：pres_max |
| `precip_night` |  |  |
| `precip_known_hours` |  |  |
| `n_hours_rh` |  |  |
| `e_tcc_mean` |  | 夜間視窗統計：e_tcc_mean |
| `e_tcc_min` |  | 夜間視窗統計：e_tcc_min |
| `e_tcc_max` |  | 夜間視窗統計：e_tcc_max |
| `e_lcc_mean` |  |  |
| `e_mcc_mean` |  |  |
| `e_hcc_mean` |  |  |
| `e_mh_mean` |  | 夜間視窗統計：e_mh_mean |
| `e_mh_min` |  | 夜間視窗統計：e_mh_min |
| `e_rh_mean` |  |  |
| `e_t2m_mean` |  |  |
| `e_precip_night` |  |  |
| `manual_cloud_2021_mean` |  |  |
| `manual_cloud_2021_max` |  |  |
| `manual_cloud_2021_n` |  |  |
| `evening_clear` |  | 20 與 21 時皆晴 |

## data/processed/nights/<stn>_nights_proxy.csv

| 欄位 | 單位 | 說明 |
|---|---|---|
| `night` |  | 夜的日期（傍晚那天） |
| `n_valid` |  | 夜視窗內有效小時數 |
| `n_clear` |  | 晴小時數 |
| `longest_clear_run` |  | 最長連續晴小時 |
| `mean_cloud` |  | 視窗平均雲量（代理版為 0/10 虛擬值） |
| `def_A` |  | 可觀星夜定義 A |
| `def_B` |  | 定義 B |
| `def_C` |  | 定義 C |
| `evening_clear` |  | 20 與 21 時皆晴 |
| `evening_any_clear` |  | 20 或 21 時至少一小時晴 |

## data/processed/astro/<site>_nights_astro_2008_2027.csv

| 欄位 | 單位 | 說明 |
|---|---|---|
| `night` |  | 夜的日期（傍晚那天） |
| `sunset` |  |  |
| `astro_dusk` |  |  |
| `astro_dawn` |  |  |
| `sunrise` |  |  |
| `moonrise` |  |  |
| `moonset` |  |  |
| `moon_illum` |  | 天文暮光末的月照亮比例 |
| `moon_alt_midnight` |  |  |
| `night_hours` |  | 天文夜長度（小時） |
| `dark_hours` |  | 天文夜中無月的小時數 |
| `dark_frac` |  | dark_hours / night_hours |

## data/processed/calendar/tw_calendar.csv

| 欄位 | 單位 | 說明 |
|---|---|---|
| `date` |  |  |
| `weekday` |  |  |
| `星期` |  |  |
| `is_holiday` |  |  |
| `next_is_holiday` |  |  |
| `remark` |  |  |
| `source` |  |  |

## data/processed/qc/
- `sentinel_codes.csv`：各站各欄的缺值哨兵碼與次數（清理前盤點）
- `coverage_by_month.csv`：各站各月各欄有效比例
- `rh_sensor_by_year.csv`：RH 上限、飽和比例、解析度（儀器異質性）
- `rh_stuck_by_year.csv`：疑似卡住小時數
- `timestamp_check_by_month.csv`：日射起始小時相對日出的偏移（0 或 +1 為正常）
