# -*- coding: utf-8 -*-
"""Proxy-indicator validation against human night cloud observations at a manned station.

Sample  : hours with a manual cloud observation at night (default 20/21 LST; 05 LST is twilight in summer), 'clear' = cloud_manual_eff <= 2
          (sky obscured by fog counts as cloud 10).
Features: only variables that the Hehuanshan automatic station also has (rh, t_air, dpd from Magnus, rain_3h,
          wind) plus ERA5 cloud for comparison.
Models  : R_dpd  : clear if dpd >= X  and no rain in the last 3 h (known)
          R_rh   : clear if rh  <= Y  and no rain in the last 3 h (known)
          LR     : logistic regression on [rh, dpd, t_air, rain flag, wind]  (interpretable, <= 6 features)
          E_tcc  : clear if ERA5 total cloud <= Z          (reanalysis baseline)
          E_mh   : clear if ERA5 mid+high cloud <= Z       (cloud-above-station variant)
          CLIM   : month climatology of the training years (predict majority class)
CV      : leave-one-year-out. Thresholds / scaler / climatology are fitted on the training years only.
Metrics : precision, recall, F1 (positive = clear), balanced accuracy, Cohen kappa, and the monthly
          clear-share bias (predicted - observed) on the held-out year.
"""
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

FEATURES = ["rh", "dpd", "t_air", "rain3_flag", "wind"]


def kappa(y, p):
    y = np.asarray(y, bool); p = np.asarray(p, bool)
    po = (y == p).mean()
    pe = y.mean() * p.mean() + (1 - y.mean()) * (1 - p.mean())
    return (po - pe) / (1 - pe) if pe < 1 else np.nan


def metrics(y, p):
    y = np.asarray(y, bool); p = np.asarray(p, bool)
    tp = (y & p).sum(); fp = (~y & p).sum(); fn = (y & ~p).sum(); tn = (~y & ~p).sum()
    prec = tp / (tp + fp) if tp + fp else np.nan
    rec = tp / (tp + fn) if tp + fn else np.nan
    f1 = 2 * prec * rec / (prec + rec) if prec and rec and not np.isnan(prec) and not np.isnan(rec) else np.nan
    tnr = tn / (tn + fp) if tn + fp else np.nan
    return dict(n=len(y), pos_rate=y.mean(), pred_rate=p.mean(), precision=prec, recall=rec, f1=f1,
                specificity=tnr, bal_acc=np.nanmean([rec, tnr]), kappa=kappa(y, p), accuracy=(y == p).mean())


def youden_threshold(x: pd.Series, y: pd.Series, direction: str):
    """Best cut on x maximising TPR - FPR. direction 'ge': predict clear if x >= t ; 'le': if x <= t."""
    xs = np.sort(x.dropna().unique())
    if len(xs) > 400:
        xs = np.quantile(xs, np.linspace(0, 1, 400))
    best, bt = -np.inf, np.nan
    yv = y.loc[x.dropna().index].to_numpy(bool); xv = x.dropna().to_numpy()
    for t in xs:
        p = xv >= t if direction == "ge" else xv <= t
        tpr = (p & yv).sum() / max(yv.sum(), 1)
        fpr = (p & ~yv).sum() / max((~yv).sum(), 1)
        j = tpr - fpr
        if j > best:
            best, bt = j, t
    return float(bt), float(best)


def prepare(nh: pd.DataFrame, truth_hours=(20, 21)) -> pd.DataFrame:
    """nh: night-hours table (index=time) with cloud_manual_eff, rh, dpd, t_air, rain_3h, rain_3h_known, wind, e_*."""
    d = nh[nh.index.hour.isin(truth_hours)].dropna(subset=["cloud_manual_eff"]).copy()
    d["y"] = d["cloud_manual_eff"] <= 2
    d["rain3_flag"] = np.where(d["rain_3h_known"].astype(bool), (d["rain_3h"] > 0).astype(float), np.nan)
    d["no_rain3"] = d["rain_3h_known"].astype(bool) & (d["rain_3h"] == 0)
    d["year"] = d.index.year
    d["month"] = d.index.month
    d["cold"] = d["t_air"] < 0
    d["wet_season"] = d["month"].between(4, 9)
    return d


def fit_predict(train: pd.DataFrame, test: pd.DataFrame) -> tuple:
    """Return (predictions DataFrame on test, thresholds dict)."""
    th = {}
    pred = pd.DataFrame(index=test.index)
    # rules
    for name, col, direction in (("R_dpd", "dpd", "ge"), ("R_rh", "rh", "le")):
        t, j = youden_threshold(train[col], train["y"], direction)
        th[name] = dict(threshold=t, youden_j=j)
        x = test[col]
        p = (x >= t) if direction == "ge" else (x <= t)
        pred[name] = p & test["no_rain3"] & x.notna()
    # ERA5 rules
    for name, col in (("E_tcc", "e_tcc"), ("E_mh", "e_mh")):
        t, j = youden_threshold(train[col], train["y"], "le")
        th[name] = dict(threshold=t, youden_j=j)
        pred[name] = (test[col] <= t) & test[col].notna()
    # climatology baseline (training-year monthly majority)
    clim = train.groupby("month")["y"].mean()
    th["CLIM"] = dict(monthly_clear_share=clim.round(3).to_dict())
    pred["CLIM"] = test["month"].map(clim >= 0.5).fillna(False).astype(bool)
    # logistic regression
    tr = train.dropna(subset=FEATURES); te = test.copy()
    if len(tr) > 50:
        sc = StandardScaler().fit(tr[FEATURES])
        lr = LogisticRegression(max_iter=1000, class_weight="balanced").fit(sc.transform(tr[FEATURES]), tr["y"])
        ok = te[FEATURES].notna().all(axis=1)
        prob = pd.Series(np.nan, index=te.index)
        prob[ok] = lr.predict_proba(sc.transform(te.loc[ok, FEATURES]))[:, 1]
        pred["LR_prob"] = prob
        pred["LR"] = (prob >= 0.5).fillna(False).astype(bool)
        th["LR"] = dict(coef=dict(zip(FEATURES, lr.coef_[0].round(3))), intercept=round(float(lr.intercept_[0]), 3),
                        scaler_mean=dict(zip(FEATURES, sc.mean_.round(3))), scaler_scale=dict(zip(FEATURES, sc.scale_.round(3))))
    return pred, th


def loyo(d: pd.DataFrame, models=("R_dpd", "R_rh", "LR", "E_tcc", "E_mh", "CLIM")):
    """Leave-one-year-out. Returns (fold metrics long table, out-of-fold predictions, thresholds per fold)."""
    rows, preds, ths = [], [], {}
    for y in sorted(d["year"].unique()):
        train, test = d[d.year != y], d[d.year == y]
        if test["y"].nunique() < 2 or len(test) < 30:
            continue
        pred, th = fit_predict(train, test)
        ths[int(y)] = th
        pred["y"] = test["y"]; pred["year"] = y; pred["month"] = test["month"]
        pred["cold"] = test["cold"]; pred["wet_season"] = test["wet_season"]
        preds.append(pred)
        for m in models:
            if m in pred:
                rows.append(dict(model=m, year=y, **metrics(pred["y"], pred[m])))
    return pd.DataFrame(rows), pd.concat(preds), ths


def pooled_metrics(oof: pd.DataFrame, models, by=None) -> pd.DataFrame:
    rows = []
    groups = [("all", oof)] if by is None else list(oof.groupby(by))
    for key, g in groups:
        for m in models:
            if m in g:
                rows.append(dict(group=key, model=m, **metrics(g["y"], g[m])))
    return pd.DataFrame(rows)


def monthly_bias(oof: pd.DataFrame, models) -> pd.DataFrame:
    obs = oof.groupby("month")["y"].mean()
    out = pd.DataFrame({"observed": obs})
    for m in models:
        if m in oof:
            out[m] = oof.groupby("month")[m].mean()
            out[f"{m}_bias"] = out[m] - obs
    return out.round(3)
